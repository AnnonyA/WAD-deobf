from __future__ import annotations


def _find_function_end(src: str, start: int):
    i = start
    depth = 0
    openers = {'function', 'if', 'for', 'while', 'do'}
    while i < len(src):
        c = src[i]
        if c in "'\"":
            q = c; i += 1
            while i < len(src):
                if src[i] == '\\': i += 2; continue
                if src[i] == q: i += 1; break
                i += 1
            continue
        if src.startswith('--', i):
            j = src.find('\n', i + 2); i = len(src) if j < 0 else j; continue
        if c.isalpha() or c == '_':
            j = i + 1
            while j < len(src) and (src[j].isalnum() or src[j] == '_'): j += 1
            word = src[i:j]
            if word in openers:
                depth += 1
            elif word == 'end':
                depth -= 1
                if depth == 0:
                    return i, j
            i = j; continue
        i += 1
    return None


def unwrap_generated_iife(source: str):
    stripped = source.strip()
    prefix = 'return(function(...)'
    if not stripped.startswith(prefix):
        return source, 0
    fn_start = stripped.find('function')
    match = _find_function_end(stripped, fn_start)
    if not match:
        return source, 0
    end_start, end_end = match
    tail = stripped[end_end:].strip()
    if tail not in {')(... )', ')(...)', ')(...);', '(...)', '(...);'}:
        return source, 0
    body_start = stripped.find(')', fn_start) + 1
    return stripped[body_start:end_start].strip(), 1
