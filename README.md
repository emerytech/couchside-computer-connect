# Couchside Computer Connect

A free MIT desktop utility for controlling a Windows PC through its Couchside
agent. Fresh implementation, separate from the PolyForm mobile app. No purchase,
account, subscription, mobile app or ViGEm controller driver is required by this
client's input-only workflow.

The look follows Couchside's Midnight palette, blue accent, rounded Reactor-style
cards, Space Mono headings and MIT brand assets. The phone app is unchanged.

## What works in this preview

- Scan for Couchside boxes, select a PC, compare its identity and enter its six-digit PIN. Manual address entry remains available.
- Opt-in live desktop snapshots, about one frame per second; no disk image cache.
- Trackpad-style pointer control, clicks, right-click, scrolling, drag hold,
  Unicode text and the existing agent's supported special keys.
- Ask the current controller holder for consent, pass/keep/release control.
  Leaving the app or minimizing releases the session; reconnect is deliberate.
- List and launch the PC's existing allowlisted launchers. The client cannot
  create commands, launch arbitrary paths or trigger agent self-updates.
- Optional user-scoped Windows DPAPI pairing storage. On macOS, pairing stays in
  process memory only. Local Forget does not revoke the agent-wide token.

This is **not a full video-streaming remote desktop**: there is no audio, video
codec stream, clipboard synchronization, file transfer, unattended login, Internet
relay, discovery browser or automatic connection. Screens are snapshots and may
lag. Pointer movement is through the separate trackpad, not clicking the image.
Windows lock/secure desktops and higher-integrity windows retain the agent's
existing input restrictions.

## Required agent

The matching experimental Windows agent source is included at
`agent/win/couchsided-win.py`. This is a source preview, not an agent installer. Production agents without
`caps.input_only: true` are refused; no virtual-pad fallback is attempted. The
portable client does not install, update or replace the agent. Linux input-only
mode is not supported by this preview. A client build is not a release or
SignPath eligibility approval.

## Pair securely

1. Run the portable client on the controlling computer. The target should be
   a different computer; do not control the same desktop running the client.
2. Click **Scan for boxes**, choose your PC and **Start secure pairing**. Scan
   uses the agent's existing LAN UDP discovery protocol, not a subnet sweep.
   Broadcasts may not cross VPNs/VLANs; use **Enter an address manually** there
   with the target address and encrypted TLS port (normally 8788).
3. Compare the **PC identity** on the target PC's PIN screen with Computer
   Connect. Check **PC identity matches**, enter the target's PIN and click
   **Confirm PIN**. Discovery is only a hint: the client sends no PIN or token
   until the user confirms the matching certificate identity. The identity is
   the first 128 bits of the SHA-256 certificate fingerprint. Full `fp` is also
   available on the target PC at `http://localhost:8787/api/tls/cert` for advanced
   verification. Computer Connect requires the updated on-PC identity display;
   the normal mobile PIN page is unchanged.
4. Choose whether to enable **Live preview** and **Request control**. An existing
   holder must grant the request; this client offers no force-takeover button.
5. Click/focus the trackpad to type. Drag locally to move the remote pointer, tap
   to click, or use right-click/wheel. **Hold left to drag** latches the remote
   left button until cleared or control is released. **Send text** sends only the
   text deliberately entered in that field; the system clipboard is not automatically read or synchronized. The six PIN boxes support explicit code paste, automatic digit advance and Backspace navigation.

A changed certificate blocks an existing pairing. Verify replacements directly on
the PC. Never confirm a mismatched identity, or trust a new fingerprint only
because a scan or network response supplied it.
All HTTP and WebSocket client requests use pinned TLS; there is no plaintext
fallback, redirect following, analytics or cloud service. Existing legacy agent
HTTP behavior is not changed. Keep the agent on a trusted LAN/VPN and do not
port-forward it. Screen content is sensitive: preview starts off, stays in memory
and clears on disconnect/error; no screenshots or recordings are saved by the
client.

The current agent uses a shared bearer token, not per-client scopes. Forgetting
locally deletes this client's saved credential only. Revoke/rotate the token on
the PC to revoke other copies. Remembered Windows credentials are bound to the
host, port and certificate inside user-scoped DPAPI ciphertext.

## Build or run from source

Python 3.12 with Tkinter is required. Runtime dependencies are hash-locked.

```powershell
cd computer-connect
py -3.12 -m venv .build-venv
.build-venv\Scripts\python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.build-venv\Scripts\python run_connect.py
```

On Windows, `powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1`
produces `dist/CouchsideComputerConnect.exe`, a checksum and accompanying notices.
The script creates a private build venv, verifies locked dependencies and runs
PyInstaller. It does not sign, publish, install the agent or change firewall rules.
The preview executable is unsigned. Keep the notices with the binary. Source
platform support is experimental on macOS; its pairing is memory-only.

Tests from the repository root:

```text
python -m pip install --require-hashes --only-binary=:all: -r computer-connect/requirements.lock
python -m pip install cryptography==46.0.7
python tests/test_computer_connect.py
python tests/test_win_input_only.py
```

The first suite exercises real HTTPS/WSS with temporary agent fixtures, pin
failure before credentials, pairing, bounds, refusal, handoff and credential
storage behavior. It does not install a service, send production credentials or
operate personal files. Native Windows input and packaged UI checks are separate
acceptance work; see the local validation report delivered with a tested build.

## Provenance and license

Entirely LLM-coded integration to make this workflow quick to try. Review and
validate before relying on it; assistance does not imply security certification.
Own client source: MIT. Third-party libraries retain their own licenses. See
`LICENSE`, `THIRD_PARTY.md` and `licenses/` in the portable distribution. The
Space Mono font is SIL OFL, registered only for this process, not installed into
system fonts. Client source contains no mobile-app implementation, private
credentials, game data or proprietary DLLs.

Private macOS preview: build with `python -m PyInstaller computer-connect/macos.spec` from the repository root. The bundle declares local-network discovery use. Scan retransmits bounded UDP probes to tolerate packet loss; local-network access must be allowed by macOS. Connection → Choose a PC and Control → Mouse provide native menu access alongside the existing widgets. Windows screen capture temporarily uses a per-thread physical-pixel DPI context and restores it, preserving the rest of the agent UI.

## Open-source scope and provenance

This repository contains the independent Computer Connect client and a snapshot
of the MIT Couchside Windows agent. Client and agent source were extracted from
[emerytech/couchside](https://github.com/emerytech/couchside) commit
`788c02f` (development branch). The paid mobile application is not included.
MIT applies to our source; bundled fonts and third-party dependencies retain
their own licenses. See [THIRD_PARTY.md](computer-connect/THIRD_PARTY.md).

This project was developed with extensive LLM assistance. It is an experimental
community source preview; review and test it before relying on remote access.
No SignPath eligibility or code-signing approval is claimed.

The included agent must run as the ordinary signed-in Windows desktop user,
not an elevated process or session-0 service. Its `--help` describes configuration,
token-file, TLS-directory and port overrides. It requires `cryptography` for TLS.
Do not run a second agent on the installed agent's ports or point it at existing
configuration/token files. This repository does not install an agent, change
firewall rules, include ViGEm, or supply a production deployment/update path.
Optional mobile QR-code rendering is absent from this snapshot; Computer Connect
uses the on-PC PIN/identity display instead.

### Validation status

Private Mac packaged-client tests against an isolated, ordinary-user Windows
agent verified discovery/selection, six-digit PIN pairing, full-desktop snapshots,
text, mouse movement, left/right clicks, scrolling, and disconnect release.
Mouse events were verified via native menu commands; Tk trackpad event bindings
were tested separately. Windows core tests, DPAPI, JPEG encoding and PIN widget
checks passed. These results are not public CI or a released binary certification.
No signed installer, binary release, internet relay, audio/video streaming, or
unattended login is supplied.
