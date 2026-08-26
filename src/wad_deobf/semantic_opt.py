from __future__ import annotations

import re

from .semantic_ir import (
    Assign,
    Attribute,
    Branch,
    Call,
    CallExpr,
    Concat,
    Expr,
    Index,
    Jump,
    Literal,
    MultiAssign,
    Name,
    Opaque,
    RawExpr,
    Return,
    SemanticBlock,
    SemanticProgram,
)


def _substitute(expr: Expr, env: dict[str, Expr], seen: set[str] | None = None) -> Expr:
    seen = set() if seen is None else seen
    if isinstance(expr, Name):
        if expr.name in seen or expr.name not in env:
            return expr
        seen.add(expr.name)
        return _substitute(env[expr.name], env, seen)
    if isinstance(expr, Attribute):
        return Attribute(_substitute(expr.base, env, seen.copy()), expr.name)
    if isinstance(expr, Index):
        return Index(_substitute(expr.base, env, seen.copy()), _substitute(expr.key, env, seen.copy()))
    if isinstance(expr, Concat):
        return Concat(tuple(_substitute(part, env, seen.copy()) for part in expr.parts))
    if isinstance(expr, CallExpr):
        return CallExpr(
            _substitute(expr.callee, env, seen.copy()),
            tuple(_substitute(arg, env, seen.copy()) for arg in expr.args),
        )
    return expr


def _has_call(expr: Expr) -> bool:
    if isinstance(expr, CallExpr):
        return True
    if isinstance(expr, Attribute):
        return _has_call(expr.base)
    if isinstance(expr, Index):
        return _has_call(expr.base) or _has_call(expr.key)
    if isinstance(expr, Concat):
        return any(_has_call(part) for part in expr.parts)
    return False


def _propagatable(expr: Expr) -> bool:
    if isinstance(expr, (Literal, Name)):
        return True
    if isinstance(expr, Attribute):
        return _propagatable(expr.base)
    return False


def _expr_names(expr: Expr) -> set[str]:
    if isinstance(expr, Name):
        return {expr.name}
    if isinstance(expr, Attribute):
        return _expr_names(expr.base)
    if isinstance(expr, Index):
        return _expr_names(expr.base) | _expr_names(expr.key)
    if isinstance(expr, Concat):
        names: set[str] = set()
        for part in expr.parts:
            names |= _expr_names(part)
        return names
    if isinstance(expr, CallExpr):
        names = _expr_names(expr.callee)
        for arg in expr.args:
            names |= _expr_names(arg)
        return names
    if isinstance(expr, RawExpr):
        return set(re.findall(r"\b[A-Za-z_]\w*\b", expr.source))
    return set()


def _invalidate_name(env: dict[str, Expr], name: str) -> None:
    stale = [key for key, value in env.items() if key == name or name in _expr_names(value)]
    for key in stale:
        env.pop(key, None)


def _pure_assignment_value(expr: Expr) -> bool:
    return isinstance(expr, (Literal, Name))


def _optimize_block(block: SemanticBlock) -> SemanticBlock:
    env: dict[str, Expr] = {}
    output = []
    for instruction in block.instructions:
        if isinstance(instruction, Assign):
            if isinstance(instruction.target, Name):
                target = instruction.target
            else:
                target = _substitute(instruction.target, env)
            value = _substitute(instruction.value, env)
            output.append(Assign(instruction.state, target, value))
            if _has_call(value):
                env.clear()
                continue
            if isinstance(target, Name):
                _invalidate_name(env, target.name)
                if _propagatable(value):
                    env[target.name] = value
            else:
                env.clear()
            continue
        if isinstance(instruction, MultiAssign):
            values = tuple(_substitute(value, env) for value in instruction.values)
            output.append(MultiAssign(instruction.state, instruction.targets, values))
            env.clear()
            continue
        if isinstance(instruction, Call):
            output.append(Call(instruction.state, _substitute(instruction.value, env)))
            env.clear()
            continue
        if isinstance(instruction, Branch):
            condition = _substitute(instruction.condition, env)
            if isinstance(condition, Literal) and type(condition.value) is bool:
                output.append(Jump(instruction.state, instruction.true_state if condition.value else instruction.false_state))
            else:
                output.append(Branch(instruction.state, condition, instruction.true_state, instruction.false_state))
            env.clear()
            continue
        if isinstance(instruction, Return):
            output.append(Return(instruction.state, tuple(_substitute(value, env) for value in instruction.values)))
            env.clear()
            continue
        if isinstance(instruction, Opaque):
            output.append(instruction)
            env.clear()
            continue
        output.append(instruction)
    return SemanticBlock(block.state, tuple(output))


def _used_names(program: SemanticProgram) -> set[str]:
    used: set[str] = set()
    for block in program.blocks:
        for instruction in block.instructions:
            if isinstance(instruction, Assign):
                if isinstance(instruction.target, Index):
                    used |= _expr_names(instruction.target)
                used |= _expr_names(instruction.value)
            elif isinstance(instruction, MultiAssign):
                for target in instruction.targets:
                    if isinstance(target, Index):
                        used |= _expr_names(target)
                for value in instruction.values:
                    used |= _expr_names(value)
            elif isinstance(instruction, Call):
                used |= _expr_names(instruction.value)
            elif isinstance(instruction, Branch):
                used |= _expr_names(instruction.condition)
            elif isinstance(instruction, Return):
                for value in instruction.values:
                    used |= _expr_names(value)
            elif isinstance(instruction, Opaque):
                used |= set(re.findall(r"\b[A-Za-z_]\w*\b", instruction.source))
    return used


def _remove_dead(program: SemanticProgram) -> SemanticProgram:
    used = _used_names(program)
    blocks: list[SemanticBlock] = []
    for block in program.blocks:
        instructions = []
        for instruction in block.instructions:
            if (
                isinstance(instruction, Assign)
                and isinstance(instruction.target, Name)
                and instruction.target.name not in used
                and _pure_assignment_value(instruction.value)
            ):
                continue
            instructions.append(instruction)
        blocks.append(SemanticBlock(block.state, tuple(instructions)))
    return SemanticProgram(program.entry_state, tuple(blocks), program.unresolved_targets)


def optimize_program(program: SemanticProgram) -> SemanticProgram:
    optimized = SemanticProgram(
        program.entry_state,
        tuple(_optimize_block(block) for block in program.blocks),
        program.unresolved_targets,
    )
    return _remove_dead(optimized)


def stable_names(program: SemanticProgram) -> dict[str, str]:
    names: list[str] = []
    seen: set[str] = set()
    for block in program.blocks:
        for instruction in block.instructions:
            targets: tuple[Expr, ...]
            if isinstance(instruction, Assign):
                targets = (instruction.target,)
            elif isinstance(instruction, MultiAssign):
                targets = instruction.targets
            else:
                continue
            for target in targets:
                if isinstance(target, Name) and target.name not in seen:
                    seen.add(target.name)
                    names.append(target.name)
    return {name: f"v{index}" for index, name in enumerate(names, 1)}
