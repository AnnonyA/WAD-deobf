from __future__ import annotations


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


def _skip_comment(source: str, index: int) -> int:
    if source.startswith("--[[", index):
        end = source.find("]]", index + 4)
        if end < 0:
            raise ValueError("unterminated Lua block comment")
        return end + 2
    end = source.find("\n", index + 2)
    return len(source) if end < 0 else end + 1


def find_balanced(source: str, start: int, opening: str, closing: str) -> tuple[int, int]:
    if start < 0 or start >= len(source) or source[start] != opening:
        raise ValueError("balanced fragment does not start with opening delimiter")
    depth = 0
    index = start
    while index < len(source):
        char = source[index]
        if char in "\"'":
            index = _skip_string(source, index)
            continue
        if source.startswith("--", index):
            index = _skip_comment(source, index)
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return start, index + 1
        index += 1
    raise ValueError("unclosed balanced fragment")


def split_top_level(source: str, separators: str = ",") -> list[str]:
    parts: list[str] = []
    start = 0
    index = 0
    stack: list[str] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    while index < len(source):
        char = source[index]
        if char in "\"'":
            index = _skip_string(source, index)
            continue
        if source.startswith("--", index):
            index = _skip_comment(source, index)
            continue
        if char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif not stack and char in separators:
            item = source[start:index].strip()
            if item:
                parts.append(item)
            start = index + 1
        index += 1
    if stack:
        raise ValueError("unclosed nested fragment")
    item = source[start:].strip()
    if item:
        parts.append(item)
    return parts
