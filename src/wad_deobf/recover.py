from __future__ import annotations

from dataclasses import dataclass
import re

from .cleanup import resolve_global_aliases
from .dataflow import propagate_straight_line_facts
from .lifter import lift_program
from .normalize import NormalizedWad
from .semantic_opt import optimize_program
from .strings import _decode_lua_string
from .structure import structure_program
from .structured_emit import emit_structured
from .vm import extract_dispatcher, infer_entry_state
from .vm_emit import emit_state_machine


_LOAD_CALL = re.compile(
    r"\b(?:loadstring|load)\s*\(\s*(?P<literal>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')\s*\)"
)
_LOAD_VAR = re.compile(r"\b(?:loadstring|load)\s*\(\s*(?P<name>[A-Za-z_]\w*)\s*\)")
_STRING_LITERAL = r"(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"


def _resolve_static_string(source: str, name: str, seen: set[str] | None = None) -> str | None:
    seen = set() if seen is None else seen
    if name in seen:
        return None
    seen.add(name)
    assignment_count = len(re.findall(rf"(?<![\w.]){re.escape(name)}\s*=", source))
    if assignment_count != 1:
        return None
    term = rf"(?:{_STRING_LITERAL}|[A-Za-z_]\w*)"
    match = re.search(
        rf"(?<![\w.])(?:local\s+)?{re.escape(name)}\s*=\s*(?P<expr>{term}(?:\s*\.\.\s*{term})*)",
        source,
    )
    if match is None:
        return None
    parts = [part.strip() for part in re.split(r"\s*\.\.\s*", match.group("expr"))]
    output: list[str] = []
    for part in parts:
        if part.startswith(("\"", "'")):
            output.append(_decode_lua_string(part))
            continue
        value = _resolve_static_string(source, part, seen.copy())
        if value is None:
            return None
        output.append(value)
    return "".join(output)


def _static_load_payload(source: str) -> str | None:
    direct = _LOAD_CALL.search(source)
    if direct is not None:
        return _decode_lua_string(direct.group("literal"))
    for match in _LOAD_VAR.finditer(source):
        value = _resolve_static_string(source, match.group("name"))
        if value is not None:
            return value
    return None


@dataclass(frozen=True)
class RecoveryResult:
    mode: str
    source: str
    reason: str | None = None


def recover_luau(normalized: NormalizedWad, entry_state: int | None = None) -> RecoveryResult:
    cleaned_source = resolve_global_aliases(normalized.source)
    payload = _static_load_payload(cleaned_source)
    if payload is not None:
        return RecoveryResult(mode="source", source=payload, reason=None)

    try:
        program = extract_dispatcher(cleaned_source)
        resolved_entry = entry_state if entry_state is not None else infer_entry_state(cleaned_source, program)
    except ValueError:
        return RecoveryResult(
            mode="normalized",
            source=normalized.source,
            reason="WAD VM payload could not be proven statically",
        )

    if resolved_entry is not None:
        try:
            lifted = lift_program(program, resolved_entry)
            propagated = propagate_straight_line_facts(lifted)
            semantic = optimize_program(propagated)
            region = structure_program(semantic)
            source, complete = emit_structured(semantic, region)
            if complete:
                return RecoveryResult(
                    mode="structured",
                    source=source,
                    reason="WAD VM recovered into structured static Luau",
                )
            return RecoveryResult(
                mode="structured-partial",
                source=source,
                reason="WAD VM lifted semantically; unresolved regions kept as a state machine",
            )
        except ValueError:
            pass

    try:
        lifted = emit_state_machine(program, entry_state=resolved_entry)
    except ValueError:
        return RecoveryResult(
            mode="normalized",
            source=normalized.source,
            reason="WAD VM payload could not be proven statically",
        )

    reason = "WAD VM dispatcher de-flattened"
    if resolved_entry is None:
        reason += "; entry state unknown"
    return RecoveryResult(mode="vm", source=lifted, reason=reason)
