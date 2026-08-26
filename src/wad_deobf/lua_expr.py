from __future__ import annotations

import re

from .semantic_ir import Attribute, CallExpr, Concat, Expr, Index, Literal, Name, RawExpr
from .strings import _decode_lua_string


_NAME = re.compile(r"[A-Za-z_]\w*")
_INT = re.compile(r"-?\d+")


def _scan_top_level(source: str, token: str) -> list[int]:
    positions: list[int] = []
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
            index += 1
            continue
        if stack and char == stack[-1]:
            stack.pop()
            index += 1
            continue
        if not stack and source.startswith(token, index):
            positions.append(index)
            index += len(token)
            continue
        index += 1
    return positions


def _split_top_level(source: str, token: str) -> list[str]:
    positions = _scan_top_level(source, token)
    if not positions:
        return [source.strip()]
    parts: list[str] = []
    cursor = 0
    for position in positions:
        parts.append(source[cursor:position].strip())
        cursor = position + len(token)
    parts.append(source[cursor:].strip())
    return parts


def _matching_open(source: str, closing_index: int, opening: str, closing: str) -> int | None:
    depth = 0
    index = closing_index
    while index >= 0:
        char = source[index]
        if char in "\"'":
            index -= 1
            continue
        if char == closing:
            depth += 1
        elif char == opening:
            depth -= 1
            if depth == 0:
                return index
        index -= 1
    return None


def parse_expr(source: str) -> Expr:
    text = source.strip()
    if not text:
        return RawExpr(text)

    if text[0] in "\"'" and len(text) >= 2 and text[-1] == text[0]:
        try:
            return Literal(_decode_lua_string(text))
        except ValueError:
            return RawExpr(text)
    if _INT.fullmatch(text):
        return Literal(int(text))
    if text == "true":
        return Literal(True)
    if text == "false":
        return Literal(False)
    if text == "nil":
        return Literal(None)

    concat = _split_top_level(text, "..")
    if len(concat) > 1 and all(concat):
        return Concat(tuple(parse_expr(part) for part in concat))

    if text.endswith(")"):
        opening = _matching_open(text, len(text) - 1, "(", ")")
        if opening is not None and opening > 0:
            callee_text = text[:opening].strip()
            if callee_text:
                args_text = text[opening + 1:-1]
                args = () if not args_text.strip() else tuple(parse_expr(part) for part in _split_top_level(args_text, ","))
                callee = parse_expr(callee_text)
                if not isinstance(callee, RawExpr):
                    return CallExpr(callee, args)

    if text.endswith("]"):
        opening = _matching_open(text, len(text) - 1, "[", "]")
        if opening is not None and opening > 0:
            base = parse_expr(text[:opening])
            key = parse_expr(text[opening + 1:-1])
            if not isinstance(base, RawExpr):
                return Index(base, key)

    dots = _scan_top_level(text, ".")
    if dots:
        position = dots[-1]
        if not text.startswith("..", position) and not (position > 0 and text[position - 1] == "."):
            base_text = text[:position].strip()
            name = text[position + 1:].strip()
            if _NAME.fullmatch(name):
                base = parse_expr(base_text)
                if not isinstance(base, RawExpr):
                    return Attribute(base, name)

    if _NAME.fullmatch(text):
        return Name(text)
    return RawExpr(text)


def _quote(value: str) -> str:
    replacements = {
        "\\": "\\\\",
        '"': '\\"',
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
    }
    return '"' + "".join(replacements.get(char, char) for char in value) + '"'


def emit_expr(expr: Expr) -> str:
    if isinstance(expr, Literal):
        if expr.value is None:
            return "nil"
        if expr.value is True:
            return "true"
        if expr.value is False:
            return "false"
        if isinstance(expr.value, str):
            return _quote(expr.value)
        return str(expr.value)
    if isinstance(expr, Name):
        return expr.name
    if isinstance(expr, Attribute):
        return f"{emit_expr(expr.base)}.{expr.name}"
    if isinstance(expr, Index):
        return f"{emit_expr(expr.base)}[{emit_expr(expr.key)}]"
    if isinstance(expr, Concat):
        return " .. ".join(emit_expr(part) for part in expr.parts)
    if isinstance(expr, CallExpr):
        return f"{emit_expr(expr.callee)}({', '.join(emit_expr(arg) for arg in expr.args)})"
    return expr.source
