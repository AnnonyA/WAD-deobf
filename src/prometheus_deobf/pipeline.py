from __future__ import annotations

from dataclasses import dataclass

from .cleanup import cleanup_dead_generated_scaffold, remove_antitamper
from .constant_array import recover_constant_arrays
from .encrypt_strings import recover_encrypted_strings
from .numbers import fold_numeric_expressions
from .unwrap import unwrap_generated_iife
from .vm import analyze_vm, lift_linear_dispatcher


@dataclass(slots=True)
class DeobfuscationResult:
    source: str
    total_changes: int
    report: list[dict]
    vm: dict


def deobfuscate(source: str, max_rounds: int = 8) -> DeobfuscationResult:
    current = source
    report: list[dict] = []
    total = 0

    for round_index in range(max_rounds):
        round_changes = 0

        unwrapped, count = unwrap_generated_iife(current)
        if count:
            current = unwrapped
            report.append({'pass': 'unwrap_iife', 'round': round_index + 1, 'changes': count})
            round_changes += count

        folded, count = fold_numeric_expressions(current)
        if count:
            current = folded
            report.append({'pass': 'fold_numbers', 'round': round_index + 1, 'changes': count})
            round_changes += count

        for name, fn in (
            ('constant_array', recover_constant_arrays),
            ('vm_linear', lift_linear_dispatcher),
            ('anti_tamper', remove_antitamper),
            ('encrypt_strings', recover_encrypted_strings),
            ('generated_scaffold', cleanup_dead_generated_scaffold),
        ):
            result = fn(current)
            if result.changes:
                current = result.source
                report.append({'pass': name, 'round': round_index + 1, 'changes': result.changes, 'details': result.details})
                round_changes += result.changes
            elif result.details.get('unresolved'):
                report.append({'pass': name, 'round': round_index + 1, 'changes': 0, 'details': result.details})

        total += round_changes
        if not round_changes:
            break

    vm = analyze_vm(current)
    return DeobfuscationResult(
        source=current,
        total_changes=total,
        report=report,
        vm={
            'detected': vm.detected,
            'position': vm.position,
            'comparisons': vm.comparisons,
            'states': vm.states,
        },
    )
