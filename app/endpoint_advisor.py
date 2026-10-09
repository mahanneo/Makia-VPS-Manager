"""Read-only, security-conscious connection address recommendations.

Do not mistake a local private interface address, an open port, or a running
service for proof that a VPN works over the public Internet.
"""
import ipaddress
import os

from app import protocol_ops
from app.db import get_setting


def _public_ipv4(value):
    try:
        parsed=ipaddress.ip_address(str(value or "").strip())
    except ValueError:
        return ""
    return parsed.compressed if parsed.version == 4 and parsed.is_global else ""


def connection_setup():
    configured=_public_ipv4(os.getenv("MAKIA_PUBLIC_IPV4", ""))
    candidates=[]
    for item in [configured, *protocol_ops._local_ipv4_candidates()]:
        ip=_public_ipv4(item)
        if ip and ip not in candidates:
            candidates.append(ip)
    domain=str(get_setting("panel_domain", "") or "").strip().lower()
    if domain:
        domain=protocol_ops._validate_endpoint_host(domain, "panel domain")
        if _public_ipv4(domain):
            domain=""
    dns4=[]
    dns_status=None
    tls_certificate=False
    certificate_expires_in=None
    if domain:
        from app import panel_ops
        status=panel_ops.domain_status(domain)
        dns4=list(status.get("resolved_ipv4") or [])
        tls_certificate=bool(status.get("certificate") and status.get("https_listener"))
        certificate_expires_in=status.get("certificate_days_left")
        if dns4 and candidates:
            dns_status=bool(set(dns4).intersection(candidates))
    recommended_mode="domain" if domain and tls_certificate and dns_status is not False else "ip"
    preferred=(candidates[0] if candidates else "") if recommended_mode=="ip" else domain
    if not preferred and domain:
        preferred=domain
        recommended_mode="domain"
    options={
        "ip":{"value":candidates[0] if candidates else "",
              "available":bool(candidates),
              "label":"Public IPv4 / آی‌پی عمومی",
              "help":"سرور مستقیم از IP قابل‌دسترسی است. برای اتصال رمزدار TLS با IP، اعتبار گواهی باید جداگانه تأیید شود."},
        "domain":{"value":domain,"available":bool(domain),
                  "label":"Domain / دامنه",
                  "help":"رکورد A باید برای SSH، WireGuard و OpenVPN مستقیم به VPS برسد (DNS only)."},
    }
    protocols={
        "ssh":{"supports_ip":True,"supports_domain":True,"tls_domain_required":False,"default_port":22},
        "wireguard":{"supports_ip":True,"supports_domain":True,"tls_domain_required":False,"default_port":51820},
        "openvpn":{"supports_ip":True,"supports_domain":True,"tls_domain_required":False,"default_port":1194},
        "xray":{"supports_ip":True,"supports_domain":True,"tls_domain_required":False,"default_port":2087,
                "note":"REALITY can use a public IPv4 endpoint; TLS/Hysteria2 needs valid certificate and SNI."},
        "openvpn_wstunnel":{"supports_ip":False,"supports_domain":True,"tls_domain_required":True,"default_port":443,
                            "note":"Existing managed WSS/HTTPS front door requires a trusted TLS hostname."},
        "ikev2":{"supports_ip":True,"supports_domain":True,"tls_domain_required":False,"default_port":500,
                 "note":"IKEv2 certificate identity/IP SAN must match the chosen server address; UDP 500/4500."},
        "outline":{"supports_ip":True,"supports_domain":True,"tls_domain_required":False,"default_port":0,
                   "note":"The Outline Server controls its actual access-key port; this is not a fixed default."},
        "pptp":{"supports_ip":False,"supports_domain":False,"tls_domain_required":False,"default_port":0,
                "unsupported":True,
                "note":"PPTP/MS-CHAPv2 is deprecated and unsafe; use IKEv2, WireGuard or OpenVPN."}
    }
    warnings=[]
    if not candidates:
        warnings.append("هیچ IPv4 عمومی روی کارت شبکه پیدا نشد؛ در سرورهای NAT مقدار MAKIA_PUBLIC_IPV4 را تنظیم کنید.")
    if domain and not dns4:
        warnings.append("دامنه رکورد A ندارد؛ ابتدا DNS را تنظیم کنید.")
    if dns_status is False:
        warnings.append("آی‌پی رکورد A با آی‌پی عمومی شناسایی‌شده سرور متفاوت است؛ اتصال مستقیم را بررسی کنید.")
    if domain and not tls_certificate:
        warnings.append("گواهی HTTPS دامنه هنوز فعال نیست؛ TLS/WSS را قبل از ساخت کاربر فعال و تست کنید.")
    if certificate_expires_in is not None and certificate_expires_in <= 0:
        warnings.append("گواهی دامنه منقضی شده است.")
    return {
        "recommended_mode":recommended_mode,
        "recommended_endpoint":preferred,
        "choices":options,
        "public_ipv4":candidates,
        "domain":domain,
        "domain_dns_ipv4":dns4,
        "domain_dns_matches_server":dns_status,
        "domain_tls_ready":tls_certificate,
        "protocols":protocols,
        "warnings":warnings,
        "ip_panel_url":("http://"+candidates[0]+"/") if candidates else "",
        "domain_panel_url":("https://"+domain+"/") if domain and tls_certificate else "",
        "security_note":"IP-based HTTP panel login is unencrypted. Use HTTPS with a trusted hostname for administration; an IP-only TLS certificate must explicitly include that IP.",
        "verification_note":"این پیشنهادها فقط بررسی مقدماتی‌اند؛ اتصال و خروج ترافیک باید با دستگاه واقعی آزمایش شود.",
    }
