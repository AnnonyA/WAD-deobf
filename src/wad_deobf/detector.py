from __future__ import annotations

from dataclasses import dataclass
import re

from .scanner import find_balanced


_MARKER = re.compile(r"--\[\[\s*v(?P<version>\d+\.\d+\.\d+)\s+https?://wearedevs\.net/obfuscator\s*\]\]")
_WRAPPER = re.compile(r"return\s*\(\s*function\s*\(\s*\.\.\.\s*\)")
_TABLE = re.compile(r"local\s+(?P<name>[A-Za-z_]\w*)\s*=\s*\{")


@dataclass(frozen=True)
class WadInfo:
    version: str | None
    table_name: str
    table_start: int
    table_end: int


def detect_wad(source: str) -> WadInfo:
    wrapper = _WRAPPER.search(source)
    if wrapper is None:
        raise ValueError("input does not match a WAD wrapper")
    table = _TABLE.search(source, wrapper.end())
    if table is None:
        raise ValueError("input does not contain a WAD string table")
    table_start = table.end() - 1
    _, table_end = find_balanced(source, table_start, "{", "}")
    tail = source[table_end:]
    name = table.group("name")
    has_shuffle = re.search(r"for\s+\w+\s*,\s*\w+\s+in\s+ipairs\s*\(", tail) is not None
    has_lookup = re.search(
        rf"local\s+function\s+\w+\s*\(\s*\w+\s*\)\s*return\s+{re.escape(name)}\s*\[",
        tail,
    ) is not None
    if not (has_shuffle and has_lookup):
        raise ValueError("input does not match WAD table/lookup structure")
    marker = _MARKER.search(source[: wrapper.start() + 1])
    return WadInfo(
        version=marker.group("version") if marker else None,
        table_name=name,
        table_start=table_start,
        table_end=table_end,
    )
