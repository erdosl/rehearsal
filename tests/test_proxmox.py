"""All endpoints/credentials below are synthetic; transport never opens a socket."""

import json
import logging
import ssl
import traceback
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from rehearsal.cli import _human, main
from rehearsal.config import Config, ProxmoxConfig, load_config
from rehearsal.credentials import load_token
from rehearsal.errors import ConfigError, InventoryError
from rehearsal.providers.proxmox import MAX_RESPONSE_BYTES, ProxmoxProvider

TOKEN_ID = "rehearsal@pve!inventory"
SECRET = "11111111-2222-3333-4444-555555555555"  # intentionally fake


@pytest.fixture
def live_config(tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({"token_id": TOKEN_ID, "token_secret": SECRET}))
    token_file.chmod(0o600)
    return Config(
        tmp_path,
        ("pve01",),
        None,
        ProxmoxConfig("https://pve.example.invalid:8006", token_file=token_file),
    )


@pytest.fixture
def responses():
    return {
        "version": {"version": "9.2.2", "release": "9.2", "repoid": "synthetic"},
        "nodes/pve01/status": {"cpuinfo": {"cpus": 2}, "memory": {"total": 12 * 2**30}},
        "nodes/pve01/storage": [
            {
                "storage": "rehearsal-lvm",
                "type": "lvmthin",
                "active": 1,
                "total": 90 * 2**30,
                "used": 0,
                "avail": 90 * 2**30,
                "content": "images,rootdir",
            }
        ],
        "nodes/pve01/qemu": [
            {
                "vmid": 9000,
                "name": "synthetic-template",
                "status": "stopped",
                "template": 1,
                "description": "must not export raw configuration",
            }
        ],
        "nodes/pve01/network": [
            {
                "iface": "vmbr0",
                "type": "bridge",
                "active": True,
                "address": "192.0.2.80",
                "netmask": "255.255.255.0",
                "bridge_ports": "nic0",
                "cidr6": "2001:db8::80/64",
            }
        ],
    }


def provider(config, handler, **kwargs):
    return ProxmoxProvider(
        config, transport=httpx.MockTransport(handler), sleep=lambda _: None, **kwargs
    )


def route(request):
    assert request.method == "GET"
    assert request.url.scheme == "https"
    assert request.url.host == "pve.example.invalid"
    assert not request.url.query
    assert request.headers["Authorization"] == f"PVEAPIToken={TOKEN_ID}={SECRET}"
    return request.url.path.removeprefix("/api2/json/")


def test_success_get_only_typed_inventory(live_config, responses):
    seen = []

    def handler(request):
        key = route(request)
        seen.append(key)
        assert request.extensions["timeout"] == {"connect": 3, "read": 15, "write": 15, "pool": 3}
        return httpx.Response(200, json={"data": responses[key]})

    result = provider(live_config, handler).inventory()
    assert seen == list(responses)
    assert result.backend == "live" and result.simulated is True  # injected test transport
    assert result.complete is True
    assert {q.status for q in result.coverage} == {"queried"}
    assert result.storage[0].total_bytes == 90 * 2**30
    assert result.storage[0].content == ("images", "rootdir")
    assert result.vms[0].template is True
    assert result.networks[0].cidr == "192.0.2.80/24"
    assert result.networks[0].cidr6 == "2001:db8::80/64"
    assert "description" not in result.to_dict()["vms"][0]
    assert _human(result).startswith("SIMULATED live-adapter transport test")


@pytest.mark.parametrize(
    "status,code,attempts",
    [
        (401, "authentication_failed", 1),
        (403, "permission_denied", 1),
        (404, "http_error", 1),
        (500, "http_error", 1),
        (302, "http_error", 1),
        (429, "unavailable", 1),
        (502, "unavailable", 3),
        (503, "unavailable", 3),
        (504, "unavailable", 3),
    ],
)
def test_status_classification_and_retry_limits(live_config, status, code, attempts, caplog):
    seen = []
    caplog.set_level(logging.DEBUG)

    def handler(request):
        seen.append(route(request))
        return httpx.Response(status, text=SECRET, headers={"Location": "https://other.invalid/"})

    with pytest.raises(InventoryError) as error:
        provider(live_config, handler).inventory()
    assert error.value.code == code
    assert len(seen) == attempts and set(seen) == {"version"}
    rendered = "".join(traceback.format_exception(error.value)) + caplog.text
    assert SECRET not in rendered and TOKEN_ID not in rendered
    assert error.value.__context__ is None and error.value.__cause__ is None


@pytest.mark.parametrize(
    "exception,code",
    [
        (httpx.ConnectTimeout, "timeout"),
        (httpx.ReadTimeout, "timeout"),
        (httpx.ConnectError, "connectivity_error"),
        (httpx.ReadError, "connectivity_error"),
        (httpx.RemoteProtocolError, "connectivity_error"),
    ],
)
def test_transient_transport_failures_are_bounded_and_safe(live_config, exception, code):
    seen = []

    def handler(request):
        seen.append(route(request))
        raise exception(SECRET, request=request)

    with pytest.raises(InventoryError) as error:
        provider(live_config, handler).inventory()
    assert error.value.code == code and len(seen) == 3
    assert error.value.__context__ is None
    assert SECRET not in "".join(traceback.format_exception(error.value))


def test_tls_failure_is_not_retried_and_preserves_no_raw_cause(live_config):
    seen = []

    def handler(request):
        seen.append(route(request))
        raise httpx.ConnectError(SECRET, request=request) from ssl.SSLCertVerificationError(
            "certificate identity mismatch " + SECRET
        )

    with pytest.raises(InventoryError) as error:
        provider(live_config, handler).inventory()
    assert error.value.code == "tls_error" and len(seen) == 1
    assert error.value.__context__ is None
    assert SECRET not in "".join(traceback.format_exception(error.value))


def test_tls_context_checks_ca_and_san_identity(live_config):
    ca_path = Path(ssl.get_default_verify_paths().cafile)
    config = replace(live_config, proxmox=replace(live_config.proxmox, ca_file=ca_path))
    instance = provider(config, lambda _: httpx.Response(500))
    assert instance.context.check_hostname is True
    assert instance.context.verify_mode == ssl.CERT_REQUIRED
    assert instance.context.hostname_checks_common_name is False
    assert instance.context.get_ca_certs()
    assert instance.simulated is True
    assert ProxmoxProvider(live_config).simulated is False  # constructor opens no network


def test_missing_ca_fails_before_credentials_or_network(live_config):
    config = replace(
        live_config,
        proxmox=replace(
            live_config.proxmox, ca_file=live_config.directory / "absent-ca.crt", token_file=None
        ),
    )
    with pytest.raises(InventoryError) as error:
        provider(config, lambda _: pytest.fail("request must not be sent"))
    assert error.value.code == "tls_error"
    assert error.value.__context__ is None


def test_retry_can_recover_and_backoff_is_bounded(live_config, responses):
    seen, delays = [], []

    def handler(request):
        key = route(request)
        seen.append(key)
        return (
            httpx.Response(503)
            if len(seen) < 3
            else httpx.Response(200, json={"data": responses[key]})
        )

    result = ProxmoxProvider(
        live_config, transport=httpx.MockTransport(handler), sleep=delays.append
    ).inventory()
    assert result.complete and seen[:3] == ["version"] * 3
    assert len(delays) == 2 and all(0 < delay <= 1 for delay in delays)


def test_request_deadline_stops_new_attempts(live_config):
    now = [0.0]
    seen = []
    options = replace(live_config.proxmox, request_deadline_seconds=0.1)

    def handler(request):
        seen.append(route(request))
        assert request.extensions["timeout"]["read"] <= 0.1
        now[0] = 1.0
        raise httpx.ConnectTimeout(SECRET, request=request)

    with pytest.raises(InventoryError) as error:
        provider(replace(live_config, proxmox=options), handler, clock=lambda: now[0]).inventory()
    assert error.value.code == "timeout" and len(seen) == 1


def test_inaccessible_node_is_failed_not_successfully_empty(live_config, responses):
    seen = []

    def handler(request):
        key = route(request)
        seen.append(key)
        if key == "nodes/inaccessible/status":
            return httpx.Response(403)
        return httpx.Response(200, json={"data": responses[key]})

    config = replace(live_config, nodes=("pve01", "inaccessible"))
    result = provider(config, handler).inventory()
    assert not result.complete
    assert [node.name for node in result.nodes] == ["pve01"]
    assert [
        (q.section, q.status, q.error_code) for q in result.coverage if q.node == "inaccessible"
    ] == [
        ("nodes", "failed", "permission_denied"),
        ("storage", "not_queried", "node_unavailable"),
        ("vms", "not_queried", "node_unavailable"),
        ("networks", "not_queried", "node_unavailable"),
    ]
    assert "nodes/inaccessible/storage" not in seen
    assert "PARTIAL" in _human(result)


@pytest.mark.parametrize(
    "section,endpoint", [("storage", "storage"), ("vms", "qemu"), ("networks", "network")]
)
def test_section_permission_failure_preserves_other_results(
    live_config, responses, section, endpoint
):
    seen = []

    def handler(request):
        key = route(request)
        seen.append(key)
        if key == f"nodes/pve01/{endpoint}":
            return httpx.Response(403, text=SECRET)
        return httpx.Response(200, json={"data": responses[key]})

    result = provider(live_config, handler).inventory()
    assert not result.complete
    assert [q.section for q in result.coverage if q.status == "failed"] == [section]
    assert all(q.status == "queried" for q in result.coverage if q.section != section)
    assert seen.count(f"nodes/pve01/{endpoint}") == 1
    assert SECRET not in json.dumps(result.to_dict())


def test_empty_acl_filtered_lists_and_unknown_capacity_are_explicit(live_config, responses):
    responses["nodes/pve01/qemu"] = []
    responses["nodes/pve01/storage"] = [{"storage": "offline", "type": "dir", "active": 0}]
    result = provider(
        live_config, lambda r: httpx.Response(200, json={"data": responses[route(r)]})
    ).inventory()
    assert result.complete and not result.vms
    assert result.storage[0].total_bytes is None
    assert "ACL-filtered" in result.visibility
    assert "capacity unknown" in _human(result)


@pytest.mark.parametrize(
    "content",
    [
        b"not JSON",
        b"{}",
        b'{"data": null}',
        b'{"data":{"version":"x"},"data":{}}',
        b'"wrong"',
        b"\xff",
        b"x" * (MAX_RESPONSE_BYTES + 1),
    ],
)
def test_malformed_version_response_is_not_retried(live_config, content):
    seen = []

    def handler(request):
        seen.append(route(request))
        return httpx.Response(200, content=content)

    with pytest.raises(InventoryError) as error:
        provider(live_config, handler).inventory()
    assert error.value.code == "malformed_response" and len(seen) == 1


def test_malformed_section_is_partial_and_does_not_leak_payload(live_config, responses):
    responses["nodes/pve01/storage"][0]["used"] = -1
    result = provider(
        live_config, lambda r: httpx.Response(200, json={"data": responses[route(r)]})
    ).inventory()
    assert not result.complete and not result.storage
    assert (
        next(q for q in result.coverage if q.section == "storage").error_code
        == "malformed_response"
    )


def test_reflected_secrets_are_redacted_even_when_json_escaped(live_config, responses, caplog):
    caplog.set_level(logging.DEBUG)
    responses["nodes/pve01/qemu"][0]["name"] = SECRET

    def handler(request):
        # Only escape string values: numeric values must retain their JSON types.
        if route(request) != "nodes/pve01/qemu":
            return httpx.Response(200, json={"data": responses[route(request)]})
        body = json.dumps({"data": responses[route(request)]}).replace(
            SECRET, SECRET.replace("1", "\\u0031")
        )
        return httpx.Response(200, content=body.encode())

    result = provider(live_config, handler).inventory()
    assert result.vms[0].name == "[REDACTED]"
    assert SECRET not in json.dumps(result.to_dict()) + _human(result) + caplog.text


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o700])
def test_token_file_permissions_are_enforced(live_config, mode):
    live_config.proxmox.token_file.chmod(mode)
    with pytest.raises(InventoryError) as error:
        load_token(live_config.proxmox.token_file)
    assert error.value.code == "credentials_error"
    assert SECRET not in str(error.value)


def test_token_file_rejects_symlink_and_bad_json_without_echo(live_config):
    path = live_config.proxmox.token_file
    assert SECRET not in repr(load_token(path))
    link = path.with_name("link")
    link.symlink_to(path)
    for selected in (link, None, path.parent / "absent"):
        with pytest.raises(InventoryError) as error:
            load_token(selected)
        assert error.value.code == "credentials_error" and error.value.__context__ is None
    for payload in (
        SECRET,
        '{"token_secret":"' + SECRET + '","token_secret":"duplicate"}',
        '{"token_id":"x","token_secret":"' + SECRET + '"}',
        "x" * 4097,
    ):
        path.write_text(payload)
        with pytest.raises(InventoryError) as error:
            load_token(path)
        assert SECRET not in "".join(traceback.format_exception(error.value))
        assert error.value.__context__ is None


@pytest.mark.parametrize("flag,environment", [(False, None), (True, None), (False, "1")])
def test_live_gate_precedes_any_credentials_or_transport(
    config_path, monkeypatch, capsys, flag, environment
):
    monkeypatch.delenv("REHEARSAL_LIVE", raising=False)
    if environment:
        monkeypatch.setenv("REHEARSAL_LIVE", environment)
    monkeypatch.setattr("rehearsal.cli.ProxmoxProvider", lambda _: pytest.fail("gate bypassed"))
    args = ["inventory", "--config", str(config_path), "--backend", "live", "--format", "json"]
    assert main(args + (["--live"] if flag else [])) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert json.loads(captured.err)["backend"] == "live"


def test_cli_partial_live_report_is_nonzero_and_never_fixture_fallback(
    live_config, responses, monkeypatch, capsys
):
    path = live_config.directory / "live.toml"
    path.write_text(
        'schema_version=1\n[inventory]\nnodes=["pve01"]\n[proxmox]\n'
        'endpoint="https://pve.example.invalid:8006"\ntoken_file="token.json"\n'
    )
    monkeypatch.setenv("REHEARSAL_LIVE", "1")

    def handler(request):
        key = route(request)
        return (
            httpx.Response(403)
            if key.endswith("/storage")
            else httpx.Response(200, json={"data": responses[key]})
        )

    monkeypatch.setattr("rehearsal.cli.ProxmoxProvider", lambda config: provider(config, handler))
    assert (
        main(
            ["inventory", "--config", str(path), "--backend", "live", "--live", "--format", "json"]
        )
        == 4
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert not data["complete"] and data["backend"] == "live" and data["simulated"] is True
    assert not captured.err
    assert load_config(path).fixture is None


def test_rejected_command_line_secrets_are_not_echoed(config_path, capsys):
    with pytest.raises(SystemExit) as error:
        main(["inventory", "--config", str(config_path), "--backend", "live", "--token", SECRET])
    assert error.value.code == 2
    assert SECRET not in capsys.readouterr().err


def test_client_disables_redirects_and_environment_overrides(live_config, responses, monkeypatch):
    original = httpx.Client
    seen = []

    def checked_client(**kwargs):
        seen.append(kwargs)
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        assert kwargs["verify"].check_hostname is True
        assert kwargs["verify"].verify_mode == ssl.CERT_REQUIRED
        assert kwargs["headers"]["Accept-Encoding"] == "identity"
        return original(**kwargs)

    monkeypatch.setattr(httpx, "Client", checked_client)
    result = provider(
        live_config, lambda r: httpx.Response(200, json={"data": responses[route(r)]})
    ).inventory()
    assert result.complete and len(seen) == 1


def test_body_deadline_stops_slow_chunks_and_closes_response(live_config):
    now, closed = [0.0], []

    class SlowBody(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"data":'
            now[0] = 31.0
            yield b'{"version":"9.2.2"}}'

        def close(self):
            closed.append(True)

    with pytest.raises(InventoryError) as error:
        provider(
            live_config, lambda _: httpx.Response(200, stream=SlowBody()), clock=lambda: now[0]
        ).inventory()
    assert error.value.code == "timeout" and closed


def test_fixture_backend_rejects_live_flags_and_live_ignores_no_fixture(
    live_config, config_path, capsys
):
    assert main(["inventory", "--config", str(config_path), "--backend", "fixture", "--live"]) == 2
    assert not capsys.readouterr().out


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://💩.example.invalid",
        "http://pve.example.invalid",
        "https://user:password@pve.example.invalid",
        "https://pve.example.invalid/api2/json",
        "https://pve.example.invalid?token=wrong",
        "https://pve.example.invalid#fragment",
    ],
)
def test_unsupported_url_fails_safely_before_reading_token(live_config, endpoint):
    options = replace(live_config.proxmox, endpoint=endpoint, token_file=None)
    with pytest.raises(ConfigError) as error:
        provider(replace(live_config, proxmox=options), lambda _: pytest.fail("unexpected request"))
    assert error.value.__context__ is None
