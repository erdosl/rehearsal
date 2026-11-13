# Development rules

- Read the README and relevant design documents before changing behaviour. Distinguish planned features from implemented and verified features.
- Preserve existing work and `LICENSE`. Inspect Git status first. Do not commit or push unless requested.
- Keep changes within the current task. The read-only CLI is deployed on `rehearsal01`; repeat bootstrap changes only when authorised, preserve matching releases/credentials and never silently rotate an existing token. Workload provisioning, an executor, recovery, a UI and Actions remain future work.
- Use Python 3.12 as the initial baseline. Prefer a small package, explicit interfaces, a CLI, systemd and SQLite. Explain new dependencies. Kubernetes and distributed services are outside the initial scope.
- Keep endpoint addresses, nodes, storage names, templates, VMID allocations and network mappings in validated configuration. Examples must contain fake credentials or credential references.
- Default tests must run offline with mocks/fixtures and no lab credentials. Block accidental network access in unit tests. Test safety properties, task failures, ambiguous outcomes and cleanup decisions.
- Live tests require both an explicit command-line opt-in and `REHEARSAL_LIVE=1`, plus the appropriate configured credentials and connectivity. Mutating exercises also require an explicit exercise/run operation; live inventory is read-only.
- Do not put secrets, private keys, production data, backup dumps or unsanitised reports in this public repository. Do not dump environment variables or credential files. Redact secrets before logs are persisted.
- Verify Proxmox TLS using a trusted CA and matching hostname/IP. Do not introduce `verify=False`, `curl -k` or password guessing as a workaround.
- Journal operation intent before API mutations; retain UPIDs and reconcile uncertain responses before issuing another mutation. Never retry provisioning blindly.
- Delete only resources whose installation, run and resource ownership match durable state and live metadata. Never infer ownership from a name prefix, VMID range or expiry alone. Templates, controller and unrelated VMs are protected.
- Apply isolation before any disposable or restored VM boots. Expiry cleanup must respect active leases and unresolved tasks. Preserve reports outside disposable VMs.

## Environment boundaries

- `dev01` (`~/projects/Rehearsal`) is for editing, local tests and Git. Delivered runtime services belong on separately provisioned Rehearsal VM(s).
- Do not depend on SSH to the physical host, shared folders, `VBoxManage` or host-side commands from `dev01`. Initial controller/network preparation may be manual work performed separately by the host operator.
- The address reservations in `docs/environment.md` do not prove VMs exist or addresses are free. `LAB-*`, `lab-storage` and `lab-cluster` must not be assumed connected.
- Do not install packages, change networks/GitHub settings, start services, provision VMs or register runners unless the current task authorises that work. Read-only inspection is appropriate within scope.
- Never execute untrusted pull-request code on a runner with lab access. Public CI uses GitHub-hosted runners; the proposed trusted lab runner has a separate trust boundary.
- Keep inspection evidence dated and label supplied facts, verified facts, assumptions and unknowns. A reachable HTTPS listener does not prove API permissions, usable storage or successful nested VM boot.
