from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import re

from .lua_expr import parse_expr
from .semantic_ir import Index, Instruction, MultiAssign, Name


@dataclass(frozen=True)
class PatternContext:
    state: int
    state_var: str
    statement: str


PatternLift = Callable[[PatternContext, re.Match[str]], tuple[Instruction, ...] | None]


@dataclass(frozen=True)
class StatementPattern:
    name: str
    expression: str
    lift: PatternLift

    def apply(self, context: PatternContext) -> tuple[Instruction, ...] | None:
        match = re.fullmatch(self.expression, context.statement.strip())
        if match is None:
            return None
        return self.lift(context, match)


def _split_top_level(source: str, separator: str) -> list[str]:
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
        elif not stack and char == separator:
            parts.append(source[start:index].strip())
            start = index + 1
        index += 1
    parts.append(source[start:].strip())
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


def _lift_multi_assignment(
    context: PatternContext,
    match: re.Match[str],
) -> tuple[Instruction, ...] | None:
    text = match.group(0).strip()
    assignment = _assignment_index(text)
    if assignment is None:
        return None
    lhs = text[:assignment].strip()
    rhs = text[assignment + 1:].strip()
    if lhs.startswith("local "):
        lhs = lhs[6:].strip()
    target_parts = _split_top_level(lhs, ",")
    if len(target_parts) < 2 or any(not part for part in target_parts):
        return None
    targets = tuple(parse_expr(part) for part in target_parts)
    if any(not isinstance(target, (Name, Index)) for target in targets):
        return None
    if any(isinstance(target, Name) and target.name == context.state_var for target in targets):
        return None
    value_parts = _split_top_level(rhs, ",")
    if not value_parts or any(not part for part in value_parts):
        return None
    values = tuple(parse_expr(part) for part in value_parts)
    return (MultiAssign(context.state, targets, values),)


DEFAULT_PATTERNS = (
    StatementPattern("multiple-assignment", r".+", _lift_multi_assignment),
)


def lift_statement(
    context: PatternContext,
    patterns: Sequence[StatementPattern] | None = None,
) -> tuple[Instruction, ...] | None:
    active = DEFAULT_PATTERNS if patterns is None else patterns
    for pattern in active:
        result = pattern.apply(context)
        if result is not None:
            return result
    return None
