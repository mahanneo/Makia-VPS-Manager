# Makia VPS Manager v1.2.7 — DNS-over-TLS Repair / Update Recovery UAT

Date: 2026-09-29
Target: `1.2.7`

## Root cause

The resolver configuration enabled `forward-tls-upstream: yes` and used authenticated upstream names such as `1.1.1.1@853#cloudflare-dns.com`, but did not declare a CA bundle. Unbound requires a CA bundle (or equivalent system trust configuration) to authenticate TLS upstream certificates. The service could therefore remain active while localhost queries failed.

The updater then treated that pre-existing optional DNS query failure as a fatal host-smoke regression and rolled the whole panel release back to the previous version.

## Fix

- Adds `tls-cert-bundle: "/etc/ssl/certs/ca-certificates.crt"` to both installer-generated and panel-generated Unbound configs.
- DNS configure now requires a successful localhost A-query before accepting the new config.
- DNS status reports `query_ok`, query latency and bounded runtime diagnostics.
- Updater records whether DNS answered before the update.
- A pre-existing broken resolver is rebuilt transactionally with the current DoT contract.
- Successful DNS repair promotes the repaired config/state hashes to the accepted update baseline.
- Failed DNS repair restores the original hashes and does not roll back the core panel release.
- Post-update smoke soft-fails DNS query only when that resolver was already broken before the update; direct `makia-uat-smoke` remains strict.
- Retains v1.2.6 MTProxy transaction repair, v1.2.5 shared permission contract, AUTO MTProxy port selection and force-main recovery.

## Host acceptance

- [ ] Run latest main updater with `MAKIA_FORCE_MAIN=1`.
- [ ] Confirm installed and running version are 1.2.7.
- [ ] Confirm `grep tls-cert-bundle /etc/unbound/unbound.conf.d/makia.conf` returns the system CA bundle path.
- [ ] Confirm `unbound-checkconf` passes.
- [ ] Confirm `dig @127.0.0.1 example.com A +short +time=3 +tries=1` returns at least one IPv4 address.
- [ ] Confirm `sudo makia-uat-smoke` passes the DNS query gate.
- [ ] Open DNS Center and verify Resolver query shows latency instead of FAILED.
- [ ] Verify MTProxy remains ACTIVE and its link/port are unchanged by this DNS repair.

## Promotion rule

CI must pass test, browser-smoke and xray-core-smoke. Real host DoT reachability remains a production UAT item because some providers can block outbound TCP/853.
