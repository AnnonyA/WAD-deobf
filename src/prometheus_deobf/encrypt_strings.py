from __future__ import annotations

import math
import re

from .literals import decode_lua_string, encode_lua_string
from .models import PassResult


def decrypt_string(cipher: str, seed: int, mul45: int, add45: int, mul8: int, key8: int) -> str:
    state45 = seed % 35184372088832
    state8 = seed % 255 + 2
    prev_values: list[int] = []
    prev = key8
    out = bytearray()
    for enc in (ord(ch) & 255 for ch in cipher):
        if not prev_values:
            state45 = (state45 * mul45 + add45) % 35184372088832
            while True:
                state8 = state8 * mul8 % 257
                if state8 != 1:
                    break
            r = state8 % 32
            shift = 13 - (state8 - r) // 32
            n = math.floor(state45 / (2 ** shift)) % (2 ** 32) / (2 ** r)
            rnd = math.floor((n % 1) * (2 ** 32)) + math.floor(n)
            low = rnd % 65536
            high = (rnd - low) // 65536
            prev_values = [low % 256, low // 256, high % 256, high // 256]
        rand = prev_values.pop()
        prev = (enc + rand + prev) % 256
        out.append(prev)
    try:
        return out.decode('utf-8')
    except UnicodeDecodeError:
        return out.decode('latin1')


def _params(source: str):
    m45 = re.search(
        r'(\w+)\s*=\s*\(\s*\1\s*\*\s*(\d+)\s*\+\s*(\d+)\s*\)\s*%\s*35184372088832',
        source,
    )
    m8 = re.search(r'(\w+)\s*=\s*\1\s*\*\s*(\d+)\s*%\s*257', source)
    if not m45 or not m8:
        return None
    key_candidates = re.findall(r'local\s+\w+\s*=\s*(\d+)\s*;?', source)
    if not key_candidates:
        return None
    byte_keys = [int(x) for x in key_candidates if 0 <= int(x) <= 255]
    if not byte_keys:
        return None
    return int(m45.group(2)), int(m45.group(3)), int(m8.group(2)), byte_keys[-1]


def recover_encrypted_strings(source: str) -> PassResult:
    if '35184372088832' not in source or '%257' not in source.replace(' ', ''):
        return PassResult(source)
    params = _params(source)
    if not params:
        return PassResult(source)
    mul45, add45, mul8, key8 = params
    string_token = r'(["\'](?:\\.|[^"\'\\])*["\'])'
    pat = re.compile(
        r'\b([A-Za-z_]\w*)\s*\[\s*([A-Za-z_]\w*)\s*\(\s*' + string_token + r'\s*,\s*(\d+)\s*\)\s*\]'
    )
    changes = 0

    def repl(m):
        nonlocal changes
        try:
            cipher = decode_lua_string(m.group(3))
            plain = decrypt_string(cipher, int(m.group(4)), mul45, add45, mul8, key8)
        except (ValueError, OverflowError):
            return m.group(0)
        changes += 1
        return encode_lua_string(plain)

    out = pat.sub(repl, source)
    return PassResult(out, changes, {
        'mul45': mul45,
        'add45': add45,
        'mul8': mul8,
        'key8': key8,
    })
