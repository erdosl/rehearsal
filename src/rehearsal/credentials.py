"""Read a protected runtime token file. Never include credentials in repr/errors."""

import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

from rehearsal.errors import InventoryError


@dataclass(frozen=True)
class APIToken:
    token_id: str = field(repr=False)
    secret: str = field(repr=False)

    @property
    def authorization(self) -> str:
        return f"PVEAPIToken={self.token_id}={self.secret}"

    def redact(self, text: str) -> str:
        for value in (self.authorization, self.token_id, self.secret):
            text = text.replace(value, "[REDACTED]")
        return text


def load_token(path: Path | None) -> APIToken:
    failure = None
    data = None
    if path is None:
        raise InventoryError("credentials_error", "live inventory requires proxmox.token_file")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) not in (0o600, 0o400)
            ):
                failure = "token file must be a regular file owned by this user with mode 0600/0400"
            else:
                raw = stream.read(4097)
                if len(raw) > 4096:
                    failure = "token file exceeds the 4 KiB limit"
                else:
                    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_fields)
    except (OSError, ValueError, UnicodeError, RecursionError):
        failure = "cannot read a valid protected token file; contents are not displayed"
    if failure:
        raise InventoryError("credentials_error", failure)
    if (
        not isinstance(data, dict)
        or set(data) != {"token_id", "token_secret"}
        or not isinstance(data["token_id"], str)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+![A-Za-z0-9_.-]+", data["token_id"])
        or not isinstance(data["token_secret"], str)
        or not re.fullmatch(
            r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", data["token_secret"]
        )
    ):
        raise InventoryError(
            "credentials_error", "token file must contain a token ID and UUID secret"
        )
    return APIToken(data["token_id"], data["token_secret"])


def _unique_fields(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate credential field")
        result[key] = value
    return result
