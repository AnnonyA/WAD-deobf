from __future__ import annotations

import re

from .cfg import build_state_graph
from .ir import VmProgram


def _rename_state(source: str, state_var: str) -> str:
    return re.sub(rf"\b{re.escape(state_var)}\b", "state", source)


def _indent_body(source: str, state_var: str) -> list[str]:
    body = _rename_state(source.strip(), state_var)
    if not body:
        return ["        -- empty block"]
    body = re.sub(r";\s*", "\n", body)
    body = re.sub(r"(?<![<>=~])=(?!=)", " = ", body)
    return ["        " + line.strip() for line in body.splitlines() if line.strip()]


def emit_state_machine(program: VmProgram, entry_state: int | None = None) -> str:
    if entry_state is None:
        states = sorted({target for block in program.blocks for target in block.targets})
        header = ["-- entry state unknown", "local state = nil", "while state do"]
    else:
        graph = build_state_graph(program, entry_state)
        states = list(graph.states)
        header = [f"local state = {entry_state}", "while state do"]

    if not states:
        raise ValueError("dispatcher has no concrete states to emit")

    lines = header
    for index, state in enumerate(states):
        block = program.block_for_state(state)
        if block is None:
            continue
        keyword = "if" if index == 0 else "elseif"
        lines.append(f"    {keyword} state == {state} then")
        lines.extend(_indent_body(block.source, program.state_var))
    lines.append("    else")
    lines.append("        error(\"unknown WAD VM state: \" .. tostring(state))")
    lines.append("    end")
    lines.append("end")
    return "\n".join(lines) + "\n"
