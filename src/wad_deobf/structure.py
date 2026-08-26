from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .semantic_ir import Branch, Expr, Jump, Opaque, Return, SemanticProgram


@dataclass(frozen=True)
class BlockRegion:
    state: int


@dataclass(frozen=True)
class ReturnRegion:
    state: int


@dataclass(frozen=True)
class IfRegion:
    state: int
    condition: Expr
    true_region: Region
    false_region: Region
    next_state: int


@dataclass(frozen=True)
class WhileRegion:
    state: int
    condition: Expr
    body: Region
    next_state: int


@dataclass(frozen=True)
class SequenceRegion:
    items: tuple[Region, ...]


@dataclass(frozen=True)
class StateMachineRegion:
    states: tuple[int, ...]


Region: TypeAlias = BlockRegion | ReturnRegion | IfRegion | WhileRegion | SequenceRegion | StateMachineRegion


def _last(program: SemanticProgram, state: int):
    block = program.block_for_state(state)
    if block is None or not block.instructions:
        return None
    return block.instructions[-1]


def _has_opaque(program: SemanticProgram) -> bool:
    return any(
        isinstance(instruction, Opaque)
        for block in program.blocks
        for instruction in block.instructions
    )


def _simple_jump_target(program: SemanticProgram, state: int) -> int | None:
    last = _last(program, state)
    return last.target if isinstance(last, Jump) else None


def _fallback(program: SemanticProgram) -> StateMachineRegion:
    return StateMachineRegion(tuple(block.state for block in program.blocks))


def structure_program(program: SemanticProgram) -> Region:
    if program.entry_state is None or program.unresolved_targets or _has_opaque(program):
        return _fallback(program)
    if program.block_for_state(program.entry_state) is None:
        return _fallback(program)

    items: list[Region] = []
    consumed: set[int] = set()
    state = program.entry_state

    while state is not None:
        if state in consumed:
            return _fallback(program)
        block = program.block_for_state(state)
        if block is None or not block.instructions:
            return _fallback(program)
        last = block.instructions[-1]

        if isinstance(last, Return):
            consumed.add(state)
            items.append(ReturnRegion(state))
            state = None
            continue

        if isinstance(last, Jump):
            consumed.add(state)
            items.append(BlockRegion(state))
            state = last.target
            continue

        if not isinstance(last, Branch):
            return _fallback(program)

        true_state = last.true_state
        false_state = last.false_state
        true_block = program.block_for_state(true_state)
        false_block = program.block_for_state(false_state)
        if true_block is None or false_block is None:
            return _fallback(program)

        true_jump = _simple_jump_target(program, true_state)
        false_jump = _simple_jump_target(program, false_state)

        if len(block.instructions) == 1 and true_jump == state and false_state != state:
            consumed.update((state, true_state))
            items.append(WhileRegion(state, last.condition, BlockRegion(true_state), false_state))
            state = false_state
            continue

        if true_jump is not None and true_jump == false_jump and true_state != false_state:
            join = true_jump
            if join in {state, true_state, false_state}:
                return _fallback(program)
            consumed.update((state, true_state, false_state))
            items.append(
                IfRegion(
                    state,
                    last.condition,
                    BlockRegion(true_state),
                    BlockRegion(false_state),
                    join,
                )
            )
            state = join
            continue

        return _fallback(program)

    return SequenceRegion(tuple(items))
