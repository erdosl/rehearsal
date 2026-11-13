# Read-only Proxmox inventory

Rehearsal **0.2.0 is deployed on `rehearsal01` at 192.168.56.83/24**. Real read-only inventory passed on **2026-11-12 at 12:05:51 UTC**, running as the unprivileged `rehearsal` account. Development remains on `dev01`; no application-code or wheel change was needed. The controller's placement directly in VirtualBox outside PVE is user-supplied.

The authorised bootstrap created only the runtime account/directories, venv prerequisite/packages, application-specific CA/configuration, and dedicated PVE audit identity/token/ACLs. It preserved unrelated state. PVE certificates, system trust, hostname mappings, VM/template/storage/network configuration, runners and backups were not changed. No persistent Rehearsal service was installed. Earlier certificate inspection timeouts were resolved; some ancillary SSH connections still timed out between successful sessions, so connectivity should be rechecked for later unattended work.

The later [nested Ubuntu guest/template preparation](nested-guest.md) is a proposal only and keeps this inventory token, its scopes and credential file unchanged. Additional mutation privileges belong to a separate future identity. The [controlled controller reboot-validation procedure](controller-reboot.md) covers pre/post release/config/credential metadata and a real live CLI run; it has not been executed and expects no daemon.

## Operations and visibility

The adapter issues only these requests, serially, against the configured HTTPS origin. It does not query arbitrary nodes, follow redirects, use SSH as a backend, load VM configuration/guest secrets, or fall back to fixtures.

| Request under `/api2/json` | Purpose | PVE 9.2.2 permission behaviour |
| --- | --- | --- |
| `GET /version` | API version | Authenticated caller (`user => all`) |
| `GET /nodes/{node}/status` | CPU count and total memory; evidence the node API answered | `Sys.Audit` on `/nodes/{node}` |
| `GET /nodes/{node}/storage` | Visible storage type/content, activity and byte capacities | Filters entries by `Datastore.Audit` **or** `Datastore.AllocateSpace` on `/storage/{storage}`; use audit only |
| `GET /nodes/{node}/qemu` | Visible QEMU VM/template IDs, names and status | Filters entries by `VM.Audit` on `/vms/{vmid}` |
| `GET /nodes/{node}/network` | Interface/bridge metadata, configured IPv4/IPv6 CIDRs and ports | Method accepts authenticated callers, but its body filters bridges/VNets by SDN rights. For local `vmbr0`, grant **`SDN.Audit` on `/sdn/zones/localnetwork/vmbr0`**; do not substitute `SDN.Use` |

These declarations and filters were inspected in the **installed official PVE packages** on `pve01`: `pve-manager` 9.2.2, `qemu-server` 9.1.15 and `libpve-storage-perl` 9.1.5. Sources were `/usr/share/perl5/PVE/API2.pm`, `PVE/API2/Nodes.pm`, `PVE/API2/Network.pm`, `PVE/API2/Storage/Status.pm` and `PVE/API2/Qemu.pm`. The installed `pve-docs` 9.2.1 user-management documentation was also checked. This version-specific evidence complements the [official API viewer](https://pve.proxmox.com/pve-docs/api-viewer/index.html), [upstream node API source](https://github.com/proxmox/pve-manager/blob/master/PVE/API2/Nodes.pm) and [official user-management source](https://github.com/proxmox/pve-docs/blob/master/pveum.adoc). Recheck after a PVE upgrade.

The real deployment corrected an omission in the initial method-header review: installed `Network.pm` always checks bridge access through `RPCEnvironment.pm::check_sdn_bridge`, using `/sdn/zones/{zone}/{bridge}`. The initial successful query omitted `vmbr0`; the scoped audit grant made it visible in the final run. Other bridges or SDN fabrics need their own applicable audit scopes if they are to be included. The existing release was not modified; its general visibility note names storage/VM filtering, and this runbook documents the additional network filtering.

Inventory covers the configured nodes and credential-visible QEMU resources, not LXC containers or complete guest configuration. Network addresses describe configured interface metadata; they are not a routing/connectivity test or proof of runtime DHCP addressing. Storage status does not expose all backing-disk, thin-metadata or physical-host health needed for provisioning.

`complete: true` means **all requested endpoint queries succeeded and parsed**. It does not mean unfiltered visibility. Storage, VM and bridge lists can return HTTP 200 while ACLs hide entries. Empty means “no visible entries”, not “no resources exist”; compare effective permissions and, where authorised, a privileged reference read.

## Operator preparation: dedicated read-only token

The following describes the authorised setup used here and the rules for later reruns. Inspect first; do not recreate or rotate a token just because its value is no longer retrievable from PVE.

1. Create a dedicated enabled PVE-realm service user, for example `rehearsal-inventory@pve`. It needs no PAM/root identity, SSH account or sudo access. Avoid administrative roles and unrelated group memberships.
2. Create custom roles containing only the privileges in the table below. Apply them to the service user, or a dedicated group containing that user. Avoid the broader built-in administrative roles.
3. Create a token such as `inventory` for that user with **Privilege Separation enabled**, a bounded expiry and a rotation/revocation procedure. Capture the generated UUID secret once into a protected file; do not copy it into chat, CLI arguments, Git or reports.
4. Apply the corresponding ACLs explicitly to the token principal `rehearsal-inventory@pve!inventory` as well. A privilege-separated token receives the **intersection** of the owner's rights and its own rights. Owner permissions alone are insufficient; the token cannot exceed its owner. This behaviour was verified in installed documentation and is described by [Proxmox user management](https://github.com/proxmox/pve-docs/blob/master/pveum.adoc).

| Suggested custom role | Privilege | ACL path and propagation | Intended scope |
| --- | --- | --- | --- |
| `RehearsalNodeAudit` | `Sys.Audit` | `/nodes/pve01`, propagation not needed for this exact status check | Required node status query |
| `RehearsalStorageAudit` | `Datastore.Audit` | `/storage/rehearsal-lvm`, propagation not needed for list filtering | Planned template/test storage |
| `RehearsalNetworkAudit` | `SDN.Audit` | `/sdn/zones/localnetwork/vmbr0`, propagation disabled | Visibility of the current management bridge; no network-use/configuration right |
| Same storage role, optional | `Datastore.Audit` | `/storage/local` and `/storage/local-lvm`, each explicitly | Include the existing stores in inventory if desired |
| `RehearsalVMAudit` | `VM.Audit` | `/vms`, **propagate enabled** | Read metadata for all VMs, including future VMIDs; this scope is cluster-wide, not limited by node |
| Alternative VM scope | `VM.Audit` | Individual `/vms/{vmid}` paths, for every permitted VM/template | Smaller scope; undisclosed and future VMIDs remain invisible until ACLs are maintained |

The deployed identity is `rehearsal-inventory@pve`, with token `inventory`. Both have the four mandatory roles above, including propagated `/vms` audit. **The optional `local`/`local-lvm` scopes were not granted.** Token privilege separation is enabled and expiry is **2026-12-12 11:51:04 UTC**. No rotation/renewal automation is installed.

Apply each chosen scope to both owner and token. Do not grant `SDN.Use`, `Datastore.AllocateSpace`, `VM.Allocate`, `VM.PowerMgmt`, `VM.Config.*`, `Sys.Modify`, shell/console permissions or ACL-management rights for inventory. The adapter only requests configured nodes, but that client allowlist is not a substitute for server ACLs. Choose and document the VM scope deliberately; a pool or node ACL does not automatically grant `/vms` audit visibility.

Review effective user/token permissions and test positive and negative scopes before relying on the inventory for planning. Do not assume an empty VM list proves the token has VM audit rights. SSH access and the observed `jgipsz` passwordless sudo policy establish no HTTPS API authorization.

## Certificate trust and endpoint identity

Obtain the **public** CA certificate through an independently authenticated operator channel. An existing pinned, host-key-verified SSH connection can transport `/etc/pve/pve-root-ca.pem` for the default PVE CA, as described in [official certificate management](https://github.com/proxmox/pve-docs/blob/master/certificate-management.adoc); a custom API certificate requires the CA chain that actually issued it. Compare its fingerprint through that trusted channel. Inspect the certificate used by `pveproxy`, including SANs, validity and issuer, before choosing an endpoint. The [official proxy documentation](https://github.com/proxmox/pve-docs/blob/master/pveproxy.adoc) identifies its certificate selection; no certificate-management operation is required by this adapter.

Store the approved public CA as a separate runtime file, for example `/etc/rehearsal/pve-ca.crt`, and reference it through `proxmox.ca_file`. This does not require adding it to the system trust store. Never copy private `.key` files. Do not treat a certificate retrieved over an untrusted HTTPS connection as automatically trusted.

For `https://192.168.56.80:8006`, the server certificate must contain **IP SAN `192.168.56.80`**. If it has only a suitable DNS SAN, use that DNS name in the endpoint and arrange verified name resolution to `.80` on `rehearsal01`. An SSH alias does not create DNS resolution for the API client. The deployed IP endpoint's SAN and chain were verified from the controller as the runtime account. No `/etc/hosts` entry or DNS change was necessary.

The adapter creates an SSL context with required chain verification, hostname checking and SAN-based identity matching; CN fallback is disabled. A configured CA file is loaded explicitly; otherwise Python's default CA discovery applies. HTTPX environment proxy handling and redirects are disabled. There is no insecure verification option. Missing/invalid CA files or trust/identity/negotiation errors are reported as `tls_error` rather than bypassed.

## Runtime secret file

`proxmox.token_file` must reference a regular, non-symlink UTF-8 JSON file outside version control, owned by the account running Rehearsal, with mode **0600 or 0400** and a protected parent directory. The limit is 4 KiB. The shape is:

```json
{"token_id": "rehearsal-inventory@pve!inventory", "token_secret": "<UUID copied securely from PVE>"}
```

This placeholder is not a usable token. Only those two fields are accepted; the secret must be a UUID. The example service identity uses ASCII letters/digits/dots/underscores/hyphens, which the loader validates. Systemd credential delivery is a future option; its generated file can be referenced through the same setting when it meets these ownership/mode requirements. No background service is needed for the current CLI.

Token-file contents are loaded only after both live opt-ins. No token/password CLI argument or token environment variable is supported. Configuration validation never opens credential files. Reports omit identity/header values; reflected token values are scrubbed before export. Error messages do not include HTTP bodies, request objects, raw exceptions or rejected CLI argument values. Do not enable external request-dumping tools or include runtime credential files in deployment/report bundles.

## Deploy independently to rehearsal01

Prerequisites are completion of its installation, a normal runtime account, Python 3.12 with venv support, verified management connectivity to `.80:8006`, correct time, and a package-index or offline wheel delivery path. None is assumed complete merely because `.83` is reserved. Do not depend on `dev01` paths, its SSH configuration or host administration from the application.

Build on `dev01` using the development setup, then deliver the versioned wheel, `requirements-runtime.lock` and optionally the runtime wheel directory through an operator-approved path. Keep credentials/CA delivery separate. In a chosen application directory **on the controller**, installation is:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-runtime.lock
.venv/bin/python -m pip install --no-index --no-deps rehearsal-0.2.0-py3-none-any.whl
```

For offline dependency delivery, add `--no-index --find-links /path/to/runtime-wheels` to the lock installation. The lock targets Python 3.12/Linux x86_64. It includes HTTPX and its transitive dependencies, not pytest/Ruff/build tools. No application service, database or Proxmox SSH privilege is required.

Prepare `/etc/rehearsal/live.toml` from [the live example](../examples/live.toml), with the verified endpoint, approved CA path, protected token path and node allowlist. From the controller's operator account, validate and run as the runtime user:

```bash
sudo -n -u rehearsal /opt/rehearsal/current/venv/bin/rehearsal config validate --config /etc/rehearsal/live.toml --format json
sudo -n -u rehearsal env REHEARSAL_LIVE=1 /opt/rehearsal/current/venv/bin/rehearsal inventory --config /etc/rehearsal/live.toml --backend live --live --format json
```

The deployment executed these application operations under UID 999. Retain output in a protected report location outside the repository using a fresh UTC filename, umask 077 and no-clobber creation. Expect `backend: "live"`, `simulated: false`, successful coverage for each requested section, and check that `rehearsal-lvm` is visible with the intended content types. Check token visibility separately. Exit 4 or failed/skipped coverage is partial evidence, not a clean inventory. The current token has a known expiry; do not interpret a later 401 as permission to rotate it automatically.

## Verified deployment record

Deployment date: **12 November 2026**. The existing 0.2.0 wheel was used unchanged; do not rebuild the same version and assume its digest remains identical to this deployment.

| Location | Purpose / permissions |
| --- | --- |
| `/opt/rehearsal/releases/0.2.0/venv` | Dedicated runtime venv; release tree root:`rehearsal`, base 0750, read-only to the runtime account |
| `/opt/rehearsal/current` | Symlink to that immutable version directory |
| `/opt/rehearsal/releases/0.2.0/artifacts` | Verified wheel, runtime lock, offline dependency wheels and non-secret setup inputs |
| `/opt/rehearsal/releases/0.2.0/bootstrap.json` / `deployment.json` | Release identity/digest and completed-install markers; no credentials |
| `/etc/rehearsal/live.toml` | Configured IP endpoint and credential references; root:`rehearsal` 0640 |
| `/etc/rehearsal/pve-ca.crt` | Application-specific public CA; root:`rehearsal` 0640 |
| `/etc/rehearsal/api-token.json` | Runtime-owned **0400** credential file, never included in artifacts or Git |
| `/var/lib/rehearsal/reports` | Runtime-owned 0700 directory; sanitized JSON and metadata files 0600 |
| `/var/lib/rehearsal/last-live-inventory.json` | Pointer to the latest verified report |

Runtime identity: `rehearsal`, UID 999 / GID 988, only its own group, home `/var/lib/rehearsal`, shell `/usr/sbin/nologin`. Application execution needs no sudo, host SSH key, Docker socket or administrative API role. The operator uses existing sudo only for bootstrap and selecting this execution identity. No application service was installed.

Verified artifact SHA-256:

```text
01527cf052c173773f7183b30b9d9cb1d87fe014a0a772112c3b092d4090d7c7  rehearsal-0.2.0-py3-none-any.whl
```

The controller is Ubuntu 24.04.5, kernel 6.8.0-149-generic, Python 3.12.3, two vCPUs and about 3.8 GiB RAM. Root had about 29 GiB available on a 38 GiB filesystem before deployment. Its host-only address is verified `.83/24`; NAT uses `10.0.2.15/24` through `10.0.2.2`. Time synchronization reported true. Only `python3.12-venv` and its two wheel-package dependencies were added; no general OS upgrade occurred.

### Reproduce or safely repeat bootstrap

1. Use bounded SSH with batch mode, `StrictHostKeyChecking=yes`, `UpdateHostKeys=no`, a connection timeout and one connection attempt. Inspect current account, directories, config metadata and release markers first. Existing unexpected files/roles/scopes must be preserved for review.
2. If missing, install `python3.12-venv` with the existing Ubuntu repositories, then create the system user with `useradd --system --user-group --home-dir /var/lib/rehearsal --no-create-home --shell /usr/sbin/nologin rehearsal`. Create application/config directories root:`rehearsal` 0750 and state/report directories `rehearsal:rehearsal` 0700. Do not change an unrelated existing account.
3. Transfer the existing wheel, lock and cached runtime wheels into a protected staging directory. Verify the wheel against the digest above and each dependency against the hash-checked lock. Retain the artifacts under the release directory. The completed marker must match the version/digest; if it does, verify version/dependencies and skip reinstallation. A different artifact at the same version must not overwrite this release.
4. For a new matching release directory, temporarily allow `rehearsal` to create its venv and perform the two offline pip installs below. After version and dependency checks pass, record the identity/digest markers and make the release tree root:`rehearsal` again. Use non-dereferencing ownership changes (`chown -hR -P`) so venv symlinks never change system Python ownership. Do not move a venv after creation; entry points contain its absolute path.

```bash
# Initial installation only; operator has prepared ownership and verified artifacts.
sudo -n -u rehearsal python3 -m venv /opt/rehearsal/releases/0.2.0/venv
sudo -n -u rehearsal /opt/rehearsal/releases/0.2.0/venv/bin/python -m pip install --no-index --find-links /opt/rehearsal/releases/0.2.0/artifacts/runtime-wheels --require-hashes -r /opt/rehearsal/releases/0.2.0/artifacts/requirements-runtime.lock
sudo -n -u rehearsal /opt/rehearsal/releases/0.2.0/venv/bin/python -m pip install --no-index --no-deps /opt/rehearsal/releases/0.2.0/artifacts/rehearsal-0.2.0-py3-none-any.whl
sudo -n -u rehearsal /opt/rehearsal/releases/0.2.0/venv/bin/python -m pip check
```

5. Obtain the public CA over verified SSH and compare its certificate fingerprint. Install only the application CA file. Verify the served certificate from the controller with chain and IP checking; compare its leaf fingerprint with the public certificate inspected over SSH. Preserve any different pre-existing CA/configuration instead of silently replacing it. This deployment needed no host mapping or system trust change.
6. Query existing PVE users, roles, token metadata and ACLs before adding anything. Reuse exactly matching dedicated objects. Add only missing audit roles/bindings from the table above to both owner and token; preserve all other principals. Verify effective permission keys with `pveum user permissions` for the user and full token principal. The deployed owner and token have only `Sys.Audit`, `Datastore.Audit`, `VM.Audit` and `SDN.Audit`; node/storage/bridge ACL propagation is disabled.
7. **Token generation must be captured, never run unwrapped to the terminal.** The bootstrap used Python `subprocess.run(..., capture_output=True)` for token creation, extracted only the two credential fields in memory, and relayed them over verified SSH stdin to a root atomic writer on the controller. The writer validated the identity/UUID, created a temporary file in `/etc/rehearsal`, fsynced it, set ownership/mode, and linked it without replacing an existing file. It removed the temporary name afterward. No secret was placed in argv, environment, files on `dev01`, reports or command history.
8. If token metadata already exists, require the existing protected runtime credential file to validate and match that identity; then reuse it. If its secret is unavailable, stop and request explicit recovery/rotation instructions. Do not call token creation again or change expiry silently. A repeat bootstrap here reused the token with the same expiry and left the credential file's modification time unchanged.
9. Validate the runtime config and perform the explicit live command above as `rehearsal`. Persist only sanitized output under a new report filename. The bootstrap checked that the actual secret/header/identity strings were absent before saving. No persistent executor is necessary.

Public certificate fingerprints, verified through the authenticated channel and real TLS connection:

| Certificate | SHA-256 fingerprint |
| --- | --- |
| Cluster CA | `6D:08:72:C6:8A:53:28:16:C5:68:A3:0D:FD:5D:2E:67:C8:FD:0C:E0:50:C1:B2:01:C1:21:3C:CB:94:83:A1:A5` |
| Served node leaf | `4C:EB:96:4C:F8:B0:2E:9A:3B:ED:54:46:EA:A9:CE:57:A0:E1:53:9B:4F:45:51:52:C6:67:EB:07:72:BA:73:39` |

These are public certificate identifiers, not token material. CN `pve01.lab.test` and IP SAN `192.168.56.80` were inspected; the runtime handshake negotiated TLS 1.3 and verified the chain and IP.

### Result and remaining limits

Final report: `/var/lib/rehearsal/reports/inventory-20261112T120551652673Z.json`, with companion metadata and latest pointer. SHA-256: `36d151beafe8ab2ad110705860ff6f1d015038548c32c0709c00b10ef5e1d6bc`.

Exit 0, `backend=live`, `simulated=false`, `complete=true`; all four sections queried successfully. Visible node `pve01`, active `rehearsal-lvm` with 90 GiB total/available and `images,rootdir`, five interfaces including `vmbr0`, and zero QEMU VMs/templates. The empty VM list matched a separate privileged read. The final network list likewise matched the privileged API reference. Initial evidence before the bridge audit grant is retained separately.

No blocker remains for this one-shot inventory milestone. Token expiry still requires a deliberate future operator action. Some SSH dial attempts timed out between successful sessions; controller UFW was inactive and the cause was not established, so investigate before unattended bootstrap. No controller reboot test was performed. Nested workload boot, dedicated test isolation and resource ownership/cleanup are separate future gates. Later [user-supplied host evidence](environment.md#user-reported-physical-host-capacity) satisfies the initial physical backing-capacity gate for `pve01`; monitor actual host free space as its dynamic VDIs grow. No disk location is established for `dev01` or `rehearsal01`. No test VM/template/storage pool/network, runner or backup job was changed.

No guest boot, dedicated guest test network, template or mutation credential is needed for this first read-only check. Those remain separate provisioning gates. Do not create resources merely to make the VM list nonempty.

## Bounds, errors and tests

Default connect/pool timeout is 3 seconds; read/write timeout is 15 seconds. Per-endpoint attempt budget is three total, configurable from one to three. A monotonic request deadline defaults to 30 seconds, checked before attempts and between body chunks; an in-flight I/O may run to its bounded timeout. Timeout fields are positive and capped (60 seconds for I/O, 120 seconds for the deadline). These limits apply per endpoint, not to the whole multi-node run; an operator can additionally bound the CLI process if required.

Only idempotent GETs are retried: connect/read/write transport interruptions, protocol disconnects, timeouts and HTTP 502/503/504. Backoff with jitter is capped at one second. TLS errors, 401/403, other HTTP failures, redirects and malformed responses are not retried. HTTP 429 fails promptly as `unavailable`, avoiding repeated requests against a rate-limit response whose retry delay may exceed the budget. Responses are capped at 2 MiB and request uncompressed content; unexpected content encoding is rejected.

Fatal errors produce no success output and safe error JSON on stderr with `--format json`. Codes distinguish `authentication_failed`, `permission_denied`, `tls_error`, `connectivity_error`, `timeout`, `malformed_response`, `unavailable`, `http_error` and `credentials_error`. A failed version request is fatal. Node/section failures instead retain successful results plus explicit coverage, returning exit **4**. Failed node status skips its dependent queries. Unknown storage capacities stay JSON null rather than invented zeroes.

The network-blocked unit suite injects HTTPX mock transport and synthetic credentials; injected transports are marked `simulated: true` even with `backend: "live"`. It exercises successful GETs, TLS settings/errors, authentication/ACL errors, transient recovery/retry limits, deadlines, partial nodes/sections, parsing, redirects and redaction. It does not prove an actual TLS handshake, real API token rights, controller connectivity or nested VM boot.
