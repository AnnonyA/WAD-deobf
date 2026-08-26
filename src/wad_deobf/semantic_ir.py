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
