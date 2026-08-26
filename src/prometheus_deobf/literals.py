from __future__ import annotations


def decode_lua_string(token: str) -> str:
    if len(token) < 2 or token[0] not in "'\"" or token[-1] != token[0]:
        raise ValueError('expected quoted Lua string')
    s = token[1:-1]
    out = []
    i = 0
    escapes = {'n': '\n', 'r': '\r', 't': '\t', '\\': '\\', '"': '"', "'": "'", 'a': '\a', 'b': '\b', 'f': '\f', 'v': '\v'}
    while i < len(s):
        if s[i] != '\\':
            out.append(s[i]); i += 1; continue
        i += 1
        if i >= len(s):
            out.append('\\'); break
        if s[i].isdigit():
            j = i
            while j < len(s) and j < i + 3 and s[j].isdigit():
                j += 1
            out.append(chr(int(s[i:j], 10) % 256))
            i = j
            continue
        if s[i] == 'z':
            i += 1
            while i < len(s) and s[i].isspace():
                i += 1
            continue
        out.append(escapes.get(s[i], s[i]))
        i += 1
    return ''.join(out)


def encode_lua_string(value: str) -> str:
    out = ['"']
    for ch in value:
        code = ord(ch)
        if ch == '\\': out.append('\\\\')
        elif ch == '"': out.append('\\"')
        elif ch == '\n': out.append('\\n')
        elif ch == '\r': out.append('\\r')
        elif ch == '\t': out.append('\\t')
        elif 32 <= code <= 126: out.append(ch)
        else: out.append(f'\\{code:03d}')
    out.append('"')
    return ''.join(out)
