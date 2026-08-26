from __future__ import annotations

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


FactEnv = dict[str, Expr]


def _substitute(expr: Expr, env: FactEnv, seen: set[str] | None = None) -> Expr:
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
    if isinstance(expr, RawExpr):
        return expr
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


def _invalidate(env: FactEnv, name: str) -> None:
    stale = [
        key
        for key, value in env.items()
        if key == name or (isinstance(value, Name) and value.name == name)
    ]
    for key in stale:
        env.pop(key, None)


def _process_block(block: SemanticBlock, incoming: FactEnv) -> tuple[SemanticBlock, FactEnv]:
    env = dict(incoming)
    output = []
    for instruction in block.instructions:
        if isinstance(instruction, Assign):
            if isinstance(instruction.target, Name):
                value = _substitute(instruction.value, env)
                output.append(Assign(instruction.state, instruction.target, value))
                if _has_call(value):
                    env.clear()
                    continue
                _invalidate(env, instruction.target.name)
                if isinstance(value, (Literal, Name)):
                    env[instruction.target.name] = value
            else:
                output.append(instruction)
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
            output.append(
                Branch(
                    instruction.state,
                    _substitute(instruction.condition, env),
                    instruction.true_state,
                    instruction.false_state,
                )
            )
            env.clear()
            continue
        if isinstance(instruction, Return):
            output.append(
                Return(
                    instruction.state,
                    tuple(_substitute(value, env) for value in instruction.values),
                )
            )
            env.clear()
            continue
        if isinstance(instruction, Opaque):
            output.append(instruction)
            env.clear()
            continue
        output.append(instruction)
    return SemanticBlock(block.state, tuple(output)), env


def _predecessors(program: SemanticProgram) -> dict[int, set[int]]:
    predecessors: dict[int, set[int]] = {block.state: set() for block in program.blocks}
    for block in program.blocks:
        if not block.instructions:
            continue
        last = block.instructions[-1]
        if isinstance(last, Jump):
            if last.target in predecessors:
                predecessors[last.target].add(block.state)
        elif isinstance(last, Branch):
            if last.true_state in predecessors:
                predecessors[last.true_state].add(block.state)
            if last.false_state in predecessors:
                predecessors[last.false_state].add(block.state)
    return predecessors


def propagate_straight_line_facts(program: SemanticProgram) -> SemanticProgram:
    if program.entry_state is None:
        return program

    by_state = {block.state: block for block in program.blocks}
    if program.entry_state not in by_state:
        return program

    predecessors = _predecessors(program)
    rewritten: dict[int, SemanticBlock] = {}
    outgoing: dict[int, FactEnv] = {}
    incoming: dict[int, FactEnv] = {program.entry_state: {}}
    queue = [program.entry_state]
    queued = {program.entry_state}
    processed: set[int] = set()

    while queue:
        state = queue.pop(0)
        queued.discard(state)
        if state in processed:
            continue
        block = by_state.get(state)
        if block is None:
            continue
        processed.add(state)
        new_block, env = _process_block(block, incoming.get(state, {}))
        rewritten[state] = new_block
        outgoing[state] = env

        if not new_block.instructions:
            continue
        last = new_block.instructions[-1]
        targets: tuple[int, ...]
        if isinstance(last, Jump):
            targets = (last.target,)
        elif isinstance(last, Branch):
            targets = (last.true_state, last.false_state)
        else:
            targets = ()

        for target in targets:
            if target not in by_state or target in processed:
                continue
            pred = predecessors.get(target, set())
            if (
                isinstance(last, Jump)
                and last.target == target
                and len(pred) == 1
                and state in pred
                and target != state
            ):
                incoming[target] = dict(outgoing[state])
            else:
                incoming[target] = {}
            if target not in queued:
                queue.append(target)
                queued.add(target)

    for block in program.blocks:
        if block.state not in rewritten:
            rewritten[block.state], _ = _process_block(block, {})

    return SemanticProgram(
        program.entry_state,
        tuple(rewritten[block.state] for block in program.blocks),
        program.unresolved_targets,
    )
