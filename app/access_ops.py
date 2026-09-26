import base64
import hashlib
import io
import json
import re
import urllib.parse

from cryptography.fernet import Fernet, InvalidToken
import pyzipper
import qrcode
import qrcode.image.svg

from .security import ensure_secret

class AccessPackageError(RuntimeError):
    pass

def _fernet():
    key=hashlib.sha256(ensure_secret()+b"makia-access-artifact-v1").digest()
    return Fernet(base64.urlsafe_b64encode(key))

def _json_pack(value):
    if isinstance(value,(bytes,bytearray)):
        return {"__makia_bytes__":base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value,dict):
        return {str(k):_json_pack(v) for k,v in value.items()}
    if isinstance(value,list):
        return [_json_pack(v) for v in value]
    if isinstance(value,tuple):
        return [_json_pack(v) for v in value]
    return value

def _json_unpack(value):
    if isinstance(value,dict):
        if set(value)=={"__makia_bytes__"}:
            return base64.b64decode(value["__makia_bytes__"])
        return {k:_json_unpack(v) for k,v in value.items()}
    if isinstance(value,list):
        return [_json_unpack(v) for v in value]
    return value

def seal_payload(payload:dict)->str:
    raw=json.dumps(_json_pack(payload),ensure_ascii=False,separators=(",",":")).encode("utf-8")
    return _fernet().encrypt(raw).decode("ascii")

def open_payload(token:str)->dict:
    try:
        raw=_fernet().decrypt(str(token).encode("ascii"))
        obj=json.loads(raw.decode("utf-8"))
        obj=_json_unpack(obj)
        if not isinstance(obj,dict):
            raise AccessPackageError("invalid access payload")
        return obj
    except (InvalidToken,ValueError,TypeError,json.JSONDecodeError) as exc:
        raise AccessPackageError("unable to decrypt access payload") from exc

def safe_filename(value:str, fallback="access"):
    value=re.sub(r"[^A-Za-z0-9_.-]+","-",str(value or "")).strip(".-")
    return (value or fallback)[:96]

def safe_archive_name(value:str,fallback="file"):
    raw=str(value or "").replace("\\","/").strip("/")
    parts=[]
    for part in raw.split("/"):
        if not part or part in {".",".."}:
            continue
        clean=safe_filename(part,fallback)
        if clean:
            parts.append(clean)
    return "/".join(parts) if parts else fallback

def make_qr_svg(text:str)->bytes:
    img=qrcode.make(text,image_factory=qrcode.image.svg.SvgPathImage)
    buf=io.BytesIO()
    img.save(buf)
    return buf.getvalue()

def describe_xray_share(link:str,protocol:str|None=None)->dict:
    link=str(link or "").strip()
    proto=str(protocol or "").strip().lower()
    if not link:
        return {"protocol":proto or "unknown"}
    try:
        if link.startswith("vmess://"):
            raw=link[len("vmess://"):]
            obj=json.loads(base64.b64decode(raw+"="*(-len(raw)%4)).decode("utf-8"))
            return {
                "protocol":"vmess",
                "label":str(obj.get("ps") or ""),
                "host":str(obj.get("add") or ""),
                "port":int(obj.get("port") or 0),
                "transport":str(obj.get("net") or "tcp"),
                "security":str(obj.get("tls") or "none"),
                "path":str(obj.get("path") or ""),
                "host_header":str(obj.get("host") or ""),
            }
        parsed=urllib.parse.urlsplit(link)
        scheme=(parsed.scheme or proto or "").lower()
        query={k:(v[-1] if isinstance(v,list) and v else v) for k,v in urllib.parse.parse_qs(parsed.query,keep_blank_values=True).items()}
        label=urllib.parse.unquote(parsed.fragment or "")
        host=parsed.hostname or ""
        port=int(parsed.port or 0)
        if scheme in {"vless","trojan"}:
            return {
                "protocol":scheme,
                "label":label,
                "host":host,
                "port":port,
                "transport":str(query.get("type") or "tcp"),
                "security":str(query.get("security") or "none"),
                "sni":str(query.get("sni") or ""),
                "path":str(query.get("path") or query.get("serviceName") or ""),
                "flow":str(query.get("flow") or ""),
                "fingerprint":str(query.get("fp") or ""),
                "reality_public_key":str(query.get("pbk") or ""),
                "reality_short_id":str(query.get("sid") or ""),
            }
        if scheme in {"hysteria2","hy2"}:
            return {
                "protocol":"hysteria2",
                "label":label,
                "host":host,
                "port":port,
                "transport":"hysteria2",
                "security":"tls",
                "sni":str(query.get("sni") or ""),
                "insecure":str(query.get("insecure") or "0"),
            }
        if scheme=="ss":
            userinfo=parsed.username or ""
            cipher=""
            try:
                decoded=base64.urlsafe_b64decode(userinfo+"="*(-len(userinfo)%4)).decode("utf-8")
                cipher=decoded.split(":",1)[0]
            except Exception:
                pass
            return {
                "protocol":"shadowsocks",
                "label":label,
                "host":host,
                "port":port,
                "transport":"tcp/udp",
                "security":"shadowsocks",
                "cipher":cipher,
            }
        return {"protocol":scheme or proto or "unknown","label":label,"host":host,"port":port}
    except Exception:
        return {"protocol":proto or "unknown"}

def npvt_ssh_link(host,username,password,port=22,remarks=None,dns_mode="UDP",udpgw_port=7300,transparent_dns=False):
    profile={
        "sshConfigType":"SSH-Direct",
        "remarks":str(remarks or f"Makia {username}"),
        "sshHost":str(host or "").strip(),
        "sshPort":int(port or 22),
        "sshUsername":str(username or "").strip(),
        "sshPassword":str(password or ""),
        "sni":"",
        "tlsVersion":"DEFAULT",
        "httpProxy":"",
        "authenticateProxy":False,
        "proxyUsername":"",
        "proxyPassword":"",
        "payload":"",
        "dnsTTMode":str(dns_mode or "UDP").upper(),
        "dnsServer":"",
        "nameserver":"",
        "publicKey":"",
        "udpgwPort":int(udpgw_port or 7300),
        "udpgwTransparentDNS":bool(transparent_dns),
    }
    raw=json.dumps(profile,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    return "npvt-ssh://"+base64.b64encode(raw).decode("ascii")

def client_guide_text(kind,protocol=""):
    kind=str(kind or "").lower()
    protocol=str(protocol or "").upper()
    common=(
        "راهنمای اتصال Makia\n"
        "====================\n"
        "این فایل فقط راهنمای استفاده است. Credential را در گروه یا کانال عمومی ارسال نکنید.\n\n"
    )
    if kind=="xray":
        return common+(
            f"نوع پروفایل: {protocol or 'XRAY'}\n"
            "1) روش ساده: QR مستقیم را با v2rayNG / Hiddify / NekoBox یا کلاینت سازگار اسکن کنید.\n"
            "2) یا Share Link را کپی و Import from Clipboard را انتخاب کنید.\n"
            "3) اگر Subscription URL دارید، آن را در بخش Subscription برنامه اضافه و Refresh کنید.\n"
            "4) UUID/Password/SNI/Public Key/Short ID/Port را بدون هماهنگی تغییر ندهید.\n"
            "5) اگر وصل نشد، Wi-Fi و Mobile Data را جداگانه تست و متن خطا را برای مدیر ارسال کنید.\n"
        )
    if kind=="wireguard":
        return common+(
            "WireGuard\n"
            "1) موبایل: برنامه رسمی WireGuard > + > Create from QR code یا Import from file.\n"
            "2) Windows/macOS: Import tunnel(s) from file و فایل .conf را انتخاب کنید.\n"
            "3) Endpoint/Port/MTU/DNS را بدون هماهنگی تغییر ندهید.\n"
        )
    if kind=="openvpn":
        return common+(
            "OpenVPN\n"
            "1) OpenVPN Connect را باز کنید.\n"
            "2) Upload File / Import Profile را انتخاب کنید.\n"
            "3) فایل .ovpn را Import و سپس Connect کنید.\n"
            "4) فایل OVPN شامل اطلاعات اختصاصی همان کاربر است.\n"
        )
    return common+(
        "SSH / NPV Tunnel\n"
        "1) برای NPV Tunnel / NapsternetV سازگار، لینک npvt-ssh:// را Import from Clipboard کنید یا QR را اسکن کنید.\n"
        "2) برای SSH معمولی از Server, Port, Username و Password داخل credentials.txt استفاده کنید.\n"
        "3) OpenSSH رمز عبور را داخل config ذخیره نمی‌کند.\n"
    )

def ssh_payload(host,username,password,port=22,npv_options=None):
    host=str(host or "").strip()
    username=str(username or "").strip()
    port=int(port or 22)
    config=(
        f"Host makia-{safe_filename(username)}\n"
        f"    HostName {host}\n"
        f"    User {username}\n"
        f"    Port {port}\n"
        "    ServerAliveInterval 30\n"
        "    ServerAliveCountMax 3\n"
    )
    opts=dict(npv_options or {})
    npv_enabled=bool(opts.get("enabled",True))
    npv=""
    files={f"{safe_filename(username)}-ssh-config.txt":config.encode("utf-8")}
    if npv_enabled:
        npv=npvt_ssh_link(
            host,username,password,port,
            remarks=opts.get("remarks") or f"Makia {username}",
            dns_mode=opts.get("dns_mode") or "UDP",
            udpgw_port=int(opts.get("udpgw_port") or 7300),
            transparent_dns=bool(opts.get("transparent_dns",False)),
        )
    credentials=(
        "Makia SSH Access\n"
        f"Server: {host}\n"
        f"Port: {port}\n"
        f"Username: {username}\n"
        f"Password: {password}\n"
    )
    if npv_enabled:
        credentials += (
            "\nNPV Tunnel / NapsternetV quick import:\n"
            f"{npv}\n"
            "\nImport the npvt-ssh link from clipboard or scan its QR in a compatible NPV client.\n"
        )
    credentials += (
        "\nOpenSSH does not support embedding passwords in config files.\n"
        "Use the included OpenSSH fragment for ordinary SSH clients.\n"
    )
    files["credentials.txt"]=credentials.encode("utf-8")
    files["connection-guide-fa.txt"]=client_guide_text("ssh").encode("utf-8")
    summary={"host":host,"port":port,"username":username,"npv_enabled":npv_enabled}
    result={
        "native_filename":f"{safe_filename(username)}-ssh-config.txt",
        "files":files,
        "primary_text":credentials,
        "summary":summary,
    }
    if npv_enabled:
        npv_name=f"{safe_filename(username)}-npvt-ssh.txt"
        files[npv_name]=(npv+"\n").encode("utf-8")
        files[f"{safe_filename(username)}-npvt-qr.svg"]=make_qr_svg(npv)
        result["share_text"]=npv
        result["share_type"]="npvt-ssh"
        summary.update({
            "npv_link":npv,"npv_filename":npv_name,
            "npv_dns_mode":str(opts.get("dns_mode") or "UDP").upper(),
            "npv_udpgw_port":int(opts.get("udpgw_port") or 7300),
            "npv_transparent_dns":bool(opts.get("transparent_dns",False)),
        })
    return result


def wireguard_payload(name,config,address=None,alternate_config=None,alternate_label="ip"):
    safe=safe_filename(name)
    filename=f"{safe}.conf"
    files={
        filename:str(config).encode("utf-8"),
        f"{safe}-qr.svg":make_qr_svg(str(config)),
        "connection-guide-fa.txt":client_guide_text("wireguard").encode("utf-8"),
    }
    if alternate_config:
        alt_label=safe_filename(alternate_label or "alternate")
        files[f"{safe}-{alt_label}.conf"]=str(alternate_config).encode("utf-8")
        files[f"{safe}-{alt_label}-qr.svg"]=make_qr_svg(str(alternate_config))
    return {
        "native_filename":filename,
        "files":files,
        "primary_text":str(config),
        "share_text":str(config),
        "share_type":"wireguard",
        "summary":{"address":address or "","alternate_profile":bool(alternate_config),"alternate_label":alternate_label if alternate_config else ""},
    }
def openvpn_payload(name,config):
    filename=f"{safe_filename(name)}.ovpn"
    return {
        "native_filename":filename,
        "files":{
            filename:str(config).encode("utf-8"),
            "connection-guide-fa.txt":client_guide_text("openvpn").encode("utf-8"),
        },
        "primary_text":str(config),
        "summary":{},
    }

def xray_payload(name,protocol,share_link,subscription_url=None,client_url=None):
    profile={
        "name":name,
        "protocol":protocol,
        "share_link":share_link,
        "subscription_url":subscription_url or "",
        "client_page":client_url or "",
    }
    filename=f"{safe_filename(name)}-{safe_filename(protocol)}.txt"
    lines=[
        "Makia Xray Access",
        f"Name: {name}",
        f"Protocol: {protocol}",
        "",
        "Share link:",
        str(share_link),
    ]
    if subscription_url:
        lines += ["","Subscription:",str(subscription_url)]
    if client_url:
        lines += ["","Client page:",str(client_url)]
    text="\n".join(lines)+"\n"
    files={
        filename:text.encode("utf-8"),
        f"{safe_filename(name)}-profile.json":json.dumps(profile,ensure_ascii=False,indent=2).encode("utf-8"),
        f"{safe_filename(name)}-qr.svg":make_qr_svg(str(share_link)),
        "connection-guide-fa.txt":client_guide_text("xray",protocol).encode("utf-8"),
    }
    if subscription_url:
        files[f"{safe_filename(name)}-subscription.txt"]=(str(subscription_url)+"\n").encode("utf-8")
        files[f"{safe_filename(name)}-subscription-qr.svg"]=make_qr_svg(str(subscription_url))
    return {
        "native_filename":filename,
        "files":files,
        "primary_text":str(share_link),
        "share_text":str(share_link),
        "share_type":"xray",
        "summary":{"protocol":protocol,"subscription_url":subscription_url or "","client_url":client_url or ""},
    }

def protected_zip(files:dict[str,bytes|str],password:str)->bytes:
    password=str(password or "")
    if len(password)<4:
        raise AccessPackageError("package password must be at least 4 characters")
    buf=io.BytesIO()
    with pyzipper.AESZipFile(buf,"w",compression=pyzipper.ZIP_DEFLATED,encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(password.encode("utf-8"))
        zf.setencryption(pyzipper.WZ_AES,nbits=256)
        for name,data in files.items():
            filename=safe_archive_name(name,"file")
            raw=data.encode("utf-8") if isinstance(data,str) else bytes(data)
            zf.writestr(filename,raw)
    return buf.getvalue()


def verify_protected_zip(blob:bytes,password:str,expected_name:str|None=None)->dict:
    try:
        with pyzipper.AESZipFile(io.BytesIO(bytes(blob)),"r") as zf:
            zf.setpassword(str(password).encode("utf-8"))
            names=zf.namelist()
            if not names:
                raise AccessPackageError("protected package is empty")
            target=expected_name if expected_name in names else names[0]
            sample=zf.read(target)
            return {"ok":True,"files":names,"sample_size":len(sample)}
    except Exception as exc:
        if isinstance(exc,AccessPackageError):
            raise
        raise AccessPackageError("protected package verification failed") from exc
