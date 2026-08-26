from __future__ import annotations

import ast
import operator
import re


_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Mod: operator.mod,
}


def eval_int_expr(source: str) -> int:
    try:
        node = ast.parse(source.strip(), mode="eval").body
    except SyntaxError as exc:
        raise ValueError("invalid integer expression") from exc

    def visit(current: ast.AST) -> int:
        if isinstance(current, ast.Constant) and type(current.value) is int:
            return current.value
        if isinstance(current, ast.UnaryOp) and isinstance(current.op, ast.USub):
            return -visit(current.operand)
        if isinstance(current, ast.BinOp):
            left = visit(current.left)
            right = visit(current.right)
            operation = _BINARY.get(type(current.op))
            if operation is not None:
                return operation(left, right)
            if isinstance(current.op, ast.Div):
                if right == 0 or left % right:
                    raise ValueError("division is not an exact integer")
                return left // right
        raise ValueError("unsupported integer expression")

    try:
        return visit(node)
    except (ZeroDivisionError, OverflowError) as exc:
        raise ValueError("invalid integer expression") from exc


def _try_fold(match: re.Match[str]) -> str:
    text = match.group(0)
    try:
        return str(eval_int_expr(text))
    except ValueError:
        return text


def _try_fold_parenthesized(match: re.Match[str]) -> str:
    text = match.group(0)
    try:
        value = str(eval_int_expr(text))
    except ValueError:
        return text
    before = match.string[: match.start()].rstrip()
    if before and (before[-1].isalnum() or before[-1] in "_.)]"):
        return f"({value})"
    return value


def fold_int_expressions(source: str) -> str:
    result = source
    inner = re.compile(r"\([^()]*\)")
    while True:
        updated = inner.sub(_try_fold_parenthesized, result)
        if updated == result:
            break
        result = updated
    flat = re.compile(r"(?<![\w.])-?\d+(?:\s*[+\-*/%]\s*-?\d+)+(?![\w.])")
    return flat.sub(_try_fold, result)
