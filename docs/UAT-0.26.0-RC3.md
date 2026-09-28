# Makia 0.26.0-rc3 — Real VPS UAT

RC3 is **not Stable**. Complete these checks on the real Ubuntu VPS and from at least one client inside Iran.

## 1. Upgrade safety
1. Take a Full Migration Backup before upgrade.
2. Run the normal Makia updater.
3. Confirm existing SSH, Xray, WireGuard and OpenVPN identities are unchanged.
4. Run `makia-doctor` and `makia-uat-smoke`.

## 2. Xray Manual / Expert Builder
Create separate test profiles using unused ports:
- VLESS / TCP / NONE on a public IP endpoint.
- VLESS / WS / NONE.
- VMess / TCP / NONE.
- VMess / WS / NONE.
- VLESS / TCP / REALITY.
- VLESS or VMess / TLS only after a valid certificate exists.

For each profile verify:
- Xray Core validation passes.
- Xray service stays active.
- The requested listener appears on the host.
- QR/share link imports into the intended client.
- DNS resolves through the tunnel.
- A real HTTP/HTTPS request passes traffic.
- RX/TX accounting changes where supported.
- Disconnect/reconnect works.

Do not interpret `security=none` as encrypted transport. It is intentionally available because Manual mode gives the operator control.

## 3. Advanced JSON
Open Xray Advanced JSON, Validate without applying, then apply a harmless validated change and confirm automatic backup/rollback behavior remains functional.

## 4. Full Migration Backup regression
Create a new Full Migration Backup and verify its ZIP contains:
`payload/systemd/makia-migration-restore@.service`

Also retry the RC2 backup that previously failed with:
`bundle payload missing: payload/systemd/makia-migration-restore@.service`

Expected: Verify & Preview succeeds through the legacy-name compatibility path.

## 5. Replacement VPS restore
1. Install exactly Makia 0.26.0-rc3 on a clean supported Ubuntu VPS.
2. Confirm the installer prints Panel URL, Username and Password in the final box.
3. Confirm `/root/makia-install-credentials.txt` exists with mode 0600.
4. Upload the encrypted migration backup.
5. Verify integrity/version preview.
6. Restore.
7. Verify Xray, WireGuard, OpenVPN UDP/TCP, IKEv2, Stealth, WStunnel and Makia services.
8. Change the Cloudflare DNS-only A record to the replacement VPS only after runtime checks pass.
9. Confirm old domain-based client configs reconnect unchanged.

Literal-IP profiles must be re-exported after the server IP changes.

## 6. Inside-Iran field gate
From at least one Iranian ISP/mobile network test every mode intended for publication. Record client, network, handshake, DNS, routed traffic, reconnect and 10+ minute stability.

Only after these real-host and real-client checks pass may a Stable promotion be considered.
