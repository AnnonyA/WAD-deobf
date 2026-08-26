from __future__ import annotations

import re

from .detector import detect_wad
from .expressions import eval_int_expr
from .scanner import find_balanced, split_top_level


def _decode_lua_string(literal: str) -> str:
    literal = literal.strip()
    if len(literal) < 2 or literal[0] not in "\"'" or literal[-1] != literal[0]:
        raise ValueError("expected Lua string literal")
    result: list[str] = []
    index = 1
    end = len(literal) - 1
    escapes = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}
    while index < end:
        char = literal[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue
        index += 1
        if index >= end:
            raise ValueError("invalid Lua escape")
        if literal[index].isdigit():
            stop = index
            while stop < end and stop < index + 3 and literal[stop].isdigit():
                stop += 1
            value = int(literal[index:stop], 10)
            if value > 255:
                raise ValueError("Lua decimal escape out of byte range")
            result.append(chr(value))
            index = stop
            continue
        escaped = literal[index]
        result.append(escapes.get(escaped, escaped))
        index += 1
    return "".join(result)


def extract_string_table(source: str) -> list[str]:
    info = detect_wad(source)
    body = source[info.table_start + 1 : info.table_end - 1]
    values: list[str] = []
    for item in split_top_level(body, ",;"):
        values.append(_decode_lua_string(item))
    return values


def _shuffle_table(source: str) -> str:
    info = detect_wad(source)
    tail = source[info.table_end :]
    match = re.search(r"for\s+\w+\s*,\s*\w+\s+in\s+ipairs\s*\(", tail)
    if match is None:
        raise ValueError("WAD shuffle table not found")
    absolute = info.table_end + match.end()
    while absolute < len(source) and source[absolute].isspace():
        absolute += 1
    if absolute >= len(source) or source[absolute] != "{":
        raise ValueError("WAD shuffle argument is not a table")
    _, end = find_balanced(source, absolute, "{", "}")
    return source[absolute + 1 : end - 1]


def recover_permutation(source: str, size: int) -> list[int]:
    order = list(range(size))
    for pair in split_top_level(_shuffle_table(source), ",;"):
        pair = pair.strip()
        if not (pair.startswith("{") and pair.endswith("}")):
            raise ValueError("malformed WAD shuffle range")
        values = split_top_level(pair[1:-1], ",;")
        if len(values) != 2:
            raise ValueError("malformed WAD shuffle range")
        left = eval_int_expr(values[0])
        right = eval_int_expr(values[1])
        if not (1 <= left <= size and 1 <= right <= size):
            raise ValueError("WAD shuffle range outside string table")
        if left < right:
            order[left - 1 : right] = reversed(order[left - 1 : right])
    return order


def _parse_alphabet_body(body: str) -> dict[str, int]:
    alphabet: dict[str, int] = {}
    for item in split_top_level(body, ",;"):
        bracket = re.match(r'^\s*\[(?P<key>"(?:\\.|[^"\\])*")\]\s*=\s*(?P<value>.+?)\s*$', item)
        if bracket:
            key = _decode_lua_string(bracket.group("key"))
            value_source = bracket.group("value")
        else:
            bare = re.match(r"^\s*(?P<key>[A-Za-z_]\w*)\s*=\s*(?P<value>.+?)\s*$", item)
            if bare is None:
                continue
            key = bare.group("key")
            value_source = bare.group("value")
        if len(key) != 1:
            continue
        alphabet[key] = eval_int_expr(value_source)
    return alphabet


def extract_alphabet(source: str) -> dict[str, int]:
    info = detect_wad(source)
    pattern = re.compile(r"local\s+[A-Za-z_]\w*\s*=\s*\{")
    for match in pattern.finditer(source, info.table_end):
        start = match.end() - 1
        try:
            _, end = find_balanced(source, start, "{", "}")
        except ValueError:
            continue
        lookahead = source[end : end + 300]
        if "string.sub" not in lookahead or "string.char" not in lookahead:
            continue
        alphabet = _parse_alphabet_body(source[start + 1 : end - 1])
        if len(alphabet) == 64 and set(alphabet.values()) == set(range(64)):
            return alphabet
    raise ValueError("valid WAD alphabet not found")


def decode_string(value: str, alphabet: dict[str, int]) -> bytes:
    if len(alphabet) != 64 or set(alphabet.values()) != set(range(64)):
        raise ValueError("invalid WAD alphabet")
    output = bytearray()
    accumulator = 0
    count = 0
    for char in value:
        mapped = alphabet.get(char)
        if mapped is not None:
            accumulator |= mapped << (18 - 6 * count)
            count += 1
            if count == 4:
                output.extend(((accumulator >> 16) & 0xFF, (accumulator >> 8) & 0xFF, accumulator & 0xFF))
                accumulator = 0
                count = 0
        elif char == "=":
            if count < 2:
                raise ValueError("truncated WAD string")
            output.append((accumulator >> 16) & 0xFF)
            if count >= 3:
                output.append((accumulator >> 8) & 0xFF)
            return bytes(output)
    if count:
        raise ValueError("truncated WAD string")
    return bytes(output)


def recover_strings(source: str) -> list[bytes]:
    table = extract_string_table(source)
    permutation = recover_permutation(source, len(table))
    shuffled = [table[index] for index in permutation]
    alphabet = extract_alphabet(source)
    return [decode_string(value, alphabet) for value in shuffled]
