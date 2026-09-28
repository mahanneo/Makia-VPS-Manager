# Makia 0.26.0-rc4 — Xray/OpenVPN Real VPS UAT

RC4 is not Stable until this checklist passes on the real VPS.

## Xray listener regression
1. Upgrade the existing RC3 host to RC4.
2. Create VLESS/TCP/NONE on three different unused high ports.
3. Create VMess/WS/NONE on one unused port.
4. For each creation confirm the panel succeeds, Xray stays active and `ss -lntup` shows the requested listener.
5. Import at least one generated profile into a real client and pass HTTP/HTTPS traffic.
6. Intentionally choose a genuinely occupied port and confirm Makia rejects it before mutation.

## OpenVPN client actions
1. Open the OpenVPN workspace.
2. Click `...` on an existing client directly from that page.
3. Confirm the detail drawer opens.
4. Download `OVPN`, import it into OpenVPN Connect and connect.
5. Download Protected ZIP and verify it opens with the selected password.
6. Open the client connection guide.
7. Refresh the page and repeat the `...` workflow to confirm cache independence.

## Migration regression
Verify the previous RC2 Full Migration backup still passes Verify & Preview on RC4 through the supported compatibility path.

## Stable gate
Do not promote to Stable until the above tests and inside-Iran client connectivity checks pass.
