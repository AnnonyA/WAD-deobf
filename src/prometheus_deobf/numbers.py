from __future__ import annotations

import ast
import operator
import re

from .lex import code_spans

_BIN = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def eval_numeric(expr: str):
    try:
        tree = ast.parse(expr.replace('^', '**'), mode='eval')
    except SyntaxError:
        return None

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = walk(node.operand)
            if value is None:
                return None
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            left, right = walk(node.left), walk(node.right)
            if left is None or right is None:
                return None
            try:
                return _BIN[type(node.op)](left, right)
            except (ZeroDivisionError, OverflowError, ValueError):
                return None
        return None

    value = walk(tree)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _fmt(value):
    if isinstance(value, int):
        return str(value)
    return format(value, '.15g')


def _fold_segment(segment: str):
    count = 0
    paren = re.compile(r'\((\s*[+-]?\d+(?:\.\d+)?(?:\s*[+\-*/%^]\s*[+-]?\d+(?:\.\d+)?)+\s*)\)')
    plain = re.compile(r'(?<![\w.])([+-]?\d+(?:\.\d+)?(?:\s*[+\-*/%^]\s*[+-]?\d+(?:\.\d+)?)+)(?![\w.])')
    while True:
        changed = False
        for pattern in (paren, plain):
            def repl(m):
                nonlocal count, changed
                value = eval_numeric(m.group(1))
                if value is None:
                    return m.group(0)
                count += 1
                changed = True
                return _fmt(value)
            segment = pattern.sub(repl, segment)
        if not changed:
            break
    return segment, count


def fold_numeric_expressions(source: str):
    pieces = []
    cursor = 0
    total = 0
    for a, b in code_spans(source):
        pieces.append(source[cursor:a])
        folded, count = _fold_segment(source[a:b])
        pieces.append(folded)
        total += count
        cursor = b
    pieces.append(source[cursor:])
    return ''.join(pieces), total
