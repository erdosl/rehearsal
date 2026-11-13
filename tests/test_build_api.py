import json
import sqlite3
import time
import traceback
import uuid

import httpx
import pytest
from test_build_admission import evidence

from rehearsal.credentials import APIToken
from rehearsal_build.api import BuildAPI
from rehearsal_build.config import BuildConfig
from rehearsal_build.journal import Journal, SafetyError, description


class Lab:
    def __init__(self, journal, config):
        self.journal = journal
        self.config = config
        self.record = journal.reserve(
            node=config.node, vmid=9000, pool=config.pool, config_digest=config.digest
        )
        admission = evidence(time.time())
        admission["pve"].update(node=config.node, storage=config.storage)
        journal.event("admission", admission)
        self.token = APIToken("sim-build@pve!bootstrap", "00000000-1111-2222-3333-444444444444")
        self.exists = False
        self.posts = 0
        self.lose_response = False
        self.exitstatus = "OK"
        self.running = False
        self.matching_tasks = 1
        self.task_type = "qmcreate"
        self.content = []
        self.split_actor = False
        self.task_starttime = int(time.time())
        self.upid = (
            f"UPID:{config.node}:00000001:00000002:{self.task_starttime:08X}:"
            f"qmcreate:9000:{self.token.token_id}:"
        )
        self.config_data = dict(
            description=description(self.record),
            template=0,
            net0=f"virtio={config.guest_mac},bridge={config.bridge},firewall=1,link_down=1",
            kvm=1,
        )

    @property
    def create(self):
        return dict(
            vmid=9000,
            pool=self.config.pool,
            description=description(self.record),
            cores=1,
            sockets=1,
            memory=2048,
            balloon=0,
            cpu="host",
            kvm=1,
            onboot=0,
            start=0,
            net0=self.config_data["net0"],
        )

    def request(self, request):
        path = request.url.path
        data = None
        if request.method == "GET":
            if path.endswith("/cluster/resources"):
                data = (
                    [
                        dict(
                            node=self.config.node,
                            vmid=9000,
                            pool=self.config.pool,
                            status="stopped",
                            template=0,
                        )
                    ]
                    if self.exists
                    else []
                )
            elif path.endswith("/content"):
                data = self.content
            elif path.endswith("/config"):
                data = self.config_data
            elif path.endswith("/status/current"):
                data = {"status": "stopped"}
            elif path.endswith("/tasks"):
                data = []
                if request.url.params.get("source") == "all":
                    data = [
                        dict(
                            id="9000",
                            type=self.task_type,
                            user=(
                                self.token.token_id.split("!", 1)[0]
                                if self.split_actor
                                else self.token.token_id
                            ),
                            **(
                                {"tokenid": self.token.token_id.split("!", 1)[1]}
                                if self.split_actor
                                else {}
                            ),
                            starttime=(
                                int(time.time())
                                if self.task_starttime is None
                                else self.task_starttime
                            ),
                            upid=self.upid,
                        )
                    ] * self.matching_tasks
            elif "/tasks/" in path and path.endswith("/status"):
                data = dict(
                    status="running" if self.running else "stopped", exitstatus=self.exitstatus
                )
            elif "/tasks/" in path and path.endswith("/log"):
                data = [{"n": 1, "t": "reflected " + self.token.secret}]
        else:
            self.posts += 1
            pending = self.journal.pending()
            assert len(pending) == 1 and pending[0]["status"] == "intent"
            assert request.headers["Authorization"] == self.token.authorization
            self.exists = request.method != "DELETE"
            if self.lose_response:
                raise httpx.ReadTimeout("synthetic lost mutation response", request=request)
            data = self.upid
        return httpx.Response(200, json={"data": data})


@pytest.fixture
def lab(tmp_path):
    config = BuildConfig.load("examples/first-guest.toml")
    with Journal(tmp_path / "state") as journal:
        model = Lab(journal, config)
        api = BuildAPI(
            config,
            journal,
            model.token,
            transport=httpx.MockTransport(model.request),
            sleeper=lambda _: None,
        )
        try:
            yield model, api, journal
        finally:
            api.close()


def test_intent_precedes_mutation_and_task_log_is_redacted(lab):
    model, api, journal = lab
    op = api.mutate(
        "create", "POST", f"/nodes/{api.config.node}/qemu", model.create, postcondition=api.owned
    )
    assert journal.operation(op)["status"] == "complete"
    assert journal.operation(op)["upid"] == model.upid
    assert model.posts == 1
    events = " ".join(row[0] for row in journal.db.execute("SELECT body FROM events"))
    assert model.token.secret not in events and "[REDACTED]" in events
    assert api.simulated is True


def test_creation_cannot_skip_capacity_admission(lab):
    model, api, journal = lab
    journal.db.execute("DELETE FROM events WHERE kind='admission'")
    with pytest.raises(SafetyError, match="capacity evidence"):
        api.mutate(
            "create",
            "POST",
            f"/nodes/{api.config.node}/qemu",
            model.create,
            postcondition=api.owned,
        )
    assert model.posts == 0
    assert journal.pending() == []


def test_firewall_address_set_is_limited_to_the_recorded_nic(lab):
    model, api, _ = lab
    model.exists = True
    api._scope("POST", api.vm_path + "/firewall/ipset", {"name": "ipfilter-net0"})
    api._scope("POST", api.vm_path + "/firewall/ipset/ipfilter-net0", {"cidr": "10.77.0.10"})
    with pytest.raises(SafetyError):
        api._scope("POST", api.vm_path + "/firewall/ipset", {"name": "unrelated"})
    with pytest.raises(SafetyError):
        api._scope("POST", api.vm_path + "/firewall/ipset/ipfilter-net0", {"cidr": "0.0.0.0/0"})


def test_firewall_reorder_is_limited_to_four_owned_policy_rules(lab):
    model, api, _ = lab
    model.exists = True
    api._scope("PUT", api.vm_path + "/firewall/rules/3", {"moveto": 0, "digest": "simulated"})
    for position, params in [(4, {"moveto": 0}), (0, {"moveto": 4}), (0, {"action": "ACCEPT"})]:
        with pytest.raises(SafetyError):
            api._scope("PUT", api.vm_path + "/firewall/rules/" + str(position), params)


def test_lost_delete_response_reconciles_task_and_volume_absence(lab):
    model, api, journal = lab
    model.exists = True
    model.task_type = "qmdestroy"
    model.upid = model.upid.replace(":qmcreate:", ":qmdestroy:")
    model.lose_response = True
    with pytest.raises(SafetyError):
        api.mutate("delete", "DELETE", api.vm_path, {}, postcondition=api.deleted)
    operation = journal.pending()[0]
    assert model.exists is False
    api.reconcile(operation["id"], postcondition=api.deleted, expected_types={"qmdestroy"})
    assert journal.operation(operation["id"])["status"] == "complete"
    assert model.posts == 1


def test_reconcile_accepts_pve_separate_task_user_and_token_fields(lab):
    model, api, journal = lab
    model.split_actor = True
    model.lose_response = True
    with pytest.raises(SafetyError):
        api.mutate(
            "create",
            "POST",
            f"/nodes/{api.config.node}/qemu",
            model.create,
            postcondition=api.owned,
        )
    api.reconcile(journal.pending()[0]["id"], postcondition=api.owned, expected_types={"qmcreate"})
    assert model.posts == 1
    assert not journal.pending()
    attribution = events(journal, "upid-attribution")[0]
    assert attribution["source"] == "task-listing"
    assert attribution["upid"] == model.upid
    lookup = next(
        event
        for event in events(journal, "api-request-end")
        if event["request"] == attribution["request"]
    )
    assert lookup["method"] == "GET" and lookup["http_status"] == 200
    assert lookup["returned_upid"] is None


def test_absent_vm_with_remaining_recorded_volume_does_not_pass_cleanup(lab):
    model, api, journal = lab
    opid = journal.intent(
        "import", "OPERATOR", api.vm_path, {}, "root@pam", model.record["resource"]
    )
    journal.update(opid, "complete")
    volume = api.config.storage + ":vm-9000-disk-0"
    journal.record_volumes(model.record, opid, [volume])
    model.content = [{"volid": volume}]
    with pytest.raises(SafetyError, match="volumes remain"):
        api.deleted()


def test_lost_creation_response_is_reconciled_without_another_post(lab):
    model, api, journal = lab
    model.lose_response = True
    with pytest.raises(SafetyError, match="reconciliation"):
        api.mutate(
            "create",
            "POST",
            f"/nodes/{api.config.node}/qemu",
            model.create,
            postcondition=api.owned,
        )
    op = journal.pending()[0]
    assert op["status"] == "uncertain"
    with pytest.raises(SafetyError):
        api.mutate(
            "retry", "POST", f"/nodes/{api.config.node}/qemu", model.create, postcondition=api.owned
        )
    model.lose_response = False
    api.reconcile(op["id"], postcondition=api.owned, expected_types={"qmcreate"})
    assert model.posts == 1
    assert journal.operation(op["id"])["status"] == "complete"


@pytest.mark.parametrize("candidates", [0, 2])
def test_ambiguous_task_provenance_is_quarantined(lab, candidates):
    model, api, journal = lab
    model.lose_response = True
    with pytest.raises(SafetyError):
        api.mutate(
            "create",
            "POST",
            f"/nodes/{api.config.node}/qemu",
            model.create,
            postcondition=api.owned,
        )
    model.matching_tasks = candidates
    with pytest.raises(SafetyError, match="provenance"):
        api.reconcile(
            journal.pending()[0]["id"], postcondition=api.owned, expected_types={"qmcreate"}
        )
    assert model.posts == 1 and journal.pending()


def test_failed_task_retains_partial_resource_and_failure(lab):
    model, api, journal = lab
    model.exitstatus = "ERROR: synthetic failure"
    with pytest.raises(SafetyError, match="task failed"):
        api.mutate(
            "create",
            "POST",
            f"/nodes/{api.config.node}/qemu",
            model.create,
            postcondition=api.owned,
        )
    assert model.exists
    row = journal.db.execute("SELECT * FROM operations").fetchone()
    assert row["status"] == "failed" and row["upid"] == model.upid


def test_task_deadline_remains_uncertain_and_blocks_another_mutation(lab):
    model, api, journal = lab
    model.running = True
    clock = [0]
    api.clock = lambda: clock[0]
    api.sleep = lambda _: clock.__setitem__(0, clock[0] + 3)
    with pytest.raises(SafetyError, match="deadline"):
        api.mutate(
            "create",
            "POST",
            f"/nodes/{api.config.node}/qemu",
            model.create,
            postcondition=api.owned,
            deadline=2,
        )
    assert journal.pending()[0]["status"] == "uncertain"
    assert model.posts == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"kvm": 0},
        {"onboot": 1},
        {"memory": 8192},
        {"net0": "virtio=02:00:00:00:90:00,bridge=vmbr0,firewall=1,link_down=1"},
    ],
)
def test_unsafe_creation_never_reaches_server(lab, changes):
    model, api, journal = lab
    with pytest.raises(SafetyError):
        api.mutate(
            "unsafe",
            "POST",
            f"/nodes/{api.config.node}/qemu",
            model.create | changes,
            postcondition=api.owned,
        )
    assert model.posts == 0 and not journal.pending()


def test_delete_rechecks_ownership_volume_and_template_protection(lab):
    model, api, journal = lab
    model.exists = True
    for changes in (
        {"template": 1},
        {"description": "unrelated"},
        {"scsi0": "sim-rehearsal-lvm:unproven-volume,size=12G"},
    ):
        original = dict(model.config_data)
        model.config_data.update(changes)
        with pytest.raises(SafetyError):
            api.mutate(
                "delete",
                "DELETE",
                api.vm_path,
                {},
                postcondition=lambda: {"absent": api.live() is None},
            )
        model.config_data = original
    assert model.posts == 0


def test_boot_and_nic_release_require_isolation_gate(lab):
    model, api, journal = lab
    model.exists = True
    with pytest.raises(SafetyError, match="isolation"):
        api.mutate("start", "POST", api.vm_path + "/status/start", {}, postcondition=api.owned)
    with pytest.raises(SafetyError, match="isolation"):
        api.mutate(
            "link",
            "PUT",
            api.vm_path + "/config",
            {"net0": model.config_data["net0"].replace("link_down=1", "link_down=0")},
            postcondition=api.owned,
        )
    assert model.posts == 0


def test_other_vm_clone_and_template_endpoints_are_unavailable(lab):
    model, api, journal = lab
    model.exists = True
    for path in (
        api.vm_path + "/clone",
        api.vm_path + "/template",
        "/nodes/sim-pve01/qemu/9100/status/start",
    ):
        with pytest.raises(SafetyError, match="outside"):
            api.mutate("out-of-scope", "POST", path, {}, postcondition=api.owned)
    assert model.posts == 0


def events(journal, kind):
    return [
        json.loads(row[0])
        for row in journal.db.execute("SELECT body FROM events WHERE kind=? ORDER BY id", (kind,))
    ]


def create(api, model, label="create"):
    return api.mutate(
        label, "POST", f"/nodes/{api.config.node}/qemu", model.create, postcondition=api.owned
    )


def test_request_evidence_is_committed_before_dispatch_and_uses_monotonic_duration(
    lab, monkeypatch
):
    model, api, journal = lab
    monotonic = [50.0]
    utc = [100.0]
    api.clock = lambda: monotonic[0]
    api.utc_clock = lambda: utc[0]
    send = api.http.send

    def dispatch(request, **kwargs):
        if request.method == "POST":
            # A second connection checks durable visibility before the transport runs.
            with sqlite3.connect(journal.directory / "journal.sqlite3") as db:
                pending = db.execute("SELECT id,status FROM operations").fetchone()
                start = json.loads(
                    db.execute("SELECT body FROM events WHERE kind='api-request-start'").fetchone()[
                        0
                    ]
                )
            assert pending == (start["operation"], "intent")
            assert start["simulated"] is True
            uuid.UUID(start["request"])
            assert start["timing_context"] == api.timing_context
            monotonic[0] += 2.5
            utc[0] -= 10  # UTC correction must not turn elapsed time negative.
        return send(request, **kwargs)

    monkeypatch.setattr(api.http, "send", dispatch)
    opid = create(api, model)
    response = events(journal, "api-request-end")[0]
    assert response["operation"] == opid
    assert response["started_utc_epoch"] == 100 and response["ended_utc_epoch"] == 90
    assert response["elapsed_seconds"] == 2.5
    assert response["http_status"] == 200 and response["outcome"] == "response"
    assert response["returned_upid"] == model.upid
    attribution = events(journal, "upid-attribution")[0]
    assert attribution["source"] == "mutation-response"
    assert attribution["request"] == response["request"]
    requests = events(journal, "api-request-start")
    assert len({event["request"] for event in requests}) == len(requests)
    assert all(event["operation"] == opid for event in requests)


@pytest.mark.parametrize("status", [200, 302, 401, 403, 500])
def test_http_and_invalid_response_evidence_never_infers_task_failure(lab, monkeypatch, status):
    model, api, journal = lab
    send = api.http.send
    mutations = []

    def dispatch(request, **kwargs):
        if request.method == "POST":
            mutations.append(request)
            return httpx.Response(status, text=model.token.authorization, request=request)
        return send(request, **kwargs)

    monkeypatch.setattr(api.http, "send", dispatch)
    with pytest.raises(SafetyError):
        create(api, model)
    operation = journal.pending()[0]
    assert operation["status"] == "uncertain" and operation["upid"] is None
    response = events(journal, "api-request-end")[0]
    assert response["http_status"] == status
    assert response["outcome"] == ("invalid-response" if status == 200 else "http-error")
    assert response["returned_upid"] is None and response["transport_error"] is None
    assert model.token.secret not in " ".join(
        row[0] for row in journal.db.execute("SELECT body FROM events")
    )
    with pytest.raises(SafetyError, match="unresolved"):
        create(api, model, "retry")
    assert len(mutations) == 1


@pytest.mark.parametrize(
    "error,expected",
    [
        (httpx.ReadTimeout, "timeout"),
        (httpx.ConnectError, "http-transport"),
        (KeyboardInterrupt, None),
    ],
)
def test_transport_loss_and_interruption_preserve_unknown_outcome_without_secrets(
    lab, monkeypatch, error, expected
):
    model, api, journal = lab
    send = api.http.send

    def dispatch(request, **kwargs):
        if request.method == "POST":
            raise error(model.token.authorization)
        return send(request, **kwargs)

    monkeypatch.setattr(api.http, "send", dispatch)
    with pytest.raises(KeyboardInterrupt if error is KeyboardInterrupt else SafetyError):
        create(api, model)
    assert journal.pending()[0]["status"] == "uncertain"
    response = events(journal, "api-request-end")[0]
    assert response["http_status"] is None and response["returned_upid"] is None
    assert response["transport_error"] == expected
    assert response["outcome"] == (
        "interrupted" if error is KeyboardInterrupt else "transport-error"
    )
    assert model.token.secret not in json.dumps(events(journal, "api-request-end"))
    assert events(journal, "upid-attribution") == []


def test_response_evidence_survives_crash_before_upid_attachment(lab, monkeypatch):
    model, api, journal = lab
    update = journal.update

    def crash(opid, status, **kwargs):
        if kwargs.get("upid"):
            raise RuntimeError("synthetic crash after receiving response")
        return update(opid, status, **kwargs)

    monkeypatch.setattr(journal, "update", crash)
    with pytest.raises(RuntimeError):
        create(api, model)
    original = journal.pending()[0]
    assert original["status"] == "intent" and original["upid"] is None
    journal.close()
    with Journal(journal.directory) as reopened:
        assert reopened.operation(original["id"]) == original
        assert events(reopened, "api-request-end")[0]["returned_upid"] == model.upid
        assert events(reopened, "upid-attribution") == []
        with pytest.raises(SafetyError, match="unresolved"):
            reopened.intent("retry", "POST", api.vm_path, {}, model.token.token_id)
        model.journal = reopened
        model.matching_tasks = 0  # Recovery must use the durable response, not discovery.
        recovered = BuildAPI(
            api.config,
            reopened,
            model.token,
            transport=httpx.MockTransport(model.request),
            clock=lambda: 1.0,
        )
        try:
            with pytest.raises(SafetyError, match="active lease"):
                recovered.reconcile(
                    original["id"], postcondition=recovered.owned, expected_types={"qmcreate"}
                )
            expires = reopened.db.execute("SELECT max(expires) FROM lease").fetchone()[0]
            monkeypatch.setattr("rehearsal_build.journal.time.time", lambda: expires + 1)
            recovered.reconcile(
                original["id"], postcondition=recovered.owned, expected_types={"qmcreate"}
            )
        finally:
            recovered.close()
        assert reopened.operation(original["id"])["status"] == "complete"
        attribution = events(reopened, "upid-attribution")[0]
        assert attribution["source"] == "mutation-response"
        assert attribution["request"] == events(reopened, "api-request-end")[0]["request"]
        recorded = events(reopened, "api-request-end")
        assert recorded[0]["timing_context"] != recorded[1]["timing_context"]
        assert recorded[1]["started_monotonic_seconds"] == 1.0
        assert recorded[1]["elapsed_seconds"] == 0.0
    assert model.posts == 1


@pytest.mark.parametrize("exitstatus", ["OK", "ERROR: reflected secret", None, ""])
def test_task_outcome_survives_missing_logs_and_missing_exitstatus_is_unknown(
    lab, monkeypatch, exitstatus
):
    model, api, journal = lab
    model.exitstatus = (
        exitstatus.replace("secret", model.token.secret) if exitstatus else exitstatus
    )
    send = api.http.send
    logs = []

    def dispatch(request, **kwargs):
        if request.url.path.endswith("/log"):
            logs.append(request)
            raise httpx.ReadTimeout(model.token.authorization, request=request)
        return send(request, **kwargs)

    monkeypatch.setattr(api.http, "send", dispatch)
    with pytest.raises(SafetyError):
        create(api, model)
    operation = dict(journal.db.execute("SELECT * FROM operations").fetchone())
    failed = bool(exitstatus and exitstatus != "OK")
    assert operation["status"] == ("failed" if failed else "uncertain")
    assert operation["upid"] == model.upid
    observation = events(journal, "task-observation")[0]
    assert observation["status"] == "stopped"
    assert observation["exitstatus"] == ("ERROR: reflected [REDACTED]" if failed else exitstatus)
    status_response = next(
        event
        for event in events(journal, "api-request-end")
        if event["request"] == observation["request"]
    )
    assert status_response["path"].endswith("/status")
    assert status_response["http_status"] == 200
    assert len(logs) == (1 if exitstatus else 0)
    assert not events(journal, "task-terminal")
    assert model.token.secret not in json.dumps(events(journal, "task-observation"))


def test_stopped_resource_and_missing_historical_task_do_not_settle_start(lab, monkeypatch):
    model, api, journal = lab
    model.exists = True
    model.upid = model.upid.replace(":qmcreate:", ":qmstart:")
    journal.resource_state("isolated", {"simulated": True})
    send = api.http.send

    def dispatch(request, **kwargs):
        if "/tasks/" in request.url.path:
            return httpx.Response(500, json={"message": "no such task"}, request=request)
        return send(request, **kwargs)

    monkeypatch.setattr(api.http, "send", dispatch)
    with pytest.raises(SafetyError):
        api.mutate("start", "POST", api.vm_path + "/status/start", {}, postcondition=api.owned)
    assert api.live()["status"] == "stopped"
    assert journal.pending()[0]["status"] == "uncertain"
    assert journal.pending()[0]["upid"] == model.upid
    assert not events(journal, "task-observation")
    assert events(journal, "api-request-end")[-1]["http_status"] == 500
    assert model.posts == 1


@pytest.mark.parametrize("failure_at", ["api-request-start", "api-request-end"])
def test_evidence_write_failure_never_allows_blind_resubmission(lab, monkeypatch, failure_at):
    model, api, journal = lab
    event = journal.event

    def persist(kind, body):
        if kind == failure_at:
            raise OSError("synthetic evidence disk failure")
        event(kind, body)

    monkeypatch.setattr(journal, "event", persist)
    with pytest.raises(OSError):
        create(api, model)
    assert model.posts == (0 if failure_at == "api-request-start" else 1)
    assert journal.pending()[0]["status"] == "uncertain"
    with pytest.raises(SafetyError, match="unresolved"):
        create(api, model, "retry")
    assert model.posts == (0 if failure_at == "api-request-start" else 1)


@pytest.mark.parametrize("record_start", [False, True])
def test_missing_request_evidence_cannot_adopt_a_later_task(lab, monkeypatch, record_start):
    model, api, journal = lab
    opid = journal.intent(
        "interrupted",
        "POST",
        f"/nodes/{api.config.node}/qemu",
        model.create,
        model.token.token_id,
        model.record["resource"],
    )
    if record_start:
        journal.event(
            "api-request-start",
            {
                "operation": opid,
                "method": "POST",
                "path": f"/nodes/{api.config.node}/qemu",
                "request": str(uuid.uuid4()),
                "timing_context": str(uuid.uuid4()),
            },
        )
    monkeypatch.setattr(api.http, "send", lambda *_args, **_kwargs: pytest.fail("task discovery"))
    with pytest.raises(SafetyError, match="provenance"):
        api.reconcile(opid, postcondition=api.owned, expected_types={"qmcreate"})
    assert journal.operation(opid)["status"] == "intent"
    assert journal.operation(opid)["upid"] is None


def test_task_discovery_rejects_a_task_outside_the_request_window(lab):
    model, api, journal = lab
    model.lose_response = True
    with pytest.raises(SafetyError):
        create(api, model)
    model.task_starttime = int(time.time()) + 3600
    opid = journal.pending()[0]["id"]
    with pytest.raises(SafetyError, match="provenance"):
        api.reconcile(opid, postcondition=api.owned, expected_types={"qmcreate"})
    assert journal.operation(opid)["upid"] is None and model.posts == 1


def test_task_discovery_refuses_a_backwards_utc_interval(lab):
    model, api, journal = lab
    utc = iter([100.0, 90.0])
    api.utc_clock = lambda: next(utc)
    model.lose_response = True
    with pytest.raises(SafetyError):
        create(api, model)
    with pytest.raises(SafetyError, match="UTC clock discontinuity"):
        api.reconcile(
            journal.pending()[0]["id"], postcondition=api.owned, expected_types={"qmcreate"}
        )
    assert model.posts == 1 and journal.pending()


def test_task_listing_timestamp_must_match_the_upid_timestamp(lab):
    model, api, journal = lab
    model.lose_response = True
    with pytest.raises(SafetyError):
        create(api, model)
    fields = model.upid.split(":")
    fields[4] = "00000003"  # Contradicts the fresh starttime in the listing row.
    model.upid = ":".join(fields)
    with pytest.raises(SafetyError, match="timestamps disagree"):
        api.reconcile(
            journal.pending()[0]["id"], postcondition=api.owned, expected_types={"qmcreate"}
        )
    assert journal.pending()[0]["upid"] is None and model.posts == 1


@pytest.mark.parametrize(
    "old,new",
    [
        (":9000:", ":9100:"),
        (":qmcreate:", ":qmstop:"),
        ("sim-build@pve!bootstrap", "other@pve!token"),
    ],
)
def test_response_upid_must_match_the_original_mutation(lab, old, new):
    model, api, journal = lab
    model.upid = model.upid.replace(old, new)
    with pytest.raises(SafetyError, match="provenance"):
        create(api, model)
    assert model.posts == 1
    assert journal.pending()[0]["status"] == "uncertain"
    assert journal.pending()[0]["upid"] == model.upid  # Retain what was actually received.


def test_transport_exception_has_no_secret_bearing_context(lab, monkeypatch):
    model, api, journal = lab
    send = api.http.send

    def dispatch(request, **kwargs):
        if request.method == "POST":
            raise httpx.ReadTimeout(model.token.authorization, request=request)
        return send(request, **kwargs)

    monkeypatch.setattr(api.http, "send", dispatch)
    with pytest.raises(SafetyError) as caught:
        create(api, model)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert model.token.secret not in "".join(traceback.format_exception(caught.value))
    assert model.token.secret not in json.dumps(events(journal, "api-request-end"))


def test_redaction_handles_other_credentials_and_nested_fields(lab):
    model, api, _ = lab
    other = "SYNTHETIC-OTHER-CREDENTIAL"
    response = {
        "Authorization": "Bearer " + other,
        "nested": {"token_secret": other, "safe": "retained"},
        "logs": [
            "Authorization: Basic " + other,
            "password=" + other,
            "-----BEGIN OPENSSH PRIVATE KEY-----\n" + other + "\n-----END OPENSSH PRIVATE KEY-----",
        ],
        "escaped": model.token.secret,
    }
    sanitized = api.sanitize(response)
    assert other not in json.dumps(sanitized)
    assert model.token.secret not in json.dumps(sanitized)
    assert sanitized["nested"] == {"safe": "retained"}
    assert sanitized["logs"] == ["[REDACTED]"]


def test_private_key_split_across_log_records_is_not_partially_retained(lab):
    _, api, _ = lab
    log = [
        {"n": 1, "t": "-----BEGIN OPENSSH PRIVATE KEY-----"},
        {"n": 2, "t": "SYNTHETIC-KEY-BODY"},
        {"n": 3, "t": "-----END OPENSSH PRIVATE KEY-----"},
    ]
    assert api.sanitize({"log": log}) == {"log": ["[REDACTED]"]}


@pytest.mark.parametrize("field", ["label", "params"])
def test_active_secret_in_mutation_input_is_rejected_before_journaling(lab, field):
    model, api, journal = lab
    label, params = "create", model.create
    if field == "label":
        label = model.token.secret
    else:
        params = params | {"sshkeys": model.token.secret}
    with pytest.raises(SafetyError, match="secret-bearing"):
        api.mutate(label, "POST", f"/nodes/{api.config.node}/qemu", params, postcondition=api.owned)
    assert not journal.pending() and model.posts == 0


@pytest.mark.parametrize(
    "path",
    [
        "https://example.invalid/collect",
        "//example.invalid/collect",
        "/../outside",
        "/nodes/%2e%2e/outside",
        "/nodes/\\outside",
        "/version?credential=synthetic",
    ],
)
def test_read_cannot_send_authorization_to_another_origin(lab, monkeypatch, path):
    _, api, _ = lab
    monkeypatch.setattr(api.http, "send", lambda *_args, **_kwargs: pytest.fail("HTTP request"))
    with pytest.raises(SafetyError, match="configured origin"):
        api.read(path)


@pytest.mark.parametrize("oversized", [False, True])
def test_partial_response_keeps_http_status_and_closes_stream_without_logging_body(
    lab, monkeypatch, oversized
):
    model, api, journal = lab
    send = api.http.send
    closed = []

    class Body(httpx.SyncByteStream):
        def __iter__(self):
            yield model.token.authorization.encode()
            if oversized:
                yield b"x" * (2 * 1024**2)
            else:
                raise httpx.ReadTimeout(model.token.authorization)

        def close(self):
            closed.append(True)

    def dispatch(request, **kwargs):
        if request.method == "POST":
            return httpx.Response(200, stream=Body(), request=request)
        return send(request, **kwargs)

    monkeypatch.setattr(api.http, "send", dispatch)
    with pytest.raises(SafetyError) as caught:
        create(api, model)
    assert closed
    response = events(journal, "api-request-end")[0]
    assert response["http_status"] == 200
    assert response["outcome"] == ("invalid-response" if oversized else "transport-error")
    assert journal.pending()[0]["status"] == "uncertain"
    assert caught.value.__context__ is None
    assert model.token.secret not in json.dumps(response)
