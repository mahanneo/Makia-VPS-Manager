# Makia Client Agent — Phase B

This directory is isolated from the VPS runtime. The agent runs on the **end-user Windows device**, not on the Makia server.

## Current Phase B capabilities

- Registers the `makia://` URI scheme for the current Windows user.
- Installs a stable copy under the current user's `LOCALAPPDATA\MakiaClient` directory.
- Generates an Ed25519 device key pair locally.
- Pairs only the public key to the browser-registered Makia device using a 5-minute one-time grant.
- Redeems 60-second connect grants with a fresh nonce, timestamp and Ed25519 signature.
- Receives a WireGuard native profile only after the server validates account, device, binding, expiry and signature.
- Uses a temporary profile file and deletes it after the WireGuard service-install command completes.
- Invokes the official WireGuard for Windows executable with `/installtunnelservice`; Windows may show a UAC prompt.

## Security properties

- The private device key never leaves the end-user device.
- Pairing and action grants are one-time; the server stores only SHA256 token hashes.
- The browser never receives decrypted protocol credentials through the Agent grant flow.
- Connect grants are bound to account + device + assigned access.
- Control-plane URLs must use HTTPS. Plain HTTP is accepted only for localhost development.
- The Agent does not print grant tokens or private keys.
- Phase B server grants are intentionally limited to **WireGuard** until the other native adapters pass their own UATs.

## Build

```bash
cd client-agent
go test ./...
go vet ./...
go build ./...
```

Windows release build:

```bash
GOOS=windows GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o makia-client-agent.exe .
```

## Install on Windows

Run once as the target user:

```powershell
.\makia-client-agent.exe install
```

The binary copies itself into the user's local application directory and registers `makia://` under HKCU.

## Pairing

From the Makia Client PWA, press **Pair Agent**. The browser receives only a short-lived pairing deep link. The Agent exchanges that one-time token for registration of its Ed25519 public key.

## Connect flow

1. User presses Connect on an assigned WireGuard access.
2. PWA requests a 60-second action grant.
3. PWA opens `makia://connect?...&grant=...`.
4. Agent signs the grant with the paired private device key.
5. Server atomically redeems the one-time grant and returns the native WireGuard profile.
6. Agent writes the profile to a temporary private directory.
7. Windows WireGuard installs the tunnel service.
8. Temporary profile material is removed.

## Deliberate boundary

OpenVPN, Xray, SSH/NPV and Outline are not automatically started in this phase. Their browser cards remain assigned/visible, but the control plane refuses native action grants until each adapter has an independent security and UAT gate.

No code in this directory is installed or executed on the VPS by the current Makia install/update scripts.
