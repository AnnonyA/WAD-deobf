from __future__ import annotations

import re

from .lex import mask_non_code
from .models import PassResult


def _standalone_do_blocks(source: str):
    masked = mask_non_code(source)
    tokens = list(re.finditer(r'\b(?:function|if|for|while|do|repeat|end|until)\b', masked))
    stack = []
    spans = []
    for token in tokens:
        word = token.group(0)
        if word in {'for', 'while'}:
            stack.append(('pending_loop', token.start(), False))
        elif word == 'do':
            if stack and stack[-1][0] == 'pending_loop':
                kind, start, _ = stack.pop()
                stack.append(('loop', start, False))
            else:
                stack.append(('do', token.start(), True))
        elif word in {'function', 'if'}:
            stack.append((word, token.start(), False))
        elif word == 'repeat':
            stack.append(('repeat', token.start(), False))
        elif word == 'until':
            if stack and stack[-1][0] == 'repeat':
                stack.pop()
        elif word == 'end':
            if not stack:
                continue
            kind, start, standalone = stack.pop()
            if kind == 'do' and standalone:
                spans.append((start, token.end()))
    return spans


def _remove_matching_do(source: str, markers: tuple[str, ...]):
    candidates = []
    for start, end in _standalone_do_blocks(source):
        block = source[start:end]
        if all(marker in block for marker in markers):
            candidates.append((end - start, start, end))
    if not candidates:
        return PassResult(source)
    _, start, end = min(candidates)
    out = source[:start] + source[end:]
    return PassResult(out, 1, {'removed_span': [start, end]})


def remove_antitamper(source: str) -> PassResult:
    return _remove_matching_do(source, ('Tamper Detected!', 'pcallIntact', 'repeat until valid'))


def cleanup_dead_generated_scaffold(source: str) -> PassResult:
    return _remove_matching_do(source, ('35184372088832', 'charmap', 'realStrings'))
