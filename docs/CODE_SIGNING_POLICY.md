# Code signing policy

Status: proposed, not activated. SignPath Foundation approval is pending. No
production signing credentials or release-publishing permission are configured
by this change. Do not describe this project as signed or Foundation-approved.

## Scope

Requested Windows scope is our `couchside-agent.exe` and own Inno Setup
`CouchsideSetup.exe`, built from reviewed source. Computer Connect's own
`CouchsideComputerConnect.exe` would require a separately approved artifact scope.
No paid mobile-app code, upstream ViGEm driver, third-party DLL or Python
interpreter is submitted for individual signing. Embedded dependencies retain
their licenses. SignPath must approve the exact artifact configuration and
source/build provenance before requests are enabled.

## Roles and source controls

Taylor Emery (`emerytech`) is the maintainer and proposed signing approver.
The proposed human reviewer is `ets3d` (the maintainer's wife). Repository write access for `ets3d` has been accepted and verified. Her own MFA verification and actual approving review remain required. Automation/LLMs do
not count as human approval. Signing stays disabled until roles are accepted.
Changes to release source, build scripts, policies and trusted update keys must
use a pull request with passing Windows tests and human review. Protected main
must reject direct pushes, force pushes and deletion; administrators are subject
to the same checks. MFA is required on GitHub and SignPath; each human must
verify their own account rather than treating repository protection as MFA proof.

## Privacy and dependencies

Computer Connect transfers input or requests snapshots only when chosen by the
operator, to the selected PC. No analytics, automatic clipboard synchronization
or cloud relay is included. The agent has other optional operator-configured
features; review its exact configuration and dependency behavior separately.
Pairing uses a shared agent token, not per-client scopes; local Forget does not
revoke the agent token. Legacy HTTP agent routes still exist. See README and
SECURITY.md; do not port-forward the agent or run it elevated.

## Release attestation

A valid Foundation certificate alone is not a Couchside identity. The updater
also requires canonical `CouchsideRelease.json` and its base64 Ed25519 signature
`CouchsideRelease.json.sig`, verified with the public key compiled into the agent.
The document binds schema, repository, stable tag/version, installer filename,
and SHA-256 of the FINAL Authenticode-signed installer. Unknown fields, malformed
bytes, missing signatures, wrong keys and mismatches fail closed. Source URLs,
monotonic stable version checks, checksum, Authenticode, product/version and the
pre-execution supervisor digest check remain mandatory.

The signing key is never read from a release, network, environment override or
CI secret. Keep the private key on a controlled signing workstation, back it up
securely, and verify its public fingerprint independently before approval. Key
rotation requires a reviewed agent build; do not silently swap verification keys.
An initial restricted local key has been generated for review; it is NOT evidence
of approved key custody or disaster recovery. Neither is claimed complete yet.

After approval: build and Authenticode-sign the final installer; verify its chain,
timestamp, metadata and source provenance on Windows; move final bytes/digest to
the controlled signing workstation; invoke `tools/sign_release_manifest.py`;
independently verify the attestation and exact bytes. Publish all four assets
(installer, checksum, manifest, signature) only after human release approval.
Never sign a manifest over an unsigned installer and then modify those bytes.

## Gates before activation

- SignPath eligibility and exact executable/installer scope approval.
- Named human reviewer/approver, MFA verification, protected source/build origin.
- Reconcile agent snapshot with the canonical Windows installer repository;
  apply the manifest verifier there before any production signed build.
- Build exact candidate; inventory shipped binaries, versions, hashes, licenses
  and provenance. Review retired ViGEm paths separately from driver-free input.
- Custody, backup/recovery and fingerprint approval for the project key.
- Genuine signed N-to-N+1 Windows upgrade, unrelated Foundation-signed file
  rejection, retained settings, failed-update cleanup and uninstall checks.
- Explicit permission to publish a binary preview/release. Source-only publication
  does not establish SignPath's released-in-the-form-to-be-signed requirement.

Until these are met, no production signing, auto-update activation or public
binary release is authorized by these preparations.
