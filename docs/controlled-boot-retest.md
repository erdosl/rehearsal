# One supervised VM 9000 boot observation

Prepared on **13 November 2026**. This is a procedure for separate authorization,
not an executed retest. No VM power operation, credential renewal, journal change,
deployment or firewall change was made while preparing it. The host faults were
close to recorded nested starts; root cause remains unresolved. One vCPU did not
prevent the later fault. Kernel/component maintenance has not established a fix.

## Newly verified read-only evidence

Bounded, pinned-key SSH from dev01 succeeded to pve01 and rehearsal01. PVE reads
used local privileged `pvesh get`; the original deployed inventory independently
completed verified-TLS HTTPS reads with its existing audit token. No historical
task search was repeated. Times below are remote UTC observations, not proof that
clocks are aligned. Collection took 20.62 seconds on PVE and 0.89 on the controller.

| Observation | Verified 2026-11-13, 21:05–21:09 UTC |
| --- | --- |
| pve01 | PVE 9.2.2, kernel 7.0.2-6-pve, 4 visible CPUs, 16,768,651,264 bytes RAM; 15,056,801,792 available; root free 9,152,798,720 bytes |
| PVE boot ID | `6cf17da9-329d-430e-a010-0982bc61055f`; differs from the second start's historical boot |
| VM 9000 | Stopped, no lock, no template; 1 core/1 socket, CPU host, KVM enabled, 2048 MiB, balloon 0, onboot 0, SeaBIOS, serial0 socket, boot scsi0 |
| Sole NIC | `net0`, VirtIO `02:52:40:61:0e:f4`, vmbr1, firewall 1, **link_down=1**; no other NIC |
| Disks | `rehearsal-lvm:vm-9000-disk-0` 12,884,901,888 bytes; `rehearsal-lvm:vm-9000-cloudinit` 4,194,304 bytes; match durable volume ledger |
| Ownership | Installation/run/resource/nonce/node/pool/role match the controller journal and live description; identifiers below |
| Tasks/HA | Active node tasks empty; HA resources empty; no active controller lease; supervised lock available |
| Storage | rehearsal-lvm enabled/active lvmthin, total 96,636,764,160 bytes, available 94,762,010,936; data 1.94%, metadata 1.65%, monitored, no reported LV health fault |
| Firewall | Legacy pve-firewall enabled/running, IPv4 and IPv6 PVEFW hooks present. Cluster enable 1; node host-zone enable 0/nftables 0. Native bridge guard loaded; controller inet guard loaded with the exact guest tuple |
| Isolation | VM IN/OUT DROP, macfilter/ipfilter 1, dhcp/ndp/radv 0, expected rules/IP set. PVE vmbr1/enp0s16 IP-less; bridge hooks 1/1; IPv4/IPv6 routing forwarding 0/0 on both machines |
| Controller | Kernel 6.8.0-149-generic, 1 visible CPU, 4,106,526,720 bytes RAM; 3,663,572,992 available; root free 29,578,358,784 bytes; inventory release still 0.2.0 |
| Time services | PVE reports NTP synchronized; controller reports **not synchronized**, timesyncd inactive/enabled, vboxadd-service active. Actual offset/corrections unknown |
| Credentials | Bootstrap owner and privilege-separated token both expired at **15:08:20 UTC**, epoch 1794582500. Exact existing ACL paths/roles remain. Inventory token expires 12 December 11:51:04 UTC; real inventory succeeded, complete/non-simulated, all four sections queried |
| Journal | 36 complete, 1 historical failed/unverifiable, **1 uncertain**; resource state retained. Configuration digest matches. Read using SQLite `mode=ro&immutable=1` only after confirming WAL absent; SHA-256/mtime unchanged; WAL/SHM remained absent |

The effective permission maps list VM.PowerMgmt and audit/config/allocation rights
for the bootstrap identity; their zero values denote non-propagation, not a fresh
successful authentication. Expiry still blocks its use. The token was not renewed
or tested with a mutation. The broader build grants are documented in
[the original role table](supervised-build.md#pool-identity-and-exact-privileges-created).

Private collection files are outside Git at
`dev01:~/.local/state/rehearsal-publish-retest-20261113-28d78340/` (directory 0700,
JSON 0600). They include `pve_readonly.json`, `controller_readonly.json`,
`inventory.json` and two supplemental metadata files. Raw operational evidence is
not a public CI artifact. Journal SHA-256 before/after inspection:
`1b9c2f5c697944c38323c2e7cac4711641af29c98530fb9a35cca4a4253b10bf`.
This is a dated snapshot, not an admission receipt for a later start.

**Not newly verified:** physical-host health/free space, VirtualBox allocation or
component versions, guest execution, guest disk integrity, guest SSH identity,
agent installation, packet enforcement or either historical task outcome. The
operator supplied host kernel 7.0.0-43-generic and VirtualBox/Extension Pack
7.2.22 r175245; recollect them on ubase. Four CPUs visible on PVE do not prove a
remedy. The one-running-nested-guest ceiling remains in force.

## Authorization and fixed identity

Request a named operator and a single maintenance window, at most 30 minutes,
covering **only**: expiry-only renewal below; evidence-backed archival of the one
pending historical operation; fresh stopped isolation attestation; **one** start
of this existing resource; passive observation for 180 seconds; and one journalled
owned shutdown after a terminal start, with a separately explicit bounded hard
stop contingency if shutdown cannot work. No retry, NIC release, import, allocation,
lock clearing, deletion, host setting change or two-guest run is included.
If stop authority is withheld, obtain the operator's explicit retained-running
handoff plan before starting. Do not begin an exercise without an agreed end state.

| Binding | Exact value |
| --- | --- |
| Installation | `cc8e4939-1846-4891-8a99-7f746db4d31e` |
| Existing run | `157c73f9-3f9d-4c38-9ddb-b5c7fb9fe170` |
| Resource | `048c39b1-a339-4891-8230-b6717068c99e` |
| Nonce | `95117fed-1ac6-451d-9f7d-11c75c5078b6` |
| Mapping | VM 9000 / pve01 / pool rehearsal / role build |
| Pending operation | `a9cf5dc8-7654-40c0-99c0-a0ba6e589a88` |
| Its retained UPID | `UPID:pve01:00001794:0001C753:6AF61EA4:qmstart:9000:rehearsal-build@pve!bootstrap-9000:` |
| Existing journal root | `/var/lib/rehearsal/supervised/first-guest-20261112T141215Z` |
| Config | `/etc/rehearsal/first-guest.toml` |
| Existing sidecar | `/opt/rehearsal/supervised-tools/e95e1c7cb30b8f40` |

Assign a fresh observation ID `boot-retest-UTC-UUID` once, recorded in approval and
every capture filename. This is a new **operation on the existing resource/run**,
not a new reservation or replacement journal. The start CLI allocates its durable
operation UUID before POST; retain it even on interruption. The old resource expiry
does not authorize deletion. Do not edit its reservation/expiry to bypass a gate.

## Fresh prerequisites immediately before the attempt

1. The ubase operator is present, independent host logging is running, the window
   and end-state authority are approved, and no other operator/automation will
   power a nested guest. Verify zero other running nested guests and no pending
   workload. Outer dev01/rehearsal01 are not an increase to the nested-guest budget.
2. Repeat the bounded readbacks above through existing verified connections. Match
   every ownership field, config digest, exact disks, no extra/unused volume,
   stopped/unlocked, onboot 0, sole disconnected NIC, no active task/HA/lease and
   exclusive supervised lock. Record current boot IDs and confirm the historical
   worker cannot still execute across the changed PVE boot. Do not search old UPIDs.
3. Recheck pool health/metadata and at least 18 GiB pool reserve plus existing
   12 GiB root/2 GiB auxiliary commitment, PVE root free >=6 GiB and MemAvailable
   >=6 GiB (4 GiB overhead reserve + 2 GiB guest). No new disk is imported. Obtain
   **fresh exact-byte backing-filesystem evidence on ubase**, including both VDI
   locations and outstanding dynamic-disk commitments; guest thin-pool space does
   not prove host capacity. Retain at least the existing 18 GiB backing reserve
   after possible growth of already committed disks; abort on unknown commitments.
4. Inspect host kernel errors, storage errors, taint/pressure and component state.
   Any fresh oops/hung VM or unresolved host error aborts admission. Maintenance
   changes alone do not pass this gate. No reboot/module/CPU/APIC change is implied.
5. Recheck both guards, actual legacy hooks, VM options/rules/IP set, disconnected
   link and forwarding off; fresh management SSH and verified-TLS inventory must
   still work. Configuration readback is not a packet-enforcement test. Do not
   release the NIC to make SSH possible during this initial observation.
6. Record UTC, monotonic uptime, boot IDs and NTP status on **all three observers**.
   Bound each SSH exchange with dev01 UTC/monotonic before/after samples and retain
   the round-trip uncertainty. Controller NTP is currently unsynchronized: require
   measured offsets bounded to <=1 second, or stop for separate time-service
   investigation; do not silently correct clocks. Durations within a process use
   monotonic time. UPID timestamps retain their encoded-start meaning.

For example on pve01, the operator can use these bounded reads (no token output):

```bash
timeout 10 sudo pvesh get /cluster/resources --type vm --output-format json
timeout 10 sudo pvesh get /nodes/pve01/qemu/9000/status/current --output-format json
timeout 10 sudo pvesh get /nodes/pve01/tasks --source active --limit 100 --output-format json
timeout 10 sudo pvesh get /nodes/pve01/storage/rehearsal-lvm/status --output-format json
timeout 10 sudo pvesh get /nodes/pve01/storage/rehearsal-lvm/content --vmid 9000 --output-format json
timeout 10 sudo lvs --units b --nosuffix -o lv_name,lv_size,lv_attr,data_percent,metadata_percent,lv_health_status rehearsal-vg
timeout 10 sudo pve-firewall status
timeout 10 sudo nft list table bridge rehearsal_test
timeout 10 sudo pvesh get /nodes/pve01/qemu/9000/firewall/options --output-format json
timeout 10 sudo pvesh get /nodes/pve01/qemu/9000/firewall/rules --output-format json
timeout 10 sudo pvesh get /nodes/pve01/qemu/9000/firewall/ipset/ipfilter-net0 --output-format json
```

Retain config/ownership via the tool's sanitized `owned` readback or a whitelist;
do not publish `qm config`/cloud-init/raw API output, which may contain access data.

## Host-operator capture on ubase

Run these **on ubase**, never from dev01 or through assumed host SSH. Use `vim`
to prepare/review capture scripts and `grep` to inspect output. No host settings
are changed. Create a new private evidence directory, recording its path in the
approval; do not reuse earlier captures:

```bash
umask 077
capture_dir=$(mktemp -d "$HOME/rehearsal-boot-retest-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
vim "$capture_dir/host-before.txt"
date -u +%Y-%m-%dT%H:%M:%S.%NZ > "$capture_dir/host-clock.txt"
cat /proc/uptime /proc/sys/kernel/random/boot_id >> "$capture_dir/host-clock.txt"
timedatectl show --property=NTPSynchronized >> "$capture_dir/host-clock.txt"
uname -a > "$capture_dir/kernel.txt"
cat /proc/sys/kernel/tainted > "$capture_dir/tainted.txt"
free -b > "$capture_dir/memory.txt"
df -B1 --output=source,fstype,size,used,avail,pcent,target /mnt/ssd > "$capture_dir/space.txt"
VBoxManage --version > "$capture_dir/vbox-version.txt"
VBoxManage list extpacks > "$capture_dir/extpacks.txt"
VBoxManage list vms > "$capture_dir/registered-vms.txt"
modinfo vboxdrv > "$capture_dir/vboxdrv.txt"
lsmod | grep -E 'vbox|kvm' > "$capture_dir/modules.txt"
cat /sys/module/kvm/parameters/enable_virt_at_load > "$capture_dir/kvm-setting.txt"
sudo fuser /dev/kvm > "$capture_dir/kvm-users.txt" 2>&1
sudo journalctl -k -b --no-pager -o short-iso-precise > "$capture_dir/kernel-before.txt"
grep -Ei 'BUG:|Oops:|NULL pointer|soft lockup|I/O error|out of memory' "$capture_dir/kernel-before.txt"
```

A nonzero `fuser` may mean no users; record the exit status separately, do not use
`-k`. Missing tools/evidence are prerequisites to resolve, not permission to install
or change components. Inspect registered VMs with vim, then set `outer_uuid` to the
verified pve01 registration and `vbox_log` to its **current** VBox.log path. Do not
assume its display name. Inspect `VBoxManage showvminfo "$outer_uuid"` privately
and record actual CPU/RAM/nested virtualization, running state, VDI paths/UUIDs,
log directory and snapshots. Retain file metadata and `du -B1` for both VDIs; the
historically supplied locations are:

```text
/mnt/ssd/VirtualBox VMs/Proxmox/Proxmox-training/pve01/pve01.vdi
/mnt/ssd/VirtualBox VMs/Proxmox/Proxmox-training/pve01/pve01_1.vdi
```

In two operator terminals, begin bounded capture **before** the single start:

```bash
sudo timeout --signal=INT 240 journalctl -k -b -n 0 -f -o short-iso-precise > "$capture_dir/kernel-follow.txt"
```

```bash
cp -- "$vbox_log" "$capture_dir/VBox-before.log"
timeout --signal=INT 240 tail -n 0 -F -- "$vbox_log" > "$capture_dir/VBox-follow.log"
```

Also retain the final current and rotated VBox.log files, final kernel journal,
clock/uptime/boot ID and file hashes after observation or host recovery. Preserve
VirtualBox's log header mapping its relative timestamps to UTC; do not equate them
with UPID or controller HTTP times without that mapping and uncertainty. Logs can
contain local paths/identities; keep them private, outside this repository/guest.

## Explicit historical archival, then narrow renewal

**Separate approval required before this section.** Archive only on the independently
verified current-effect evidence below. This step does not require the expired API
credential; privileged read-only SSH and the unchanged audit token supply evidence.

The old second start cannot simply be called successful/failed based on stopped
state. Require current ownership/disks/stopped state, the changed boot boundary,
no remaining old worker/active task, lock/lease clearance and a written/dated operator
decision that its **current effect** is settled while historical outcome stays
unknown. Missing task history alone is insufficient. Do not repeat old task searches.

On rehearsal01, as the rehearsal runtime user, use the existing sidecar and root.
Create a new private observation subdirectory with `mkdir` (fail if it exists).
Under the Journal exclusive lock, take a consistent SQLite backup to a new 0600
file using `Connection.backup`, retain its hash and full original pending row, and
append an `external-restart-reconciliation` event containing the operator approval,
fresh evidence references, original operation/UPID and `historical_task_outcome:
unknown`. This is an explicit future state mutation, not part of read-only prep.

After setting the runtime variables in the next command block and verifying a
fresh private `current-effect.json` receipt, the backup/event preparation is:

```bash
"$build_python" - "$observation_dir" <<'PY'
import hashlib, json, os, sqlite3, sys, time
from pathlib import Path
from rehearsal_build.journal import Journal

os.umask(0o077)
out = Path(sys.argv[1])
receipt = json.loads((out / "current-effect.json").read_text())
assert 0 <= time.time() - receipt["utc_epoch"] < 120
assert receipt["historical_task_outcome"] == "unknown"
assert receipt["operator_approval"] and receipt["evidence_sha256"]
assert all(receipt[k] is True for k in (
    "ownership_matches", "volumes_match", "stopped_unlocked",
    "new_boot_boundary", "old_worker_absent", "no_active_tasks_or_leases"))
root = Path('/var/lib/rehearsal/supervised/first-guest-20261112T141215Z')
with Journal(root) as journal:
    old = journal.operation('a9cf5dc8-7654-40c0-99c0-a0ba6e589a88')
    assert old['status'] == 'uncertain'
    assert old['resource'] == '048c39b1-a339-4891-8230-b6717068c99e'
    backup = out / 'journal-before.sqlite3'
    backup.open('xb').close()  # Existing evidence must never be replaced.
    with sqlite3.connect(backup) as destination:
        journal.db.backup(destination)
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    with (out / 'original-operation.json').open('x') as stream:
        json.dump({'operation': old, 'backup_sha256': digest}, stream)
    journal.event('external-restart-reconciliation', {
        'previous_operation': old, 'receipt': receipt, 'backup_sha256': digest,
        'historical_task_outcome': 'unknown', 'action': 'approved-archival-intent'})
PY
```

The receipt is an operator assertion backed by the independently retained fresh
readbacks, not a substitute for them. Fill it with vim only after performing those
checks. A failed assertion or existing filename stops the procedure. Never set
booleans merely to satisfy this script. Inspect any interruption before continuing.

Then create `archive-historical.json` with vim in that private directory:

```json
{
  "operation": "a9cf5dc8-7654-40c0-99c0-a0ba6e589a88",
  "state": "failed",
  "result": {
    "classification": "historical-outcome-unavailable",
    "historical_task_outcome": "unknown",
    "current_effect": "owned-stopped-after-external-restart",
    "reason": "Operator-approved archival; fresh evidence retained separately"
  }
}
```

Use the existing CLI `operator-result` once. Its legacy `failed` is an archival
controller status, **not confirmed Proxmox task failure**. Preserve the old UPID,
the original first-start terminal row and all events/snapshots. Check the backup
and append-only explanation before making this transition. If interrupted, inspect
the exact row/event/backup before continuing; do not recreate or clear the journal.

Set these runtime variables before the backup script above, then perform the
archival CLI invocation below, on rehearsal01 in the approved runtime shell:

```bash
export PYTHONPATH=/opt/rehearsal/supervised-tools/e95e1c7cb30b8f40
export REHEARSAL_LIVE=1
build_python=/opt/rehearsal/current/venv/bin/python
build_config=/etc/rehearsal/first-guest.toml
# Set observation_dir to the newly created private directory, never the old run root.
"$build_python" -m rehearsal_build exercise --config "$build_config" --live \
  --exercise first-guest --operation operator-result \
  --request "$observation_dir/archive-historical.json"
```

### Expiry-only renewal after historical archival

The old uncertainty must be archived first: the existing journal correctly blocks
new operation intents while it remains pending. For **each** expiry modification,
record a separate `operator-intent` before the PVE operator's command, then verify
metadata and record `operator-result` before proceeding. Use unique labels with the
observation ID. For the owner, the request shape is:

```json
{
  "label": "renew-owner-OBSERVATION_ID",
  "path": "/access/users/rehearsal-build@pve",
  "actor": "root@pam",
  "desired": {"expire": 0}
}
```

Replace zero with the approved end epoch. Invoke the existing explicit exercise
CLI with `--operation operator-intent --request PATH`, capture the returned operation
UUID, then perform **only** that owner expiry command. After independent readback,
record that UUID with `--operation operator-result`, `state: complete` and a result
containing the observed expiry and unchanged ACL evidence reference. Repeat for
`/access/users/rehearsal-build@pve/token/bootstrap-9000` with a distinct token label.
An interrupted command remains uncertain until metadata readback reconciles it;
never retry creation/modification blindly. Do not create another state root.

**Separate approval required before this section.** On PVE, the operator may extend
only the expiry of existing `rehearsal-build@pve` and its existing
`bootstrap-9000` token to the agreed window end (<=30 minutes), then read both
metadata back. Preserve privilege separation, roles, ACL paths/propagation and the
existing secret. Do not recreate/rotate the token, display its value or change the
protected file/config digest. Example after recording the approved UTC epoch:

```bash
sudo pveum user modify rehearsal-build@pve --expire "$approved_end_epoch"
sudo pveum user token modify rehearsal-build@pve bootstrap-9000 --expire "$approved_end_epoch"
```

These existing build grants include allocation/config rights not needed for a
start. No use of those rights is authorized. A different least-privilege identity
or config-digest rebinding needs a separately reviewed change; do not broaden ACLs
or silently substitute credentials. Verify TLS and effective audit/VM.PowerMgmt
permissions before proceeding, without printing token material.

## One start, passive guest proof and bounded reconciliation

After the actual isolation checks, create `isolation.json` with current epoch and
the exact six check names below; its observation must be younger than 120 seconds.
Do not copy a stale timestamp or attest unperformed checks:

```json
{
  "state": "isolated",
  "evidence": {
    "resource": "048c39b1-a339-4891-8230-b6717068c99e",
    "utc_epoch": 0,
    "checks": ["stopped", "nic_disconnected", "per_vm_policy", "bridge_guard", "controller_filter", "kvm"]
  }
}
```

Run `--operation attest --request "$observation_dir/isolation.json"` with the same
explicit exercise/config/opt-ins as above. This changes only the resource's journal
state to isolated. It neither releases the NIC nor changes PVE configuration.

Before POST, have the PVE operator arm a passive serial reader for the existing
`serial0: socket`: bound its entire lifetime to 240 seconds, waiting for
`/run/qemu-server/9000.serial0`,
connect as root using Python AF_UNIX/SOCK_STREAM, **recv only, never send**, cap
output at 2 MiB, and timestamp each chunk with UTC and monotonic time. Persist the
raw bytes privately on PVE and transfer them to the independent observer afterward.
Review its code with vim before authorization. Do not use `qm terminal` interactively
or inject keys. In parallel retain PVE kernel logs and new QEMU PID/process start
time/boot ID with a bounded read-only collector. Missing serial output is an
inconclusive attempt, not authorization to reboot or reconnect the NIC.

For example, use vim to prepare this reader on PVE, then run as root in a separate
terminal with a new private output path before the controller invocation. It has
no API client, serial writes or VM power action. JSONL base64 frames retain exact
serial bytes and local timing; this is **private raw evidence**, never a CI upload:

Save it as `serial-reader.py` in a new mode-0700 PVE evidence directory with vim;
invoke `sudo timeout --signal=INT --kill-after=5 245 python3 PATH/serial-reader.py
PATH/new-serial.jsonl`. Use real reviewed absolute paths. Confirm its `armed` event
and all host captures before POST. Start within 30 seconds of arming, or replace
only passive captures with new filenames before any POST. Require captures through
at least 180 seconds after the invocation start; incomplete coverage is inconclusive.

```python
import base64
import datetime
import json
import os
import socket
import sys
import time
from pathlib import Path

os.umask(0o077)
end = time.monotonic() + 240
remaining = 2 * 1024 * 1024
with open(sys.argv[1], 'x') as output:
    def record(**fields):
        fields.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      monotonic=time.monotonic())
        output.write(json.dumps(fields) + '\n')
        output.flush()

    record(event='armed', boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    connection = None
    while time.monotonic() < end:
        candidate = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        candidate.settimeout(0.5)
        try:
            candidate.connect('/run/qemu-server/9000.serial0')
        except OSError:
            candidate.close()
            time.sleep(0.2)
        else:
            connection = candidate
            break
    if connection is not None:
        with connection:
            pid = int(Path('/run/qemu-server/9000.pid').read_text())
            record(event='connected', qemu_pid=pid,
                   proc_stat=Path(f'/proc/{pid}/stat').read_text().strip())
            while remaining and time.monotonic() < end:
                try:
                    data = connection.recv(min(65536, remaining))
                except socket.timeout:
                    continue
                if not data:
                    break
                remaining -= len(data)
                record(event='serial', data_base64=base64.b64encode(data).decode('ascii'))
    record(event='end', bytes_received=2 * 1024 * 1024 - remaining)
```

Create `start.json` once; substitute the approved observation ID in the label:

```json
{
  "label": "controlled-boot-retest-01-OBSERVATION_ID",
  "method": "POST",
  "path": "/nodes/pve01/qemu/9000/status/start",
  "params": {},
  "deadline": 120,
  "expect": {
    "kind": "read",
    "path": "/nodes/pve01/qemu/9000/status/current",
    "fields": {"status": "running"}
  }
}
```

Bracket the following **single invocation** with UTC and monotonic timestamps in
an exclusive new private evidence file; use `timeout --signal=INT --kill-after=5
150` to bound the command. Capture its JSON, exit status and resulting operation
UUID/UPID from the existing journal even when it exits nonzero:

```bash
"$build_python" - "$observation_dir" "$build_config" <<'PY'
import datetime, json, os, subprocess, sys, time
from pathlib import Path

os.umask(0o077)
out = Path(sys.argv[1])
def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

# Exclusive files prevent accidental repetition through this wrapper.
with (out / 'start-invocation.jsonl').open('x') as record:
    with (out / 'start-output.json').open('x') as stdout:
        with (out / 'start-error.json').open('x') as stderr:
            start = time.monotonic()
            record.write(json.dumps({'event': 'invocation-start', 'utc': utc(),
                                     'monotonic': start}) + '\n')
            record.flush()
            code = None
            try:
                code = subprocess.run([
                    'timeout', '--signal=INT', '--kill-after=5', '150',
                    sys.executable, '-m', 'rehearsal_build', 'exercise',
                    '--config', sys.argv[2], '--live', '--exercise', 'first-guest',
                    '--operation', 'request', '--request', str(out / 'start.json')
                ], stdout=stdout, stderr=stderr, check=False).returncode
            finally:
                record.write(json.dumps({'event': 'invocation-end', 'utc': utc(),
                    'elapsed_seconds': time.monotonic() - start, 'exit_code': code}) + '\n')
            if code != 0:
                raise SystemExit('Stop: inspect retained operation; do not repeat request')
PY
```

The deployed sidecar journals intent before POST and retains its returned UPID,
but lacks the newer local HTTP timing/provenance events. The wrapper interval is
**command invocation time**, not HTTP send time; a UPID in the journal is not newly
proved wire-response provenance. Do not deploy an update under this procedure.
If that newer telemetry is a prerequisite, stop and request a separate deployment
review instead. The command's `running` postcondition proves only the API state.

If the command loses its response, **do not invoke request again**. Keep uncertain
state and captures. With connectivity healthy and a recorded exact new UPID,
perform at most three status GETs separated by 5 seconds (each <=10 seconds), plus
one bounded log GET for that **new** task; validate node/type/VMID/actor against the
new operation. A missing/unknown UPID, unavailable terminal result or a continuing
task after the deadline ends this attempt for operator review. Do not invoke the
old sidecar's 600-second-default reconciliation or broad discovery to settle it.
Only after independently observed terminal `OK` and matching owned running state
may an operator explicitly record completion with the new operation's evidence;
a terminal PVE failure must be labelled as such. Preserve ambiguity otherwise.

Success requires all of: terminal start `OK`; exact owned VM/config/disks and NIC
still disconnected; **new Linux kernel and systemd/cloud-init progress from this
guest's serial stream**, correlated to the new QEMU PID and capture window; PVE,
controller and host remain responsive without a new host fault for the 180-second
observation. A GUI, QEMU PID, task `OK` or VM `running` alone is insufficient.
No serial progress means inconclusive/failed boot observation. Guest agent is
not assumed installed; network SSH readiness is a later stage.

## Abort, end state and evidence

On host oops/NULL write, new hung execution, loss of management responsiveness,
ownership/config drift, storage pressure, active competing task or deadline:
**stop new mutations immediately**. No repeated start, stop during an uncertain
task, import, lock clearing or deletion. Keep every operation/UPID and both disks.
The host operator preserves logs before separately deciding host recovery; a host
reboot/power cycle is not an automated recovery action. Later stopped state can
prove current effect, never retroactively prove task outcome.

On a healthy completed observation, use the separately approved owned shutdown:
same request operation, POST `/nodes/pve01/qemu/9000/status/shutdown`, params
`{"timeout":60}`, deadline 90, expect read status `stopped`. Journal its own intent
and UPID; bound the invocation at 120 seconds. Reconcile a lost response before
any fallback. Because the NIC is disconnected and the agent is unproved, clean
shutdown may fail. A single hard stop is permitted **only if explicitly included
in the approval**, after terminal shutdown/no pending task and fresh ownership
checks: POST `/nodes/pve01/qemu/9000/status/stop`, empty params, deadline 60, same
stopped postcondition. Never retry an ambiguous stop. Record whether shutdown was
graceful; preserve disks for offline filesystem review if it was forced.

Verify stopped/unlocked, onboot 0, link_down 1, no active task/lease and exact disks;
use `mark-stopped` only when journal/task outcomes permit it. Retain a consistent
post-attempt journal backup, configuration/ownership/volume projection, terminal
task evidence, serial bytes, host/PVE kernel and VBox logs, timing uncertainty,
component/capacity samples, operator decisions and SHA-256 index outside the VM.
Raw evidence stays private; publish only a reviewed sanitized factual summary.
No automatic retention deletion applies to unresolved evidence or VM disks.

One successful observation would establish one boot under its recorded conditions,
not root-cause resolution, sustained stability, effective guest packet isolation or
PostgreSQL recovery. NIC release/host-key authentication/isolation probes are a
separate later authorization. The prepared source/restore adapter needs another
separate two-guest capacity decision; **do not raise the current one-guest cap**
to use it during this retest.
