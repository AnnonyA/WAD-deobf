from __future__ import annotations

from .recover import RecoveryResult


def emit_luau(result: RecoveryResult) -> str:
    body = result.source.rstrip() + "\n"
    if result.mode == "source":
        return body
    reason = result.reason or "unresolved WAD VM"
    if result.mode == "structured":
        return f"-- WAD deobfuscation: structured static recovery\n-- {reason}\n{body}"
    if result.mode == "structured-partial":
        return f"-- WAD deobfuscation: partial semantic recovery\n-- {reason}\n{body}"
    if result.mode == "vm":
        return f"-- WAD deobfuscation: de-flattened VM\n-- {reason}\n{body}"
    return f"-- WAD deobfuscation: partial static recovery\n-- {reason}\n{body}"
