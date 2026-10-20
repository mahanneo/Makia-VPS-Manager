"""Truthful Windows built-in VPN onboarding; no VPN daemon provisioning here.

IKEv2 reuses Makia's one and only strongSwan owner (protocol_ops). SSTP and
L2TP/IPsec must not be marked ready or provisioned without independently
validated runtime, authentication, port ownership, firewall and real UAT.
"""
import ipaddress
import re

from . import protocol_ops


class NativeWindowsError(ValueError):
    pass


def profile_script(kind, host):
    """Produce a credential-free, Windows built-in client setup script.

    Never serialize passwords, PSKs, session tokens or private certificates.
    The Windows credential UI handles the first user/password entry.
    """
    kind=str(kind or "").lower().strip()
    if kind!="ikev2":
        raise NativeWindowsError("Only the existing managed IKEv2 runtime supports native profile export")
    host=protocol_ops._validate_endpoint_host(host)
    if not re.fullmatch(r"[a-z0-9.-]{3,253}",host) or "." not in host:
        raise NativeWindowsError("IKEv2 requires a certificate-matching DNS hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise NativeWindowsError("IKEv2 profile must use a DNS hostname matching the TLS certificate")
    try:
        # No arbitrary expression/string injection into PowerShell.
        if any(ch in host for ch in "'\"`$;()[]{} \\"):
            raise NativeWindowsError("Invalid server hostname")
    except TypeError as exc:
        raise NativeWindowsError("Invalid server hostname") from exc
    return """# Makia Windows built-in VPN — IKEv2
# Run in Windows PowerShell 5.1+ as your normal Windows user.
# This file contains NO username, password, PSK or certificate private key.
# Check that this DNS hostname matches the trusted server certificate.
$ErrorActionPreference = 'Stop'
$server = '%s'
$name = 'Makia IKEv2'
if (-not (Get-Command Add-VpnConnection -ErrorAction SilentlyContinue)) {
    throw 'This Windows edition does not expose the built-in VpnClient PowerShell module.'
}
$existing = Get-VpnConnection -Name $name -ErrorAction SilentlyContinue
if ($existing) {
    if ($existing.ServerAddress -ne $server -or $existing.TunnelType -ne 'Ikev2') {
        throw 'An existing Makia IKEv2 profile differs. Check it manually; no automatic overwrite.'
    }
    Write-Host 'Makia IKEv2 profile already exists; no overwrite.' -ForegroundColor Cyan
} else {
    Add-VpnConnection -Name $name -ServerAddress $server -TunnelType Ikev2 `
        -AuthenticationMethod Eap -EncryptionLevel Required -RememberCredential `
        -Force -ErrorAction Stop | Out-Null
    Write-Host 'Makia IKEv2 profile created.' -ForegroundColor Green
}
Write-Host 'Open Windows Settings > Network & Internet > VPN; connect to Makia IKEv2.'
Write-Host 'At first connect, enter the account-specific IKEv2 username/password supplied by the administrator.'
Write-Host 'If server identity/certificate validation fails, STOP: never bypass it.'
Start-Process 'ms-settings:network-vpn'
""" % host


def readiness():
    ike=protocol_ops.ikev2_status()
    listeners=ike.get("listeners") or {}
    ike_ready=bool(
        ike.get("installed") and ike.get("configured") and ike.get("service_active")
        and listeners.get("500_udp") and listeners.get("4500_udp")
        and ike.get("domain")
    )
    return {"protocols":[
        {"id":"ikev2","label":"IKEv2","native_windows":True,"ready":ike_ready,
         "ports":["UDP/500","UDP/4500"],"endpoint":ike.get("domain") or "",
         "reason":"" if ike_ready else "Existing strongSwan needs HTTPS certificate, server config, running service and both UDP listeners.",
         "delivery":"PowerShell Windows built-in VPN profile; password entered at first connect"},
        {"id":"sstp","label":"SSTP","native_windows":True,"ready":False,
         "ports":["TCP/443"],"endpoint":"",
         "reason":"Not installed or production-verified. TCP/443 currently belongs to HTTPS/Nginx; requires a separately verified public IP or an approved non-disruptive Layer-4 SNI architecture.",
         "delivery":"Blocked until dedicated SSTP runtime, certificate and real Windows UAT"},
        {"id":"l2tp-ipsec","label":"L2TP/IPsec","native_windows":True,"ready":False,
         "ports":["UDP/500","UDP/4500","UDP/1701 inside IPsec"],"endpoint":"",
         "reason":"No managed L2TP/PPP backend exists. IKEv1/transport-mode coexistence with existing IKEv2 must be separately configured and real-tested.",
         "delivery":"Blocked until independent L2TP/PPP auth, IPsec-only policy, quotas and real Windows UAT"},
    ],"note":"Only readiness=true represents a configured runtime; creating a Windows profile alone never creates a VPN server."}
