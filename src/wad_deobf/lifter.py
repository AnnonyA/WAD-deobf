from __future__ import annotations

import re

from .cfg import build_state_graph
from .ir import VmProgram
from .lua_expr import parse_expr
from .semantic_ir import (
    Assign,
    Branch,
    Call,
    CallExpr,
    Index,
    Jump,
    Name,
    Opaque,
    Return,
    SemanticBlock,
    SemanticProgram,
)


_INT = re.compile(r"-?\d+")


def _split_top_level(source: str, separators: str) -> list[str]:
    parts: list[str] = []
    start = 0
    index = 0
    stack: list[str] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    while index < len(source):
        char = source[index]
        if char in "\"'":
            quote = char
            index += 1
            while index < len(source):
                if source[index] == "\\":
                    index += 2
                    continue
                if source[index] == quote:
                    index += 1
                    break
                index += 1
            continue
        if char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif not stack and char in separators:
            item = source[start:index].strip()
            if item:
                parts.append(item)
            start = index + 1
        index += 1
    item = source[start:].strip()
    if item:
        parts.append(item)
    return parts


def _assignment_index(source: str) -> int | None:
    stack: list[str] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    index = 0
    while index < len(source):
        char = source[index]
        if char in "\"'":
            quote = char
            index += 1
            while index < len(source):
                if source[index] == "\\":
                    index += 2
                    continue
                if source[index] == quote:
                    index += 1
                    break
                index += 1
            continue
        if char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif not stack and char == "=":
            before = source[index - 1] if index else ""
            after = source[index + 1] if index + 1 < len(source) else ""
            if before not in "<>=~" and after != "=":
                return index
        index += 1
    return None


def _lift_state_assignment(state: int, rhs: str):
    value = rhs.strip()
    if _INT.fullmatch(value):
        return Jump(state, int(value))
    match = re.fullmatch(r"(?P<condition>.+?)\s+and\s+(?P<yes>-?\d+)\s+or\s+(?P<no>-?\d+)", value)
    if match is not None:
        return Branch(
            state,
            parse_expr(match.group("condition")),
            int(match.group("yes")),
            int(match.group("no")),
        )
    return Opaque(state, f"state = {value}")


def _lift_statement(state: int, state_var: str, statement: str):
    text = statement.strip()
    if not text:
        return None
    if text.startswith("return") and (len(text) == 6 or text[6].isspace()):
        rest = text[6:].strip()
        values = () if not rest else tuple(parse_expr(part) for part in _split_top_level(rest, ","))
        return Return(state, values)

    assignment = _assignment_index(text)
    if assignment is not None:
        lhs = text[:assignment].strip()
        rhs = text[assignment + 1:].strip()
        if lhs.startswith("local "):
            lhs = lhs[6:].strip()
        if lhs == state_var:
            return _lift_state_assignment(state, rhs)
        target = parse_expr(lhs)
        if not isinstance(target, (Name, Index)):
            return Opaque(state, text)
        return Assign(state, target, parse_expr(rhs))

    value = parse_expr(text)
    if isinstance(value, CallExpr):
        return Call(state, value)
    return Opaque(state, text)


def _lift_block(state: int, state_var: str, source: str) -> SemanticBlock:
    instructions = []
    for statement in _split_top_level(source, ";\n"):
        instruction = _lift_statement(state, state_var, statement)
        if instruction is not None:
            instructions.append(instruction)
    return SemanticBlock(state, tuple(instructions))


def lift_program(program: VmProgram, entry_state: int | None = None) -> SemanticProgram:
    if entry_state is not None:
        graph = build_state_graph(program, entry_state)
        states = graph.states
        unresolved = graph.unresolved_targets
    else:
        states = tuple(sorted({target for block in program.blocks for target in block.targets}))
        unresolved = tuple(state for state in states if program.block_for_state(state) is None)

    blocks: list[SemanticBlock] = []
    for state in states:
        block = program.block_for_state(state)
        if block is None:
            continue
        blocks.append(_lift_block(state, program.state_var, block.source))
    return SemanticProgram(entry_state, tuple(blocks), tuple(dict.fromkeys(unresolved)))
