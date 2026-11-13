"""Bounded GET-only PVE inventory. No resource mutation or fixture fallback."""

import ipaddress
import json
import random
import ssl
import time
from collections.abc import Callable

import httpx

from rehearsal.config import Config, ProxmoxConfig
from rehearsal.credentials import load_token
from rehearsal.errors import ConfigError, InventoryError
from rehearsal.inventory import VM, Coverage, Inventory, Network, Node, Storage

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
RETRY_STATUSES = {502, 503, 504}
MESSAGES = {
    "authentication_failed": "API authentication rejected; check the dedicated token",
    "permission_denied": "API permission denied; check user and token ACLs",
    "tls_error": "TLS verification/negotiation failed; check CA trust and certificate identity",
    "connectivity_error": "cannot communicate with the configured API endpoint",
    "timeout": "API request exceeded a timeout or deadline",
    "http_error": "API returned an unexpected HTTP status; redirects are not followed",
    "unavailable": "API is temporarily unavailable or rate limited",
    "malformed_response": "API response does not satisfy the inventory contract",
}


def _error(code: str) -> InventoryError:
    return InventoryError(code, MESSAGES[code])


def _tls_failure(error: BaseException) -> bool:
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(error).upper():
            return True
        error = error.__cause__ or error.__context__
    return False


def _tls_context(config: ProxmoxConfig) -> ssl.SSLContext:
    if config.verify_tls is not True:
        raise ConfigError("TLS verification must remain enabled")
    context = None
    try:
        context = ssl.create_default_context(cafile=config.ca_file)
    except (OSError, ssl.SSLError, ValueError):
        pass
    if context is None:
        raise _error("tls_error")
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.hostname_checks_common_name = False
    return context


def _object(value: object) -> dict:
    if not isinstance(value, dict):
        raise _error("malformed_response")
    return value


def _text(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 256
        or any(not c.isprintable() for c in value)
    ):
        raise _error("malformed_response")
    return value


def _number(value: object, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= 2**63 - 1:
        raise _error("malformed_response")
    return value


def _flag(value: object) -> bool | None:
    if value is None:
        return None
    if type(value) is bool or type(value) is int and value in (0, 1):
        return bool(value)
    raise _error("malformed_response")


def _rows(data: object) -> list[dict]:
    if not isinstance(data, list):
        raise _error("malformed_response")
    return [_object(row) for row in data]


def _unique(rows: list, key: Callable) -> list:
    values = [key(row) for row in rows]
    if len(values) != len(set(values)):
        raise _error("malformed_response")
    return rows


def _node(data: object, node: str) -> list[Node]:
    data = _object(data)
    return [
        Node(
            node,
            "online",
            _number(_object(data.get("cpuinfo")).get("cpus"), 1),
            _number(_object(data.get("memory")).get("total"), 1),
        )
    ]


def _storage(data: object, node: str) -> list[Storage]:
    result = []
    for row in _rows(data):
        capacity = [row.get(name) for name in ("total", "used", "avail")]
        if any(value is not None for value in capacity):
            capacity = [_number(value) for value in capacity]
            if capacity[1] + capacity[2] > capacity[0]:
                raise _error("malformed_response")
        content = row.get("content", "")
        if not isinstance(content, str):
            raise _error("malformed_response")
        result.append(
            Storage(
                node,
                _text(row.get("storage")),
                _text(row.get("type")),
                _flag(row.get("active")),
                *capacity,
                content=tuple(_text(item) for item in content.split(",") if item),
            )
        )
    return _unique(result, lambda row: row.name)


def _vms(data: object, node: str) -> list[VM]:
    result = []
    for row in _rows(data):
        vmid = _number(row.get("vmid"), 100)
        status = _text(row.get("status"))
        if status not in {"running", "stopped", "paused", "unknown"}:
            raise _error("malformed_response")
        template = _flag(row.get("template", 0))
        if template is None:
            raise _error("malformed_response")
        result.append(VM(node, vmid, _text(row.get("name") or f"vm-{vmid}"), status, template))
    return _unique(result, lambda row: row.vmid)


def _cidr(row: dict, suffix: str = "") -> str | None:
    value = row.get("cidr" + suffix)
    if value is None and row.get("address" + suffix):
        address = row["address" + suffix]
        mask = row.get("netmask" + suffix)
        if not isinstance(address, str) or mask is None and "/" not in address:
            raise _error("malformed_response")
        value = address if "/" in address else f"{address}/{mask}"
    if value is not None:
        value = _text(value)
        valid = True
        try:
            value = str(ipaddress.ip_interface(value))
        except ValueError:
            valid = False
        if not valid:
            raise _error("malformed_response")
    return value


def _networks(data: object, node: str) -> list[Network]:
    result = []
    for row in _rows(data):
        ports = row.get("bridge_ports") or row.get("ovs_ports") or row.get("bond_slaves") or ""
        if not isinstance(ports, str):
            raise _error("malformed_response")
        result.append(
            Network(
                node,
                _text(row.get("iface")),
                _text(row.get("type", "unknown")),
                _flag(row.get("active")),
                _cidr(row),
                tuple(_text(p) for p in ports.split()),
                cidr6=_cidr(row, "6"),
            )
        )
    return _unique(result, lambda row: row.name)


def _unique_json(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite JSON number")


class ProxmoxProvider:
    def __init__(
        self,
        config: Config,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if config.proxmox is None:
            raise ConfigError("live inventory requires a proxmox configuration table")
        self.config = config
        self.options = config.proxmox
        supported_url = True
        try:
            url = httpx.URL(self.options.endpoint)
            supported_url = (
                url.scheme == "https"
                and bool(url.host)
                and not url.username
                and not url.password
                and not url.query
                and not url.fragment
                and url.path == "/"
            )
        except (httpx.InvalidURL, ValueError):
            supported_url = False
        if not supported_url:
            raise ConfigError("API endpoint is not a supported HTTPS URL")
        self.context = _tls_context(self.options)
        self._token = load_token(self.options.token_file)
        self.simulated = transport is not None
        self._transport = transport
        self._sleep = sleep
        self._clock = clock

    def _scrub(self, value: object) -> object:
        if isinstance(value, str):
            return self._token.redact(value)
        if isinstance(value, list):
            return [self._scrub(item) for item in value]
        if isinstance(value, dict):
            return {key: self._scrub(item) for key, item in value.items()}
        return value

    def _get(self, client: httpx.Client, path: str) -> object:
        deadline = self._clock() + self.options.request_deadline_seconds
        failure = _error("timeout")
        for attempt in range(self.options.max_attempts):
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise _error("timeout")
            retry = False
            body = None
            try:
                timeout = httpx.Timeout(
                    connect=min(self.options.connect_timeout_seconds, remaining),
                    read=min(self.options.read_timeout_seconds, remaining),
                    write=min(self.options.read_timeout_seconds, remaining),
                    pool=min(self.options.connect_timeout_seconds, remaining),
                )
                with client.stream("GET", path, timeout=timeout) as response:
                    status = response.status_code
                    if status == 200:
                        if response.headers.get("content-encoding", "identity") != "identity":
                            raise _error("malformed_response")
                        chunks = bytearray()
                        for chunk in response.iter_bytes():
                            if self._clock() >= deadline:
                                raise _error("timeout")
                            if len(chunks) + len(chunk) > MAX_RESPONSE_BYTES:
                                raise _error("malformed_response")
                            chunks.extend(chunk)
                        if self._clock() >= deadline:
                            raise _error("timeout")
                        body = bytes(chunks)
                    else:
                        code = {401: "authentication_failed", 403: "permission_denied"}.get(
                            status,
                            "unavailable" if status in RETRY_STATUSES | {429} else "http_error",
                        )
                        failure = _error(code)
                        retry = status in RETRY_STATUSES
            except httpx.TimeoutException:
                failure, retry = _error("timeout"), True
            except (
                httpx.ConnectError,
                httpx.ReadError,
                httpx.WriteError,
                httpx.RemoteProtocolError,
            ) as error:
                code = "tls_error" if _tls_failure(error) else "connectivity_error"
                failure, retry = _error(code), code != "tls_error"
            except httpx.DecodingError:
                failure = _error("malformed_response")
            except httpx.RequestError:
                failure = _error("connectivity_error")
            # Raise outside transport exception handlers: do not retain request/header causes.
            if body is not None:
                data = None
                try:
                    # Scrub even reflected credentials before normalization or reporting.
                    text = self._token.redact(body.decode("utf-8"))
                    data = self._scrub(
                        json.loads(
                            text,
                            object_pairs_hook=_unique_json,
                            parse_constant=_reject_constant,
                        )
                    )
                except (ValueError, UnicodeError, RecursionError):
                    pass
                if not isinstance(data, dict) or "data" not in data:
                    raise _error("malformed_response")
                return data["data"]
            if not retry or attempt + 1 == self.options.max_attempts:
                raise failure
            remaining = deadline - self._clock()
            delay = min(0.25 * 2**attempt + random.uniform(0, 0.1), 1.0)
            if remaining <= delay:
                raise _error("timeout")
            self._sleep(delay)
        raise failure

    def inventory(self) -> Inventory:
        coverage = []
        collected = {"nodes": [], "storage": [], "vms": [], "networks": []}
        with httpx.Client(
            base_url=self.options.endpoint + "/api2/json/",
            verify=self.context,
            headers={"Authorization": self._token.authorization, "Accept-Encoding": "identity"},
            trust_env=False,
            follow_redirects=False,
            transport=self._transport,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        ) as client:
            version = _text(_object(self._get(client, "version")).get("version"))
            for node in self.config.nodes:
                for section, endpoint, parse in (
                    ("nodes", "status", _node),
                    ("storage", "storage", _storage),
                    ("vms", "qemu", _vms),
                    ("networks", "network", _networks),
                ):
                    if section != "nodes" and not any(n.name == node for n in collected["nodes"]):
                        coverage.append(Coverage(node, section, "not_queried", "node_unavailable"))
                        continue
                    try:
                        data = self._get(client, f"nodes/{node}/{endpoint}")
                        rows = parse(data, node)
                    except InventoryError as error:
                        coverage.append(Coverage(node, section, "failed", error.code))
                    else:
                        collected[section].extend(rows)
                        coverage.append(Coverage(node, section, "queried"))
        return Inventory(
            source=self._token.redact(self.options.endpoint),
            description=(
                "SIMULATED live-adapter transport test"
                if self.simulated
                else "Read-only Proxmox HTTPS API inventory"
            ),
            version=version,
            nodes=tuple(sorted(collected["nodes"], key=lambda r: r.name)),
            storage=tuple(sorted(collected["storage"], key=lambda r: (r.node, r.name))),
            vms=tuple(sorted(_unique(collected["vms"], lambda r: r.vmid), key=lambda r: r.vmid)),
            networks=tuple(sorted(collected["networks"], key=lambda r: (r.node, r.name))),
            backend="live",
            simulated=self.simulated,
            complete=all(row.status == "queried" for row in coverage),
            coverage=tuple(coverage),
            visibility="Credential-visible resources only; storage/VM lists may be ACL-filtered",
        )
