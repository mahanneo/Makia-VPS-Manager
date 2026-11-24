"""Configure fresh Makia VPS: domain-specific TLS, unique Xray keys and private DNS."""
import os,sys,json,shutil,subprocess,re,tempfile
from pathlib import Path
sys.path.insert(0,'/opt/makia-vps-manager')
from app import panel_ops,protocol_ops as p,network_services as n
from app.db import connect,set_setting
if len(sys.argv)!=3 or os.geteuid()!=0: raise SystemExit('Usage: configure-fresh.py DOMAIN EMAIL as root')
domain=panel_ops.validate_domain(sys.argv[1]);email=sys.argv[2]
with connect() as c:
 if c.execute('select count(*) from protocol_clients').fetchone()[0] or c.execute('select count(*) from client_accounts').fetchone()[0]:
  raise SystemExit('This setup is only for a fresh installation without client credentials.')
if not Path(f'/etc/letsencrypt/live/{domain}/fullchain.pem').is_file():panel_ops.issue_certificate(domain,email)
else:panel_ops.apply_domain(domain)
set_setting('panel_domain',domain)
config=Path(p._config_path());binary=p._binary()
original=config.read_bytes();data=json.loads(original)
if any((i.get('settings') or {}).get('clients') for i in data.get('inbounds',[])):raise SystemExit('Existing Xray clients found; refusing to replace configuration')
# Keep the standard stats-enabled server profile, with no copied private keys or users.
specs=[('makia-IR-xhttp-reality-lab-2053-2053','vless',2053,'xhttp','reality','/makia-xhttp'),('makia-IR-reality-raw-vision-443-11443','vless',11443,'raw','reality','/'),('makia-IR-vmess-ws-tls-13001-13001','vmess',13001,'websocket','tls','/makia-vmess'),('makia-IR-trojan-grpc-tls-13002-13002','trojan',13002,'grpc','tls','/makia-trojan'),(p.LEGACY_WS443_TAG,'vless',13003,'websocket','tls','/makia-ws')]
known={i['tag'] for i in data.get('inbounds',[]) if 'tag' in i}
for tag,proto,port,transport,security,path in specs:
 if tag in known:continue
 if p._port_transport_in_use(port,'tcp'):raise RuntimeError(f'Port {port} is already in use')
 stream,_=p._xray_builder_stream(binary,proto,transport,security,{'path':path,'server_name':domain if security=='tls' else 'www.microsoft.com','reality_dest':'www.microsoft.com:443','xhttp_mode':'packet-up','host':domain if transport=='websocket' else ''})
 settings={'clients':[]}
 if proto=='vless':settings['decryption']='none'
 data.setdefault('inbounds',[]).append({'tag':tag,'listen':'0.0.0.0','port':port,'protocol':proto,'settings':settings,'streamSettings':stream})
p._ensure_xray_stats(data)
backup=Path('/var/backups/makia-vps-manager/fresh-config');backup.mkdir(mode=0o700,exist_ok=True)
(backup/'xray-original.json').write_bytes(original);os.chmod(backup/'xray-original.json',0o600)
tmp=p._xray_temp_json_path(config,'fresh');tmp.write_text(json.dumps(data,indent=2)+'\n');os.chmod(tmp,0o600)
try:
 p._xray_test_config(binary,tmp);os.replace(tmp,config);p._xray_secure_runtime_file(config);p._xray_test_config_as_service(binary,config)
 subprocess.run(['systemctl','restart','xray'],check=True);subprocess.run(['systemctl','is-active','--quiet','xray'],check=True)
except Exception:
 tmp.unlink(missing_ok=True);config.write_bytes(original);p._xray_secure_runtime_file(config);subprocess.run(['systemctl','restart','xray'],check=False);raise
site=panel_ops.NGINX_SITE;old=site.read_text();snippet=Path('/etc/nginx/snippets/makia-unified-https.conf')
parts=[]
for public,backend,internal in ((p.LEGACY_WS443_PATH,13003,'/makia-ws'),('/makia-vmess',13001,'/makia-vmess')):
 parts.append(f'''location = {public} {{
    proxy_pass https://127.0.0.1:{backend}{internal};
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host {domain};
    proxy_ssl_server_name on;
    proxy_ssl_name {domain};
    proxy_ssl_verify on;
    proxy_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_buffering off;
}}''')
parts.append(f'''location ^~ /makia-trojan/ {{
    grpc_pass grpcs://127.0.0.1:13002;
    grpc_set_header Host {domain};
    grpc_ssl_server_name on;
    grpc_ssl_name {domain};
    grpc_ssl_verify on;
    grpc_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;
    grpc_read_timeout 3600s;
    grpc_send_timeout 3600s;
}}''')
snippet.write_text('\n\n'.join(parts)+'\n')
if str(snippet) not in old:
 updated,num=re.subn(r'(?m)^(\s*listen\s+443\s+ssl)([^;]*);',lambda m:m.group(1)+(m.group(2) if 'http2' in m.group(2) else ' http2'+m.group(2))+';\n    include '+str(snippet)+';',old,count=1)
 if num!=1:raise RuntimeError('Could not find HTTPS Nginx server block')
 updated=re.sub(r'(?m)^(\s*listen\s+\[::\]:443\s+ssl)([^;]*);',lambda m:m.group(1)+(m.group(2) if 'http2' in m.group(2) else ' http2'+m.group(2))+';',updated,count=1)
 (backup/'nginx-original.conf').write_text(old);site.write_text(updated)
 try:subprocess.run(['nginx','-t'],check=True);subprocess.run(['systemctl','reload','nginx'],check=True)
 except Exception:site.write_text(old);subprocess.run(['systemctl','reload','nginx'],check=False);raise
p.ensure_openvpn_tcp_fallback(8443)
os.chmod('/etc/openvpn/server/crl.pem',0o644)
n.configure_dns('private','cloudflare');set_setting('default_wireguard_dns','10.66.66.1')
print('Fresh Xray TLS routes, OpenVPN TCP fallback and private WireGuard DNS configured')
