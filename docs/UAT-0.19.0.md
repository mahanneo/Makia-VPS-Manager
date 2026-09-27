# Makia 0.19.0 — WireGuard host acceptance

Upgrade an existing installation with `sudo makia-upgrade`. Confirm `cat /opt/makia-vps-manager/VERSION` reports `0.19.0`. Keep the updater's backup. Existing `wg0` keys and client profiles should remain unchanged.

1. Run `sudo makia-doctor` and `sudo makia-uat-smoke`. In Protocol Hub, inspect WireGuard Diagnostics. Verify `wg-quick@wg0` is active, the UDP listener uses the configured port, IPv4 forwarding is enabled and FORWARD/NAT checks pass.
2. In the WireGuard menu, create one peer using the public IPv4. Export its `.conf`, import it in a client outside the VPS, activate it and verify a recent handshake plus RX/TX counters in the peer list. Visit an external site through the tunnel.
3. Create a second peer using a direct DNS-only hostname whose A record points to the same public IPv4. If an AAAA record exists, it must route to the VPS too. Test handshake, traffic and internet reachability again from outside the VPS. A CDN/proxied hostname cannot carry ordinary WireGuard UDP.
4. Disable the second peer. Its status must change, the server must reject its traffic, and `wg show wg0` must omit its public key. Restart `wg-quick@wg0`; the peer must remain disabled. Re-enable it, verify it reconnects with the original imported profile and check that no address is reused while disabled.
5. Change the endpoint of a saved peer, re-export the profile and import the updated profile in the client. Confirm that the public key and tunnel address remain the same. Delete a test peer and check that it disappears from `wg show wg0` and the panel.
6. On a narrow screen, open the menu, visit WireGuard, create and export a test profile, then close the menu. Confirm no controls are covered or clipped.

If a client cannot handshake, compare the selected endpoint and DNS A/AAAA records with the real VPS addresses, the UDP port in its profile with `wg show wg0 listen-port`, upstream provider firewall rules, and `sudo journalctl -u wg-quick@wg0 -n 100 --no-pager`. A green server-side diagnostic does not prove external UDP reachability. Record the client network and time of the attempt before changing the server configuration.
