from __future__ import annotations


def code_spans(source: str):
    i = 0
    start = 0
    n = len(source)
    while i < n:
        if source.startswith('--[[', i):
            if start < i:
                yield start, i
            j = source.find(']]', i + 4)
            i = n if j < 0 else j + 2
            start = i
            continue
        if source.startswith('--', i):
            if start < i:
                yield start, i
            j = source.find('\n', i + 2)
            i = n if j < 0 else j
            start = i
            continue
        if source[i] in "'\"":
            if start < i:
                yield start, i
            q = source[i]
            i += 1
            while i < n:
                if source[i] == '\\':
                    i += 2
                    continue
                if source[i] == q:
                    i += 1
                    break
                i += 1
            start = i
            continue
        i += 1
    if start < n:
        yield start, n


def mask_non_code(source: str) -> str:
    out = [' '] * len(source)
    for a, b in code_spans(source):
        out[a:b] = source[a:b]
    return ''.join(out)
