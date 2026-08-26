from __future__ import annotations

from dataclasses import dataclass
import re

from .expressions import eval_int_expr
from .ir import VmBlock, VmProgram


_WORD = re.compile(r"[A-Za-z_]\w*")


@dataclass(frozen=True)
class _Token:
    value: str
    start: int
    end: int


def _skip_string(source: str, index: int) -> int:
    quote = source[index]
    index += 1
    while index < len(source):
        if source[index] == "\\":
            index += 2
            continue
        if source[index] == quote:
            return index + 1
        index += 1
    raise ValueError("unterminated Lua string")


def _tokens(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    while index < len(source):
        if source[index].isspace():
            index += 1
            continue
        if source.startswith("--[[", index):
            end = source.find("]]", index + 4)
            if end < 0:
                raise ValueError("unterminated Lua block comment")
            index = end + 2
            continue
        if source.startswith("--", index):
            end = source.find("\n", index + 2)
            index = len(source) if end < 0 else end + 1
            continue
        if source[index] in "\"'":
            end = _skip_string(source, index)
            tokens.append(_Token(source[index:end], index, end))
            index = end
            continue
        match = _WORD.match(source, index)
        if match:
            tokens.append(_Token(match.group(0), match.start(), match.end()))
            index = match.end()
            continue
        match = re.match(r"\d+", source[index:])
        if match:
            end = index + len(match.group(0))
            tokens.append(_Token(source[index:end], index, end))
            index = end
            continue
        two = source[index:index + 2]
        if two in {"<=", ">=", "==", "~="}:
            tokens.append(_Token(two, index, index + 2))
            index += 2
        else:
            tokens.append(_Token(source[index], index, index + 1))
            index += 1
    return tokens


def _matching_end(tokens: list[_Token], opener: int) -> tuple[int | None, int]:
    stack = [tokens[opener].value]
    else_index: int | None = None
    index = opener + 1
    while index < len(tokens):
        value = tokens[index].value
        if value in {"if", "function", "for", "while", "repeat"}:
            stack.append(value)
        elif value == "until":
            if stack and stack[-1] == "repeat":
                stack.pop()
        elif value == "else" and len(stack) == 1 and stack[-1] == "if":
            else_index = index
        elif value == "end":
            if stack and stack[-1] != "repeat":
                stack.pop()
                if not stack:
                    return else_index, index
        index += 1
    raise ValueError("unterminated Lua block")


def _find_dispatcher(tokens: list[_Token]) -> tuple[int, int, str]:
    for index, token in enumerate(tokens[:-2]):
        if token.value != "while":
            continue
        state = tokens[index + 1]
        if not _WORD.fullmatch(state.value) or tokens[index + 2].value != "do":
            continue
        _, end_index = _matching_end(tokens, index)
        return index, end_index, state.value
    raise ValueError("WAD VM dispatcher not found")


def _leading_partition(source: str, state_var: str) -> tuple[str, int, str, str] | None:
    tokens = _tokens(source)
    if not tokens or tokens[0].value != "if":
        return None
    try:
        then_index = next(index for index, token in enumerate(tokens) if token.value == "then")
    except StopIteration:
        return None
    else_index, end_index = _matching_end(tokens, 0)
    if else_index is None:
        return None
    if source[tokens[end_index].end:].strip():
        return None
    condition = source[tokens[0].end:tokens[then_index].start].strip()
    match = re.fullmatch(rf"{re.escape(state_var)}\s*(<=|>=|<|>)\s*(.+)", condition)
    if match is None:
        return None
    threshold = eval_int_expr(match.group(2))
    then_source = source[tokens[then_index].end:tokens[else_index].start]
    else_source = source[tokens[else_index].end:tokens[end_index].start]
    return match.group(1), threshold, then_source, else_source


def _extract_targets(source: str, state_var: str) -> tuple[tuple[int, ...], bool]:
    tokens = _tokens(source)
    unknown_true = object()
    unknown_false = object()
    unknown = frozenset((unknown_true, unknown_false))
    values: dict[str, frozenset[object]] = {}
    targets: list[int] = []
    terminal = False

    def is_truthy(value: object) -> bool:
        return value is unknown_true or (value is not unknown_false and value is not None and value is not False)

    def rhs_end(start: int) -> int:
        depth = 0
        index = start
        while index < len(tokens):
            value = tokens[index].value
            if value in {"(", "[", "{"}:
                depth += 1
            elif value in {")", "]", "}"}:
                if depth == 0:
                    break
                depth -= 1
            if depth == 0 and index > start:
                if value in {"local", "return", "if", "elseif", "else", "end", "for", "while", "repeat", "until"}:
                    break
                if _WORD.fullmatch(value) and index + 1 < len(tokens) and tokens[index + 1].value == "=":
                    break
            index += 1
        return index

    def eval_expr(expr: list[_Token]) -> frozenset[object]:
        position = 0

        def atom() -> frozenset[object]:
            nonlocal position
            if position >= len(expr):
                return unknown
            value = expr[position].value
            if value == "not":
                position += 1
                inner = atom()
                return frozenset(not is_truthy(item) for item in inner)
            if value == "(":
                position += 1
                inner = parse_or()
                if position < len(expr) and expr[position].value == ")":
                    position += 1
                return inner
            if value == "-" and position + 1 < len(expr) and expr[position + 1].value.isdigit():
                position += 2
                return frozenset((-int(expr[position - 1].value),))
            if value.isdigit():
                position += 1
                return frozenset((int(value),))
            if value == "true":
                position += 1
                return frozenset((True,))
            if value == "false":
                position += 1
                return frozenset((False,))
            if value == "nil":
                position += 1
                return frozenset((None,))
            if _WORD.fullmatch(value):
                position += 1
                return values.get(value, unknown)
            if value.startswith(("\"", "'")):
                position += 1
                return frozenset((unknown_true,))
            position += 1
            return unknown

        def parse_and() -> frozenset[object]:
            nonlocal position
            result = atom()
            while position < len(expr) and expr[position].value == "and":
                position += 1
                right = atom()
                combined: set[object] = set()
                for item in result:
                    if is_truthy(item):
                        combined.update(right)
                    else:
                        combined.add(item)
                result = frozenset(combined)
            return result

        def parse_or() -> frozenset[object]:
            nonlocal position
            result = parse_and()
            while position < len(expr) and expr[position].value == "or":
                position += 1
                right = parse_and()
                combined: set[object] = set()
                for item in result:
                    if is_truthy(item):
                        combined.add(item)
                    else:
                        combined.update(right)
                result = frozenset(combined)
            return result

        result = parse_or()
        if position != len(expr):
            return unknown
        return result

    index = 0
    while index + 2 < len(tokens):
        lhs = tokens[index].value
        if not _WORD.fullmatch(lhs) or tokens[index + 1].value != "=":
            index += 1
            continue
        start = index + 2
        end = rhs_end(start)
        if end <= start:
            index += 1
            continue
        result = eval_expr(tokens[start:end])
        values[lhs] = result
        if lhs == state_var:
            for item in result:
                if type(item) is int and item not in targets:
                    targets.append(item)
            if result and all(not is_truthy(item) for item in result):
                terminal = True
        index = end
    return tuple(targets), terminal


def _partition(source: str, state_var: str, lower: int | None, upper: int | None) -> list[VmBlock]:
    split = _leading_partition(source.strip(), state_var)
    if split is None:
        targets, terminal = _extract_targets(source, state_var)
        return [VmBlock(lower=lower, upper=upper, source=source.strip(), targets=targets, terminal=terminal)]
    operator, threshold, left, right = split
    if operator == "<":
        return _partition(left, state_var, lower, threshold) + _partition(right, state_var, threshold, upper)
    if operator == "<=":
        edge = threshold + 1
        return _partition(left, state_var, lower, edge) + _partition(right, state_var, edge, upper)
    if operator == ">":
        edge = threshold + 1
        return _partition(right, state_var, lower, edge) + _partition(left, state_var, edge, upper)
    return _partition(right, state_var, lower, threshold) + _partition(left, state_var, threshold, upper)


def extract_dispatcher(source: str) -> VmProgram:
    tokens = _tokens(source)
    while_index, end_index, state_var = _find_dispatcher(tokens)
    do_index = while_index + 2
    body = source[tokens[do_index].end:tokens[end_index].start]
    blocks = tuple(_partition(body, state_var, None, None))
    return VmProgram(state_var=state_var, blocks=blocks)


def infer_entry_state(source: str, program: VmProgram) -> int | None:
    tokens = _tokens(source)
    while_index, _, _ = _find_dispatcher(tokens)
    state_var = program.state_var
    function_index: int | None = None
    function_end: int | None = None
    for index in range(while_index - 1, -1, -1):
        if tokens[index].value != "function":
            continue
        try:
            _, end_index = _matching_end(tokens, index)
        except ValueError:
            continue
        if end_index > while_index:
            function_index = index
            function_end = end_index
            break
    if function_index is None or function_end is None:
        return None

    name: str | None = None
    parameter_index: int | None = None
    if function_index + 2 < len(tokens) and _WORD.fullmatch(tokens[function_index + 1].value) and tokens[function_index + 2].value == "(":
        name = tokens[function_index + 1].value
        parameter_index = function_index + 3
    elif function_index >= 2 and tokens[function_index - 1].value == "=" and _WORD.fullmatch(tokens[function_index - 2].value):
        name = tokens[function_index - 2].value
        if function_index + 1 < len(tokens) and tokens[function_index + 1].value == "(":
            parameter_index = function_index + 2
    if name is None or parameter_index is None or parameter_index >= len(tokens):
        return None
    if tokens[parameter_index].value != state_var:
        return None

    suffix = source[tokens[function_end].end:]
    call = re.search(rf"\b{re.escape(name)}\s*\(\s*(?P<expr>[-+*/%()\d\s]+?)\s*(?:,|\))", suffix)
    if call is None:
        return None
    try:
        return eval_int_expr(call.group("expr"))
    except ValueError:
        return None
