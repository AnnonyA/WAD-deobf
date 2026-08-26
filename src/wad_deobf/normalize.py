from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Callable

from .detector import detect_wad
from .expressions import eval_int_expr, fold_int_expressions
from .scanner import find_balanced
from .strings import recover_strings


@dataclass(frozen=True)
class NormalizedWad:
    version: str | None
    decoded_strings: tuple[bytes, ...]
    lookup_name: str
    lookup_offset: int
    source: str


def _lookup_info(source: str, table_name: str) -> tuple[str, int]:
    pattern = re.compile(
        rf"local\s+function\s+(?P<name>[A-Za-z_]\w*)\s*\(\s*(?P<arg>[A-Za-z_]\w*)\s*\)"
        rf"\s*return\s+{re.escape(table_name)}\s*\[\s*(?P=arg)\s*(?P<sign>[+-])\s*(?P<offset>.*?)\]\s*end"
    )
    match = pattern.search(source)
    if match is None:
        raise ValueError("WAD string lookup function not found")
    offset = eval_int_expr(match.group("offset"))
    if match.group("sign") == "-":
        offset = -offset
    return match.group("name"), offset


def _lua_quote(value: bytes) -> str:
    chunks = ['"']
    index = 0
    while index < len(value):
        byte = value[index]
        if byte == 34:
            chunks.append('\\"')
        elif byte == 92:
            chunks.append("\\\\")
        elif 32 <= byte <= 126:
            chunks.append(chr(byte))
        elif byte >= 128:
            width = 2 if byte < 224 else 3 if byte < 240 else 4 if byte < 248 else 1
            chunk = value[index : index + width]
            try:
                text = chunk.decode("utf-8")
            except UnicodeDecodeError:
                chunks.append(f"\\{byte:03d}")
            else:
                if len(chunk) == width and text.isprintable():
                    chunks.append(text)
                    index += width - 1
                else:
                    chunks.append(f"\\{byte:03d}")
        else:
            chunks.append(f"\\{byte:03d}")
        index += 1
    chunks.append('"')
    return "".join(chunks)


def _replace_lookup_calls(code: str, name: str, offset: int, values: tuple[bytes, ...]) -> str:
    pattern = re.compile(rf"\b{re.escape(name)}\s*\(")
    result: list[str] = []
    cursor = 0
    while True:
        match = pattern.search(code, cursor)
        if match is None:
            result.append(code[cursor:])
            break
        opening = code.find("(", match.start(), match.end())
        try:
            _, end = find_balanced(code, opening, "(", ")")
        except ValueError:
            result.append(code[cursor:])
            break
        argument = code[opening + 1 : end - 1]
        try:
            table_index = eval_int_expr(argument) + offset
        except ValueError:
            result.append(code[cursor:end])
            cursor = end
            continue
        result.append(code[cursor:match.start()])
        if 1 <= table_index <= len(values):
            result.append(_lua_quote(values[table_index - 1]))
        else:
            result.append(code[match.start():end])
        cursor = end
    return "".join(result)


def _map_code(source: str, transform: Callable[[str], str]) -> str:
    output: list[str] = []
    code_start = 0
    index = 0
    while index < len(source):
        if source[index] in "\"'":
            output.append(transform(source[code_start:index]))
            quote = source[index]
            end = index + 1
            while end < len(source):
                if source[end] == "\\":
                    end += 2
                    continue
                if source[end] == quote:
                    end += 1
                    break
                end += 1
            if end > len(source):
                raise ValueError("unterminated Lua string")
            output.append(source[index:end])
            index = end
            code_start = end
            continue
        if source.startswith("--", index):
            output.append(transform(source[code_start:index]))
            if source.startswith("--[[", index):
                end = source.find("]]", index + 4)
                if end < 0:
                    raise ValueError("unterminated Lua block comment")
                end += 2
            else:
                end = source.find("\n", index + 2)
                end = len(source) if end < 0 else end + 1
            output.append(source[index:end])
            index = end
            code_start = end
            continue
        index += 1
    output.append(transform(source[code_start:]))
    return "".join(output)


def normalize_wad(source: str) -> NormalizedWad:
    info = detect_wad(source)
    values = tuple(recover_strings(source))
    lookup_name, lookup_offset = _lookup_info(source, info.table_name)
    replaced = _map_code(source, lambda code: _replace_lookup_calls(code, lookup_name, lookup_offset, values))
    folded = _map_code(replaced, fold_int_expressions)
    return NormalizedWad(
        version=info.version,
        decoded_strings=values,
        lookup_name=lookup_name,
        lookup_offset=lookup_offset,
        source=folded,
    )
