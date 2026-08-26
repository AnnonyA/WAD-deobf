from __future__ import annotations

from dataclasses import dataclass

from .lua_expr import emit_expr
from .semantic_ir import Assign, Branch, Call, Jump, Opaque, Return, SemanticProgram
from .structure import Region, StateMachineRegion


@dataclass(frozen=True)
class DiagnosticReport:
    state_count: int
    opaque_states: tuple[int, ...]
    unresolved_targets: tuple[int, ...]
    structured: bool


def analyze_semantic_program(program: SemanticProgram, region: Region) -> DiagnosticReport:
    opaque = []
    for block in program.blocks:
        if any(isinstance(instruction, Opaque) for instruction in block.instructions):
            opaque.append(block.state)
    return DiagnosticReport(
        state_count=len(program.blocks),
        opaque_states=tuple(opaque),
        unresolved_targets=program.unresolved_targets,
        structured=not isinstance(region, StateMachineRegion),
    )


def render_diagnostics(report: DiagnosticReport) -> str:
    lines = [
        f"states: {report.state_count}",
        f"structured: {'yes' if report.structured else 'no'}",
        "opaque states: " + (", ".join(str(state) for state in report.opaque_states) if report.opaque_states else "none"),
        "unresolved targets: " + (
            ", ".join(str(state) for state in report.unresolved_targets)
            if report.unresolved_targets
            else "none"
        ),
    ]
    return "\n".join(lines) + "\n"


def render_semantic_ir(program: SemanticProgram) -> str:
    lines = [f"entry: {program.entry_state if program.entry_state is not None else 'unknown'}"]
    for block in program.blocks:
        lines.append(f"state {block.state}:")
        if not block.instructions:
            lines.append("  empty")
            continue
        for instruction in block.instructions:
            if isinstance(instruction, Assign):
                lines.append(f"  assign {emit_expr(instruction.target)} = {emit_expr(instruction.value)}")
            elif isinstance(instruction, Call):
                lines.append(f"  call {emit_expr(instruction.value)}")
            elif isinstance(instruction, Branch):
                lines.append(
                    f"  branch {emit_expr(instruction.condition)} ? {instruction.true_state} : {instruction.false_state}"
                )
            elif isinstance(instruction, Jump):
                lines.append(f"  jump {instruction.target}")
            elif isinstance(instruction, Return):
                values = ", ".join(emit_expr(value) for value in instruction.values)
                lines.append(f"  return{(' ' + values) if values else ''}")
            elif isinstance(instruction, Opaque):
                lines.append(f"  opaque {instruction.source}")
    if program.unresolved_targets:
        lines.append("unresolved: " + ", ".join(str(state) for state in program.unresolved_targets))
    return "\n".join(lines) + "\n"
