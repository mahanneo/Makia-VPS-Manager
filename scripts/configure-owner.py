#!/usr/bin/env python3
import argparse
import os
import re
import urllib.parse
from pathlib import Path

ENV_PATH=Path("/etc/makia-vps-manager/makia.env")

def parse_existing():
    out={}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8",errors="ignore").splitlines():
            line=raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k,v=line.split("=",1)
            out[k.strip()]=v.strip().strip('"').strip("'")
    return out

def main():
    p=argparse.ArgumentParser(description="Configure Makia owner/support and public client URLs.")
    p.add_argument("--telegram",default=None,help="Telegram username without @")
    p.add_argument("--webhook",default=None,help="Optional HTTPS support webhook")
    p.add_argument("--support-token",default=None,help="Bearer token used for secure ticket ingestion")
    p.add_argument("--release-archive-url",default=None,help="Optional private release .tar.gz URL")
    p.add_argument("--release-token",default=None,help="Optional bearer token for private release download")
    p.add_argument("--admin-cidrs",default=None,help="Optional comma-separated admin CIDRs, e.g. 203.0.113.4/32,10.0.0.0/8")
    p.add_argument("--public-base-url",default=None,help="Public HTTPS Makia origin used by native Direct Connect")
    p.add_argument("--android-connector-url",default=None,help="HTTPS URL of the approved Makia Android Connector APK")
    args=p.parse_args()
    data=parse_existing()
    if args.telegram is not None:
        username=args.telegram.strip().lstrip("@")
        if username and not re.fullmatch(r"[A-Za-z0-9_]{5,32}",username):
            raise SystemExit("Invalid Telegram username")
        data["MAKIA_SUPPORT_TELEGRAM"]=username
    if args.webhook is not None:
        url=args.webhook.strip()
        if url:
            parsed=urllib.parse.urlparse(url)
            if parsed.scheme!="https" or not parsed.netloc:
                raise SystemExit("Support webhook must be HTTPS")
        data["MAKIA_SUPPORT_WEBHOOK_URL"]=url
    if args.support_token is not None:
        data["MAKIA_SUPPORT_WEBHOOK_TOKEN"]=args.support_token.strip()
    if args.release_archive_url is not None:
        url=args.release_archive_url.strip()
        if url:
            parsed=urllib.parse.urlparse(url)
            if parsed.scheme!="https" or not parsed.netloc:
                raise SystemExit("Release archive URL must be HTTPS")
        data["MAKIA_RELEASE_ARCHIVE_URL"]=url
    if args.release_token is not None:
        data["MAKIA_RELEASE_BEARER_TOKEN"]=args.release_token.strip()
    if args.public_base_url is not None:
        url=args.public_base_url.strip().rstrip("/")
        if url:
            parsed=urllib.parse.urlparse(url)
            if parsed.scheme!="https" or not parsed.netloc or parsed.path not in {"","/"} or parsed.query or parsed.fragment:
                raise SystemExit("Public base URL must be an HTTPS origin without path/query/fragment")
        data["MAKIA_PUBLIC_BASE_URL"]=url
    if args.android_connector_url is not None:
        url=args.android_connector_url.strip()
        if url:
            parsed=urllib.parse.urlparse(url)
            if parsed.scheme!="https" or not parsed.netloc:
                raise SystemExit("Android connector URL must be HTTPS")
        data["MAKIA_ANDROID_CONNECTOR_URL"]=url
    if args.admin_cidrs is not None:
        import ipaddress
        values=[]
        for item in args.admin_cidrs.split(","):
            item=item.strip()
            if not item:
                continue
            values.append(str(ipaddress.ip_network(item,strict=False)))
        data["MAKIA_ADMIN_ALLOWED_CIDRS"]=",".join(values)
    ENV_PATH.parent.mkdir(parents=True,exist_ok=True)
    keys=[
        "MAKIA_SUPPORT_TELEGRAM","MAKIA_SUPPORT_WEBHOOK_URL","MAKIA_SUPPORT_WEBHOOK_TOKEN",
        "MAKIA_RELEASE_ARCHIVE_URL","MAKIA_RELEASE_BEARER_TOKEN","MAKIA_ADMIN_ALLOWED_CIDRS",
        "MAKIA_CLIENT_PORTAL_ENABLED","MAKIA_PUBLIC_BASE_URL","MAKIA_ANDROID_CONNECTOR_URL",
    ]
    body="# Makia owner/distribution configuration. Keep this file root-only.\n"
    for key in keys:
        default="auto" if key=="MAKIA_CLIENT_PORTAL_ENABLED" else ""
        value=data.get(key,default)
        body+=f"{key}={value}\n"
    ENV_PATH.write_text(body,encoding="utf-8")
    os.chmod(ENV_PATH,0o600)
    print(f"Updated {ENV_PATH}")
    print("Restart with: systemctl restart makia-vps-manager")

if __name__=="__main__":
    main()
