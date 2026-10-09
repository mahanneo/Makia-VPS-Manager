"""Safe, dependency-free endpoint selection and compatibility preflight.

No mutation or service restart. For exact public endpoint exports the caller must
select a compatible protocol; TLS transports cannot be silently downgraded to IP.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
from dataclasses import asdict, dataclass
from typing import Literal

DIRECT = {"ssh", "wireguard", "openvpn", "outline", "xray-direct"}
TLS_NAME_REQUIRED = {"browser-gateway", "wstunnel-wss", "openvpn-wstunnel", "stealth-tls", "ikev2-cert"}
ALL = DIRECT | TLS_NAME_REQUIRED
PORTS = {
    "ssh": (22, "tcp"), "wireguard": (51820, "udp"),
    "openvpn": (1194, "udp"), "outline": (0, "tcp/udp"),
    "xray-direct": (0, "tcp/udp"), "browser-gateway": (9444, "tcp"),
    "wstunnel-wss": (8444, "tcp"), "openvpn-wstunnel": (443, "tcp"),
    "stealth-tls": (39443, "tcp"), "ikev2-cert": (500, "udp"),
}

@dataclass
class Check:
    ok: bool
    protocol: str
    endpoint: str
    mode: str
    port: int
    transport: str
    errors: list[str]
    warnings: list[str]
    next_steps: list[str]
    needs_tls_certificate: bool = False
    direct_ip_supported: bool = False
    recommended_for_first_setup: bool = False
    user_message_fa: str = ""

def _host(raw: str):
    raw = str(raw or "").strip()
    if not raw or len(raw) > 253 or "://" in raw or any(c.isspace() for c in raw) or any(c in raw for c in "/?#@"):
        raise ValueError("Enter only the public server IP or hostname; no https://, path, credentials or port.")
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    try:
        ip = ipaddress.ip_address(raw)
        if not ip.is_global:
            raise ValueError("Use a publicly routable server IP, not localhost/private/reserved addresses.")
        return str(ip), "ip"
    except ValueError as exc:
        if "publicly routable" in str(exc):
            raise
    name = raw.rstrip(".").encode("idna").decode("ascii").lower()
    if not name or len(name)>253 or "." not in name:
        raise ValueError("Enter a complete hostname such as vpn.example.com.")
    label = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    if any(not label.fullmatch(x) for x in name.split(".")):
        raise ValueError("Invalid domain label; check dots, hyphens and special characters.")
    return name, "domain"

def evaluate(protocol: str, endpoint: str, port: int | None = None, *,
             resolved_ipv4: list[str] | None = None, server_ipv4: str = "",
             tls_names: list[str] | None = None) -> Check:
    protocol = str(protocol or "").strip().lower()
    if protocol not in ALL:
        raise ValueError("Unsupported protocol. PPTP is intentionally not supported because it is insecure.")
    host, mode = _host(endpoint)
    default, transport = PORTS[protocol]
    try:
        port = default if port is None else int(port)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Port must be an integer between 1 and 65535.") from exc
    errors, warnings, steps = [], [], []
    if server_ipv4:
        try:
            server_address=ipaddress.IPv4Address(server_ipv4)
            if not server_address.is_global:
                errors.append("Server IP must be a publicly routable IPv4 address.")
        except ipaddress.AddressValueError:
            errors.append("Server IP must be a valid public IPv4 address.")
    if not 1 <= port <= 65535:
        errors.append("Choose a port between 1 and 65535.")
    if mode == "ip" and protocol in TLS_NAME_REQUIRED:
        errors.append("This protocol requires a DNS hostname with a matching trusted TLS certificate. IP-only setup is not supported in this mode.")
        steps.append("Use a DNS A record and obtain a TLS certificate for that hostname; or choose classic WireGuard/OpenVPN/SSH.")
    if mode == "domain":
        if resolved_ipv4 is None:
            try:
                resolved_ipv4 = sorted({row[4][0] for row in socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)})
            except (OSError, ValueError):
                resolved_ipv4 = []
        if not resolved_ipv4:
            errors.append("Domain has no IPv4 A record. Create an A record pointing to your VPS.")
        else:
            try:
                parsed_addresses = [ipaddress.IPv4Address(value) for value in resolved_ipv4]
            except (ipaddress.AddressValueError, ValueError, TypeError):
                errors.append("Domain lookup returned an invalid IPv4 A record; verify DNS before creating a profile.")
            else:
                if any(not address.is_global for address in parsed_addresses):
                    errors.append("Domain A record points to a private or non-public IPv4; choose the actual public VPS address.")
                elif server_ipv4 and protocol not in {"xray-direct"} and server_ipv4 not in [str(address) for address in parsed_addresses]:
                    errors.append("Domain A record does not point at the selected server IP; raw VPN protocols must not use an HTTP-only CDN proxy.")
        # End of DNS A record validation.
        if protocol in TLS_NAME_REQUIRED:
            if tls_names is None:
                warnings.append("TLS certificate coverage cannot be confirmed offline; verify on the VPS before activating.")
            elif host not in [x.lower().rstrip(".") for x in tls_names]:
                errors.append("The TLS certificate does not contain this hostname.")
        if protocol in {"ssh", "wireguard", "openvpn", "outline"}:
            steps.append("DNS-only A record recommended; CDN HTTP proxy is not compatible with this direct protocol.")
    if protocol == "outline":
        warnings.append("Outline ports are assigned by Outline; use the port from its generated access key.")
    if protocol == "ikev2-cert":
        steps.append("Also verify UDP/500 and UDP/4500, matching server certificate identity and client trust.")
    if protocol == "wireguard":
        steps.append("Confirm UDP listener, server forwarding/NAT and client handshake; a generated QR alone is not proof.")
    if protocol == "openvpn":
        steps.append("Verify server's actual UDP/TCP transport matches the .ovpn profile.")
    if protocol == "browser-gateway":
        steps.append("Requires HTTPS proxy port, proxy authentication, and a real external IP check in Chrome/Edge.")
    # A successful endpoint preflight is not a verified service/handshake.
    needs_tls = protocol in TLS_NAME_REQUIRED
    beginner = protocol in {"ssh", "wireguard", "openvpn"} and mode == "ip"
    if errors:
        fa = "آدرس یا پورت برای این پروتکل معتبر نیست؛ ابتدا خطاها را اصلاح کنید."
    elif warnings:
        fa = "بررسی اولیه موفق بود؛ هشدارها و اتصال واقعی را جدا بررسی کنید."
    else:
        fa = "مشخصات اولیه درست است؛ وضعیت سرویس، فایروال و اتصال واقعی هنوز باید بررسی شود."
    return Check(not errors, protocol, host, mode, port, transport, errors, warnings, steps,
                 needs_tls_certificate=needs_tls,
                 direct_ip_supported=protocol in DIRECT,
                 recommended_for_first_setup=beginner,
                 user_message_fa=fa)

def main():
    parser=argparse.ArgumentParser(description="Makia IP/domain endpoint preflight (read-only)")
    parser.add_argument("--protocol", required=True, choices=sorted(ALL))
    parser.add_argument("--endpoint", required=True, help="Public IP or hostname only")
    parser.add_argument("--port", type=int)
    parser.add_argument("--server-ip", default="", help="Known public VPS IPv4 for DNS matching")
    parser.add_argument("--json", action="store_true")
    args=parser.parse_args()
    try:
        result=evaluate(args.protocol,args.endpoint,args.port,server_ipv4=args.server_ip)
    except ValueError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(asdict(result),ensure_ascii=False,indent=2))
    else:
        print(f"Protocol: {result.protocol} | Endpoint: {result.endpoint}:{result.port} ({result.transport})")
        print("READY FOR NEXT SETUP STEP" if result.ok else "NOT READY — no changes made")
        for group,rows in (("ERROR",result.errors),("WARNING",result.warnings),("NEXT",result.next_steps)):
            for row in rows: print(f"{group}: {row}")
    return 0 if result.ok else 2

if __name__=="__main__":
    raise SystemExit(main())
