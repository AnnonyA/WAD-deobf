from __future__ import annotations

from dataclasses import dataclass

from .semantic_ir import Opaque, SemanticProgram
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
