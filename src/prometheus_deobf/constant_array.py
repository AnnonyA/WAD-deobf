from __future__ import annotations

import re

from .literals import decode_lua_string, encode_lua_string
from .models import PassResult
from .numbers import eval_numeric

_STRING = re.compile(r'(["\'])(?:\\.|(?!\1).)*\1', re.S)


def _balanced(src: str, start: int, open_ch: str = '{', close_ch: str = '}'):
    depth = 0
    i = start
    quote = None
    while i < len(src):
        c = src[i]
        if quote:
            if c == '\\': i += 2; continue
            if c == quote: quote = None
            i += 1; continue
        if c in "'\"": quote = c; i += 1; continue
        if src.startswith('--[[', i):
            j = src.find(']]', i + 4); i = len(src) if j < 0 else j + 2; continue
        if src.startswith('--', i):
            j = src.find('\n', i + 2); i = len(src) if j < 0 else j; continue
        if c == open_ch: depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0: return i + 1
        i += 1
    return None


def _lookup(source: str):
    pairs = re.findall(r'\[\s*(["\'])(.)\1\s*\]\s*=\s*(\d+)', source)
    mapping = {ch: int(value) for _, ch, value in pairs if int(value) < 64}
    if len(mapping) != 64 or set(mapping.values()) != set(range(64)):
        return None
    return mapping


def _decode(value: str, lookup: dict[str, int]):
    out = bytearray()
    acc = 0
    count = 0
    i = 0
    while i < len(value):
        ch = value[i]
        if ch in lookup:
            acc += lookup[ch] * (64 ** (3 - count))
            count += 1
            if count == 4:
                out.extend((acc // 65536, (acc % 65536) // 256, acc % 256))
                acc = 0; count = 0
        elif ch == '=':
            out.append(acc // 65536)
            if i + 1 >= len(value) or value[i + 1] != '=':
                out.append((acc % 65536) // 256)
            break
        i += 1
    try:
        return out.decode('utf-8')
    except UnicodeDecodeError:
        return out.decode('latin1')


def _arrays(source: str):
    pat = re.compile(r'\blocal\s+([A-Za-z_]\w*)\s*=\s*\{')
    for m in pat.finditer(source):
        start = source.find('{', m.start())
        end = _balanced(source, start)
        if not end: continue
        body = source[start + 1:end - 1]
        tokens = [x.group(0) for x in _STRING.finditer(body)]
        if not tokens: continue
        residue = _STRING.sub('', body)
        if re.sub(r'[\s,;]', '', residue):
            continue
        try:
            values = [decode_lua_string(t) for t in tokens]
        except ValueError:
            continue
        yield m.group(1), m.start(), end, values


def _apply_runtime_rotation(source: str, name: str, values: list[str]):
    arr = re.escape(name)
    p = re.compile(
        r'for\s+\w+\s*,\s*\w+\s+in\s+ipairs\s*\(\s*\{\s*'
        r'\{\s*1\s*,\s*(\d+)\s*\}\s*,?\s*'
        r'\{\s*1\s*,\s*(\d+)\s*\}\s*,?\s*'
        r'\{\s*(\d+)\s*,\s*(\d+)\s*\}\s*\}\s*\)\s+do\s+'
        r'while\s+\w+\[1\]\s*<\s*\w+\[2\]\s+do\s+' + arr,
        re.S,
    )
    m = p.search(source)
    if not m:
        return values
    ranges = [(1, int(m.group(1))), (1, int(m.group(2))), (int(m.group(3)), int(m.group(4)))]
    out = list(values)
    for lo, hi in ranges:
        lo -= 1; hi -= 1
        while 0 <= lo < hi < len(out):
            out[lo], out[hi] = out[hi], out[lo]
            lo += 1; hi -= 1
    return out


def _wrapper(source: str, arr_name: str):
    a = re.escape(arr_name)
    patterns = [
        re.compile(r'local\s+function\s+(\w+)\s*\(\s*(\w+)\s*\)\s*return\s+' + a + r'\s*\[\s*\2\s*([+-])\s*(\d+)\s*\]\s*end'),
        re.compile(r'local\s+(\w+)\s*=\s*function\s*\(\s*(\w+)\s*\)\s*return\s+' + a + r'\s*\[\s*\2\s*([+-])\s*(\d+)\s*\]\s*end'),
    ]
    for p in patterns:
        m = p.search(source)
        if m:
            offset = int(m.group(4)) * (1 if m.group(3) == '+' else -1)
            return m.group(1), offset
    return None


def recover_constant_arrays(source: str) -> PassResult:
    lookup = _lookup(source)
    if not lookup:
        return PassResult(source)
    best = None
    for item in _arrays(source):
        if len(item[3]) >= 2:
            best = item
            break
    if not best:
        return PassResult(source)
    name, _, _, encoded = best
    encoded = _apply_runtime_rotation(source, name, encoded)
    decoded = [_decode(v, lookup) for v in encoded]
    out = source
    changes = 0

    wrap = _wrapper(out, name)
    if wrap:
        func, offset = wrap
        call = re.compile(r'\b' + re.escape(func) + r'\s*\(\s*([^()]+?)\s*\)')
        def repl(m):
            nonlocal changes
            value = eval_numeric(m.group(1))
            if value is None or not float(value).is_integer(): return m.group(0)
            idx = int(value) + offset
            if not 1 <= idx <= len(decoded): return m.group(0)
            changes += 1
            return encode_lua_string(decoded[idx - 1])
        out = call.sub(repl, out)

    direct = re.compile(r'\b' + re.escape(name) + r'\s*\[\s*([^\[\]]+?)\s*\]')
    def direct_repl(m):
        nonlocal changes
        value = eval_numeric(m.group(1))
        if value is None or not float(value).is_integer(): return m.group(0)
        idx = int(value)
        if not 1 <= idx <= len(decoded): return m.group(0)
        changes += 1
        return encode_lua_string(decoded[idx - 1])
    out = direct.sub(direct_repl, out)
    return PassResult(out, changes, {'decoded_entries': len(decoded), 'array': name})
