# Dependency and artifact review

This is a source inventory, not a completed binary SBOM. Generate the exact
installed-package/license inventory with `computer-connect/tools/collect_notices.py`
in the isolated build environment. Keep `dist/dependencies.json`, `dist/licenses/`
and SHA-256 sums beside every reviewed portable candidate.

| Component | Version/source | License | Treatment |
|---|---|---|---|
| Computer Connect and included Windows agent | repository commit | MIT | Own maintained source |
| Python | 3.12 build environment | PSF | Inventory exact build; retain notices |
| Tcl/Tk | Python's bundled build | Tcl/Tk | Inventory exact DLLs/notices |
| websocket-client | 1.9.2 runtime lock | Apache-2.0 | Hash-locked wheels |
| Pillow | 13.0.0 runtime lock | MIT-CMU / bundled libraries | Keep collected bundled-library notices |
| PyInstaller | 6.22.3 build lock | GPL + bootloader exception | Not a relicensing of dependencies |
| cryptography | 46.0.7 test environment | Apache-2.0 OR BSD-3-Clause | Agent TLS/manifest verification; inventory actual packaged version |
| Space Mono | included asset | OFL-1.1 | Preserve included OFL |
| Couchside brand images | source MIT brand assets | MIT | Included with client |
| ViGEmClient / ViGEmBus | absent from client source package | MIT / BSD-3-Clause | Retired; do not re-sign; exact agent installer payload still needs inventory |

No installer, driver, game assets, private key or SignPath credential is included
in this source repository. The input-only client never creates a ViGEm device;
this does not mean the full agent's gamepad features are driver-free. Optional
mobile QR encoder is not shipped in this snapshot. The canonical Windows release
repository's installer/build chain must be reviewed, not inferred from this client
snapshot. No exact shipped-binary provenance is claimed before that build exists.
