from __future__ import annotations

import re


_ALIAS = re.compile(r"\blocal\s+(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<target>(?:math|string|table|coroutine|utf8|bit32)\.[A-Za-z_]\w*)")


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


def _mask_noncode(source: str) -> str:
    chars = list(source)
    index = 0
    while index < len(source):
        if source[index] in "\"'":
            end = _skip_string(source, index)
            for pos in range(index, end):
                chars[pos] = " "
            index = end
            continue
        if source.startswith("--[[", index):
            end = source.find("]]", index + 4)
            if end < 0:
                raise ValueError("unterminated Lua block comment")
            end += 2
            for pos in range(index, end):
                chars[pos] = " "
            index = end
            continue
        if source.startswith("--", index):
            end = source.find("\n", index + 2)
            end = len(source) if end < 0 else end
            for pos in range(index, end):
                chars[pos] = " "
            index = end
            continue
        index += 1
    return "".join(chars)


def _replace_calls_in_code(source: str, replacements: dict[str, str]) -> str:
    output: list[str] = []
    code_start = 0
    index = 0
    while index < len(source):
        if source[index] in "\"'":
            code = source[code_start:index]
            for name, target in replacements.items():
                code = re.sub(rf"\b{re.escape(name)}(?=\s*\()", target, code)
            output.append(code)
            end = _skip_string(source, index)
            output.append(source[index:end])
            index = end
            code_start = end
            continue
        if source.startswith("--", index):
            code = source[code_start:index]
            for name, target in replacements.items():
                code = re.sub(rf"\b{re.escape(name)}(?=\s*\()", target, code)
            output.append(code)
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
    code = source[code_start:]
    for name, target in replacements.items():
        code = re.sub(rf"\b{re.escape(name)}(?=\s*\()", target, code)
    output.append(code)
    return "".join(output)


def resolve_global_aliases(source: str) -> str:
    masked = _mask_noncode(source)
    replacements: dict[str, str] = {}
    for match in _ALIAS.finditer(masked):
        name = match.group("name")
        assignments = re.findall(rf"\b{re.escape(name)}\s*=", masked)
        if len(assignments) == 1:
            replacements[name] = match.group("target")
    if not replacements:
        return source
    return _replace_calls_in_code(source, replacements)
