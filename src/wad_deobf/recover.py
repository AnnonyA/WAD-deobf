from __future__ import annotations

from dataclasses import dataclass
import re

from .normalize import NormalizedWad
from .strings import _decode_lua_string


_LOAD_CALL = re.compile(
    r"\b(?:loadstring|load)\s*\(\s*(?P<literal>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')\s*\)"
)


@dataclass(frozen=True)
class RecoveryResult:
    mode: str
    source: str
    reason: str | None = None


def recover_luau(normalized: NormalizedWad) -> RecoveryResult:
    match = _LOAD_CALL.search(normalized.source)
    if match is not None:
        payload = _decode_lua_string(match.group("literal"))
        return RecoveryResult(mode="source", source=payload, reason=None)
    return RecoveryResult(
        mode="normalized",
        source=normalized.source,
        reason="WAD VM payload could not be proven statically",
    )
