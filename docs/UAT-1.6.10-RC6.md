# Makia VPS Manager 1.6.10-rc6 — France Host UAT

Date: 2026-10-31
Target: France VPS 155.117.5.236
Panel: p.mahinet.shop
Status: Release candidate; not Stable.

## Code and automated tests

- [x] Installed application source copied into the release worktree without replacing the existing repository documentation/client packages.
- [x] Axon dashboard, landing page, login assets and expanded protocol operations preserved.
- [x] MTProxy hostname-save regression added; status returns the configured public IPv4; UI verifies the saved hostname and explains same-domain/IP migrations.
- [x] Service-worker cache revision advanced to v175.
- [x] 578 pytest tests pass.
- [x] Python compile, Bash syntax, JavaScript syntax pass.
- [x] Browser extension verified-egress contract: 16 scenario groups pass.
- [x] mtg 2.2.8 release smoke passes.
- [x] WStunnel 11.0.0 installer/flag smoke passes.

## France server-side checks

- [x] makia-uat-smoke: 34 PASS / 1 WARN / 0 FAIL.
- [x] makia-doctor: 34 PASS / 1 WARN / 0 FAIL.
- [x] Nginx config valid; HTTPS and panel health endpoint pass.
- [x] Xray active config validates; 11 inbounds present.
- [x] WireGuard runtime/forwarding/NAT/listener ready.
- [x] OpenVPN runtime active on UDP/1194; TCP fallback active on TCP/8443.
- [x] IKEv2/strongSwan runtime and UDP/500/4500 listeners active.
- [x] L2TP service ready.
- [x] SSTP backend ready; TCP/14443 listener active.
- [x] WStunnel and OpenVPN WStunnel 443 route active.
- [x] TUIC/Hysteria2 configs validate; TLS certificates valid; UDP listeners and one existing user each are present.
- [x] MTProxy active on TCP/10443; mtg doctor passes Telegram DC/front-domain checks.
- [x] DNS resolver active and answers local query.
- [x] MahiNet storefront/worker and Outline Shadowbox containers running.

## External client tests performed

- [x] From Germany, p.mahinet.shop resolved directly to France IPv4 155.117.5.236.
- [x] Temporary TUIC client over UDP/8445 completed HTTPS egress; observed exit IP 155.117.5.236.
- [x] Temporary Hysteria2 client over UDP/8446 completed HTTPS egress; observed exit IP 155.117.5.236.
- [x] Temporary test users, client configs, client logs and transfer key were removed after tests; existing TUIC/Hysteria2 users remain (one each).
- [x] From Germany, TCP/10443 on France was reachable.

## Warnings observed

- [ ] Stealth uses the legacy global stunnel4 process; active listener is preserved but the panel's dedicated service ownership is not migrated. Do not stop it until its other listener/client dependencies are audited.
- [ ] Client Portal is enabled; operator must confirm this is intentional.
- [ ] UFW is inactive; provider firewall and host firewall hardening require a separate tested rollback plan.

## Required before Stable

- [ ] Real Telegram phone/desktop client connects using the current MTProxy link.
- [ ] Windows native SSTP client completes connection; specifically retest the previous RasClient error 720.
- [ ] Android client demonstrates post-DNS-change internet egress.
- [ ] Test the intended protocol set from the actual user networks/ISPs, especially inside Iran.
- [ ] Create an encrypted off-host backup and perform a restore/rollback rehearsal on a disposable VPS.
- [ ] Confirm the legacy Stunnel ownership plan and Client Portal exposure.
- [ ] Run GitHub Actions on the exact frozen release commit; promote that exact SHA to main only after the above gates pass.

The Germany VPS remains the rollback source and must not be deleted before these gates pass.
