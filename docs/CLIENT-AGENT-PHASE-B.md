# Makia Client Agent — Phase B

Status: development branch only  
Branch: `feat/v1.3-client-agent-phase-b`  
Depends on: `feat/v1.3-client-control-plane-phase-a`  
Production activation: **not permitted**

## Objective

Add the cryptographic device/Agent layer that sits between the Makia Client PWA and native tunnel engines without changing the VPS protocol runtime.

Phase B enables one real native adapter only: **WireGuard on Windows**. Other protocol cards remain assigned/visible but cannot receive executable Agent grants.

## Security model

### Device key

The Agent creates an Ed25519 key pair locally.

- Private key stays on the end-user device.
- Only the public key is registered with the Makia control plane.
- The device row records Agent version/platform and pairing time.

### Pairing

The authenticated PWA requests a one-time `mkp_` token.

- TTL: 5 minutes.
- Database stores SHA256(token), never the raw token.
- Token is bound to account + browser device.
- Pair endpoint validates the linked device/account policy.
- Token becomes unusable after the first successful pair.

Deep link:

```text
makia://pair?server=https%3A%2F%2Fclient.example&token=mkp_...
```

### Connect grant

The authenticated PWA requests a `mkg_` grant for an assigned access binding.

- TTL: 60 seconds.
- Only WireGuard bindings are accepted in Phase B.
- Database stores SHA256(token).
- Grant is bound to account + device + binding + action.
- Browser receives no decrypted WireGuard configuration.

Deep link:

```text
makia://connect?server=https%3A%2F%2Fclient.example&grant=mkg_...
```

### Agent redeem

The Agent signs:

```text
makia-agent-v1
<grant>
<nonce>
<unix timestamp>
```

with the paired Ed25519 private key.

Server checks:
- feature flag
- grant not expired/redeemed
- timestamp within 90 seconds
- device active and paired
- access binding active
- account/profile enabled and not expired
- Ed25519 signature

The grant is atomically marked redeemed before decrypted artifact delivery.

## Windows Agent

Source:
- `client-agent/go.mod`
- `client-agent/main.go`
- `client-agent/main_test.go`
- `client-agent/README.md`

Agent behavior:
- `install` copies the executable to the current user's local application directory.
- Registers `makia://` under HKCU, so install does not mutate the VPS.
- Requires HTTPS control-plane URL except localhost development.
- WireGuard profile is written only to a temporary private directory.
- Official `wireguard.exe /installtunnelservice` is invoked through Windows UAC.
- Temporary profile material is deleted when the install command returns.

## Non-WireGuard protocols

OpenVPN, Xray, SSH/NPV and Outline do **not** receive action grants in this phase.

This is deliberate. Each adapter must have:
- native process lifecycle design
- kill/cleanup semantics
- credential-at-rest rules
- DNS/routing behavior
- upgrade behavior
- Windows UAT

before enablement.

## Production safety

Phase A and Phase B remain on development branches.

The production panel:
- stays on the current stable main release
- keeps `MAKIA_CLIENT_APP_ENABLED=0`
- receives no Client Agent binary
- receives no WireGuard peer changes
- receives no service restart because of these branches

## CI gates

Phase B requires:
- all existing Python/unit/release gates
- Phase A safety tests
- signed Agent pairing/grant tests
- JavaScript syntax
- browser smoke
- Xray core smoke
- Go unit tests
- `go vet`
- Windows amd64 cross-build
- source boundary guard preventing VPS command paths in Agent Go source

## Staging promotion sequence

1. Merge Phase A only after review.
2. Deploy to isolated staging with feature flag still OFF.
3. Enable client app only on staging.
4. Create a test client/profile/access binding.
5. Validate browser login/device/session limits.
6. Install a test Windows Agent.
7. Pair Agent and verify Ed25519 registration.
8. Request/redeem one WireGuard grant.
9. Verify Windows tunnel starts/stops cleanly.
10. Verify no existing VPS protocol credential changed.
11. Only then discuss production release/version bump.
