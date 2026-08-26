from __future__ import annotations

from .recover import RecoveryResult


def emit_luau(result: RecoveryResult) -> str:
    body = result.source.rstrip() + "\n"
    if result.mode == "source":
        return body
    reason = result.reason or "unresolved WAD VM"
    return f"-- WAD deobfuscation: partial static recovery\n-- {reason}\n{body}"
