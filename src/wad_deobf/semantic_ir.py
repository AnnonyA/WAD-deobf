from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True)
class Literal:
    value: object


@dataclass(frozen=True)
class Name:
    name: str


@dataclass(frozen=True)
class Attribute:
    base: Expr
    name: str


@dataclass(frozen=True)
class Index:
    base: Expr
    key: Expr


@dataclass(frozen=True)
class Concat:
    parts: tuple[Expr, ...]


@dataclass(frozen=True)
class CallExpr:
    callee: Expr
    args: tuple[Expr, ...]


@dataclass(frozen=True)
class RawExpr:
    source: str


Expr: TypeAlias = Literal | Name | Attribute | Index | Concat | CallExpr | RawExpr


@dataclass(frozen=True)
class Assign:
    state: int
    target: Expr
    value: Expr

    @property
    def targets(self) -> tuple[int, ...]:
        return ()


@dataclass(frozen=True)
class Call:
    state: int
    value: CallExpr

    @property
    def targets(self) -> tuple[int, ...]:
        return ()


@dataclass(frozen=True)
class Branch:
    state: int
    condition: Expr
    true_state: int
    false_state: int

    @property
    def targets(self) -> tuple[int, ...]:
        return (self.true_state, self.false_state)


@dataclass(frozen=True)
class Jump:
    state: int
    target: int

    @property
    def targets(self) -> tuple[int, ...]:
        return (self.target,)


@dataclass(frozen=True)
class Return:
    state: int
    values: tuple[Expr, ...]

    @property
    def targets(self) -> tuple[int, ...]:
        return ()


@dataclass(frozen=True)
class Opaque:
    state: int
    source: str

    @property
    def targets(self) -> tuple[int, ...]:
        return ()


Instruction: TypeAlias = Assign | Call | Branch | Jump | Return | Opaque


@dataclass(frozen=True)
class SemanticBlock:
    state: int
    instructions: tuple[Instruction, ...]

    @property
    def targets(self) -> tuple[int, ...]:
        if not self.instructions:
            return ()
        return self.instructions[-1].targets


@dataclass(frozen=True)
class SemanticProgram:
    entry_state: int | None
    blocks: tuple[SemanticBlock, ...]
    unresolved_targets: tuple[int, ...] = ()

    def block_for_state(self, state: int) -> SemanticBlock | None:
        for block in self.blocks:
            if block.state == state:
                return block
        return None
