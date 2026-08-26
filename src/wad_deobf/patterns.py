from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import re

from .semantic_ir import Instruction


@dataclass(frozen=True)
class PatternContext:
    state: int
    state_var: str
    statement: str


PatternLift = Callable[[PatternContext, re.Match[str]], tuple[Instruction, ...]]


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


def lift_statement(
    context: PatternContext,
    patterns: Sequence[StatementPattern] = (),
) -> tuple[Instruction, ...] | None:
    for pattern in patterns:
        result = pattern.apply(context)
        if result is not None:
            return result
    return None
