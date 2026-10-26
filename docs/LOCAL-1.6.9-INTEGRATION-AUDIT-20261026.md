# Makia 1.6.9 production-source integration (staging ONLY) — 2026-10-26

Base: GitHub integration PR #127, commit b656d5079dc480cb8ea2f1145262adaed225fa87.
Destination: local review directory, NOT live /opt/makia-vps-manager.
Live server is 1.6.9 (2026-10-24); public main is 1.6.5.

## Ported into staging
- Nine edited app files from production 1.6.9, including native IKEv2/L2TP and 26.10.21 Xray handling
- Seven original 1.6.9 regression suites
- Updated stale historical tests for revised asset cache key, mkcp network schema and added L2TP mode
- Explicit immutable upstream Xray installer commit from PR #126 restored, with tmp file cleanup and argv safety

## Evidence
- No DB, .secret, environment credentials, certificates or client data copied into this Git clone
- Compiled Python source and JavaScript syntax passed; git diff --check clean
- 535 of 545 full-suite tests passed before installer hardening; 10 failures remained, including installer test
- 13 focused installer/transport/ALPN tests passed after installer hardening
- No production service stop/restart, VPN user mutation, database migration, firewall or port change made

## Release blockers
- Rerun full suite after installer fix and triage remaining failures rather than weakening relevant invariants
- Verify live 1.6.9 installer compatibility with pinned installer release in disposable Ubuntu (not live)
- Confirm Xray 26.10.21 compatibility by independent full clean install/upgrade CI
- Resolve test failures arising from version 1.6.5 release contract vs newer 1.6.9 and removed method field
- Fix isolated test DB setup for Xray preset readiness so it does not access production SQLite
- Review Outline guide regression and XHTTP lab-only gate; preserve verified safety behavior
- Validate active VPN protocol config and real browser/Windows/Android client egress on staging
- Verify encrypted off-host backup, credentials, rollback, explicit maintenance window before live deployment
- Security review and code scan mandatory before considering GitHub PR

This is a local checkpoint, not an official 1.6.10 release.
