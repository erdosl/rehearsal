# Controlled rehearsal01 reboot validation

Updated **2026-11-12**. **Executed successfully at 14:16 UTC**, under the subsequent first-guest authorization. PVE was separately rebooted once and passed by 14:20 UTC, after the controller returned and its checks passed. Neither machine needed repair. Rehearsal has no application daemon; the firewall persistence service is a separate oneshot. Success proves persistent installation/firewall configuration and a manually invoked live CLI after restart. [Dated execution evidence](supervised-build.md#completed-persistence-checks) records boot IDs, comparisons, report paths and limits.

## Preconditions and recovery path

- Confirm the target is **`rehearsal01`, 192.168.56.83**, not `pve01` or the physical host. Use existing SSH alias/host-key pinning; each connection uses batch mode, one attempt, a five-second connection timeout and an overall command timeout. No host-key replacement is permitted.
- Arrange a host operator who can use the controller's VirtualBox console if it does not return. `dev01` cannot administer that host; no automated host SSH/`VBoxManage` recovery is available. Do not start without that recovery arrangement.
- Do not combine the check with OS upgrades, network/firewall changes, a release switch, token rotation or PVE maintenance. Capture current address/routes/time state; close pending administrative work. No Rehearsal run/task may be active. Once provisioning exists, reconcile it before a planned reboot.
- Confirm the unchanged inventory token is still valid: its recorded expiry is **2026-12-12 11:51:04 UTC**. If expired or missing, stop; a planned credential lifecycle task is separate from reboot validation.
- Confirm operator `sudo -n` access and the unprivileged runtime account still work. The runtime account has a nologin shell; use `sudo -n -u rehearsal <absolute executable>`, not an interactive login.

Example bounded inspection from `dev01`, before a future reboot:

```bash
timeout 25s ssh -T -o BatchMode=yes -o ConnectTimeout=5 -o ConnectionAttempts=1 -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o ServerAliveInterval=5 -o ServerAliveCountMax=2 rehearsal01 'hostname; ip -br address; ip -4 route; cat /proc/sys/kernel/random/boot_id; uptime; timedatectl show -p NTPSynchronized; sudo -n id'
```

Use the same SSH options for later connections. Keep evidence under a fresh UTC/UUID validation directory on the controller, e.g. `/var/lib/rehearsal/validation/<validation-id>/`, owned by `rehearsal`, mode 0700; evidence files are 0600 and created without overwriting. Record that directory outside the SSH session so it can be reopened after reboot. It is private operator evidence, not a public artifact bundle.

## Before reboot: establish a passing baseline

1. As the runtime user record the current boot ID, UTC time and resolved `/opt/rehearsal/current` path. Expect `/opt/rehearsal/releases/0.2.0`. Record public wheel digest from the retained release artifact; it must equal `01527cf052c173773f7183b30b9d9cb1d87fe014a0a772112c3b092d4090d7c7`. Record hashes of `live.toml`, public CA, release markers and installed release files against a trusted baseline; do not rebuild/reinstall anything.
2. Record ownership/type/mode metadata for the release, `/etc/rehearsal`, config, CA, credential file and state/reports. Credential must remain a regular non-symlink file, owned by `rehearsal`, **0400**; config/CA root:`rehearsal` 0640; config directory 0750; state/report directories runtime-owned 0700. Record credential inode, size and modification timestamp for comparison, **never its contents or digest in exported reports**. Config validation does not test credential readability; the real inventory below does.
3. Run these existing installed commands on the controller, as the runtime account. Require version 0.2.0, no broken dependencies and valid configuration:

```bash
sudo -n -u rehearsal /opt/rehearsal/current/venv/bin/rehearsal --version
sudo -n -u rehearsal /opt/rehearsal/current/venv/bin/python -m pip check
sudo -n -u rehearsal /opt/rehearsal/current/venv/bin/rehearsal config validate --config /etc/rehearsal/live.toml --format json
```

4. Run the documented real inventory and retain its sanitized JSON, exit status, start/end UTC and release/config identifiers as `pre-inventory` evidence. The command itself is:

```bash
sudo -n -u rehearsal timeout 240s env REHEARSAL_LIVE=1 /opt/rehearsal/current/venv/bin/rehearsal inventory --config /etc/rehearsal/live.toml --backend live --live --format json
```

When saving stdout/stderr, arrange redirection **inside the runtime-user process**, with umask 077 and exclusive/no-clobber creation. Do not use a root/operator redirection that changes file ownership or replaces the earlier successful report. Do not enable shell tracing, HTTP debug output or credential dumps. The existing CLI emits sanitized inventory/errors; retain only these and selected public metadata. No credential material is copied to `dev01`.

Require exit 0, `backend=live`, `simulated=false`, `complete=true`, all configured node/storage/VM/network coverage `queried`, node `pve01` and active `rehearsal-lvm`. Today there are no VMs, but do not hard-code an empty VM list once guest work is authorized; compare with the intended baseline and scoped visibility. Current bridge visibility is `vmbr0`; a later bridge requires a separately reviewed audit scope. Check pool capacity against the pre-check observation rather than requiring 90 GiB free forever. A failure or partial inventory **before** reboot blocks this comparison until diagnosed.

5. Confirm there is no installed Rehearsal executor/application daemon expected to start. Separately require `rehearsal-test-filter.service` enabled/active/exited and inspect its effective nft input/forward rules against the saved baseline. An empty guest set is expected until an owned guest is admitted. Keep generic OS service failures separate from CLI results.

## One reboot and bounded return check

Only after the preceding baseline passes, an authorized operator runs **on rehearsal01**:

```bash
sudo -n systemctl reboot
```

Send this command **once**. An SSH disconnect is consistent with reboot but is not proof. From `dev01`, use bounded strict-host-key SSH probes at approximately ten-second intervals, with a **five-minute overall deadline** and per-attempt connection timeout. A successful login must report `hostname=rehearsal01` and a **different kernel boot ID** from the baseline; uptime alone is insufficient. Do not repeat the reboot because its response was lost. Do not accept a changed host key.

If the deadline expires, record `reboot return unverified`, retain the last successful baseline and stop automated attempts. Ask the arranged host operator to inspect the controller console; do not reboot `pve01`, change networks or credentials, disable host-key checks, or repeatedly power-cycle the controller. Existing intermittent SSH dial timeouts are a reason to use the bounded window and console fallback, not to claim a successful reboot from elapsed time.

## After reboot: prove persistence and real API use

1. Confirm changed boot ID, expected hostname and `.83/24` on the management interface, intact NAT/default route, reachable `.80:8006`, time synchronization and available filesystem space. Use explicit endpoints with bounded calls; no network scan. A live inventory succeeding with the configured CA is the application-level connectivity/TLS check.
2. Compare the current symlink target, wheel/release/config/CA hashes and ownership/mode metadata with the pre-check. Check that the runtime user can traverse/read its installed executable/config/CA/state and the credential remains a non-symlink owned 0400 file with unchanged inode/size/mtime. Do not print credential contents. A changed/missing file is a failure to investigate, not permission to bootstrap again.
3. Repeat version, `pip check`, config validation and the **same explicit live inventory command as `rehearsal`**. Save fresh `post-inventory` JSON/exit status/timestamps. Require real, complete queried coverage and expected node/storage/resources, with no fixture fallback. This proves the stored credential can still authenticate and authorize the calls after reboot; SSH/sudo alone does not.
4. Confirm the retained earlier reports are readable with the same hashes and that a new private evidence file can be created by `rehearsal`. Preserve the pre/post snapshots and comparison result. Do not overwrite `/var/lib/rehearsal/last-live-inventory.json` until the new result has passed; updating that pointer is optional, not the test itself.
5. Record absence of an application daemon as normal. Require the enabled firewall oneshot to have succeeded and compare persistent rule bytes with effective rules, ignoring only reset counters/handles in the normalized comparison. Confirm controller enp0s9 addressing/Netplan, interface-scoped input deny (including management/NAT destinations), forwarding deny and routing forwarding 0/0. Review only relevant boot errors if a prerequisite fails; do not dump broad journals.

Pass only if the boot ID changed, the same release/configuration/trust and protected credential persisted, evidence storage remains usable, and the post-reboot live CLI passes without repair. Classify a TLS, authentication, permission, connectivity, timeout or partial-coverage error separately. An expired token, pre-existing failure or changed resource list must not be labeled a reboot-induced application failure without evidence. If no reboot was observed, mark this test **not completed**, even if the CLI works.

The [environment evidence](environment.md) and [execution record](supervised-build.md) now contain the actual pre/post boot identifiers, version/digest preservation, addresses, CLI exit/coverage and sanitized report paths. No physical-host resilience, executor restart or guest isolation is claimed by this check.

## PVE restart, after the controller passes

For a separately authorized PVE restart, first require no guests, active PVE tasks, Rehearsal operation/lease, pending systemd work or rollback timer. Preserve a fresh root-only baseline of public network/firewall configuration, effective IPv4/IPv6 hooks, selected backend/options, custom bridge table/unit and procfs forwarding settings. Run fresh dev01 SSH/sudo, DNS/NAT HTTPS and controller verified-TLS inventory before restart. Keep the controller's filter unchanged. Record both boot IDs and confirm the operator console recovery path.

Journal and issue `sudo -n systemctl reboot` **once on pve01**. Use the same five-minute deadline, bounded strict-host-key probes and changed-boot-ID requirement. A lost response is not permission for another reboot. Stop if return/enforcement cannot be proved; request operator console recovery instead of changing management networking or bypassing trust.

After restart verify management/default routes, routing forwarding 0/0, vmbr1's sole enp0s16 port in forwarding state, no test-interface IPs and host IPv6 disabled. Require legacy `pve-firewall` enabled/running with `nftables=0`, actual IPv4/IPv6 FORWARD hooks, bridge netfilter switches 1/1, identical enabled bridge guard and persisted files. Compilation alone does not establish enforcement. Keep node host-zone filtering disabled. Repeat fresh SSH/sudo, DNS/NAT HTTPS and real controller inventory before declaring success.

pmxcfs is a FUSE configuration filesystem: inode numbers can change across reboot. Compare bytes/hash, mode, owner/group and modification time for its firewall files; do not require stable pmxcfs inodes. Keep the original inventory credential's local-filesystem inode/size/mtime comparison intact. In the executed check only the two pmxcfs firewall inode fields differed; both before/after observations and the corrected comparison were retained.

The current authorization allowed **one restart of each machine**, and both have been consumed successfully. Do not repeat them for later guest-profile validation without further authorization. Guest rules/tuples were absent at these restarts and remain untested across reboot.
