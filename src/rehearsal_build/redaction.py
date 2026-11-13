"""Remove credential fields and recognizable credential text before evidence leaves memory."""

import re

SENSITIVE = {
    "password",
    "passwd",
    "cipassword",
    "token",
    "token_secret",
    "authorization",
    "proxy_authorization",
    "private_key",
    "secret",
    "client_secret",
    "access_token",
    "refresh_token",
    "api_key",
    "cookie",
    "set_cookie",
}
SECRET_TEXT = re.compile(
    r"PVEAPIToken=|PRIVATE KEY-----|"
    r"\b(?:Bearer|Basic)\s+\S+|"
    r"(?<![!@.\w-])(?:authorization|proxy[-_]authorization|password|passwd|cipassword|"
    r"token|api[-_]token|token[-_]secret|client[-_]secret|access[-_]token|refresh[-_]token|api[-_]key|"
    r"secret|cookie|set[-_]cookie)[\"']?\s*[:=]|"
    r"://[^/\s]*:[^@\s]+@",
    re.IGNORECASE,
)


def sensitive_key(key):
    return str(key).lower().replace("-", "_") in SENSITIVE


def _private_key_marker(value):
    if isinstance(value, dict):
        return any(_private_key_marker(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_private_key_marker(item) for item in value)
    return isinstance(value, str) and "PRIVATE KEY-----" in value


def redact(value, secrets=()):
    """Omit credential fields and suppress credential-bearing free text as a whole.

    Arbitrary unlabelled external text is not a safe public report format. This is
    for protected local evidence and the supervised tool's structured responses.
    """
    if isinstance(value, dict):
        return {
            redact(key, secrets): redact(item, secrets)
            for key, item in value.items()
            if not sensitive_key(key)
        }
    if isinstance(value, (list, tuple)):
        # Logs may split a key across lines/records; suppress the whole group.
        if _private_key_marker(value):
            return ["[REDACTED]"]
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
        return "[REDACTED]" if SECRET_TEXT.search(value) else value
    return value
