from __future__ import annotations

from dataclasses import dataclass
import re

from .lex import mask_non_code
from .models import PassResult


@dataclass(slots=True)
class VmReport:
    detected: bool = False
    position: str | None = None
    comparisons: int = 0
    states: int = 0


def _find_while(source: str):
    masked = mask_non_code(source)
    m = re.search(r'\bwhile\s+([A-Za-z_]\w*)\s+do\b', masked)
    if not m:
        return None
    pos = m.group(1)
    body_start = m.end()
    token_re = re.compile(r'\b(function|if|for|while|do|repeat|end|until)\b')
    stack = [('loop', False)]
    for t in token_re.finditer(masked, body_start):
        w = t.group(1)
        if w in {'for', 'while'}:
            stack.append(('pending_loop', False))
        elif w == 'do':
            if stack and stack[-1][0] == 'pending_loop':
                stack[-1] = ('loop', False)
            else:
                stack.append(('do', False))
        elif w in {'function', 'if'}:
            stack.append((w, False))
        elif w == 'repeat':
            stack.append(('repeat', False))
        elif w == 'until':
            if stack and stack[-1][0] == 'repeat':
                stack.pop()
        elif w == 'end':
            if not stack:
                continue
            if stack[-1][0] == 'repeat':
                continue
            stack.pop()
            if not stack:
                return pos, m.start(), body_start, t.start(), t.end()
    return None


def _simple_condition(cond: str, pos: str, state: int):
    m = re.fullmatch(r'\s*' + re.escape(pos) + r'\s*(<=|>=|==|~=|<|>)\s*(-?\d+)\s*', cond)
    if not m:
        return None
    rhs = int(m.group(2)); op = m.group(1)
    return {
        '<': state < rhs,
        '>': state > rhs,
        '<=': state <= rhs,
        '>=': state >= rhs,
        '==': state == rhs,
        '~=': state != rhs,
    }[op]


def _split_if(segment: str):
    masked = mask_non_code(segment)
    head = re.match(r'\s*if\s+(.+?)\s+then\b', masked, re.S)
    if not head:
        return None
    cond = segment[head.start(1):head.end(1)]
    token_re = re.compile(r'\b(function|if|for|while|do|repeat|elseif|else|end|until)\b')
    stack = ['if']
    boundary = None
    end_token = None
    for t in token_re.finditer(masked, head.end()):
        w = t.group(1)
        if w in {'for', 'while'}:
            stack.append('pending_loop')
        elif w == 'do':
            if stack and stack[-1] == 'pending_loop': stack[-1] = 'loop'
            else: stack.append('do')
        elif w in {'function', 'if'}:
            stack.append(w)
        elif w == 'repeat':
            stack.append('repeat')
        elif w == 'until':
            if stack and stack[-1] == 'repeat': stack.pop()
        elif w in {'else', 'elseif'} and len(stack) == 1 and stack[-1] == 'if' and boundary is None:
            boundary = (w, t.start(), t.end())
        elif w == 'end':
            if stack and stack[-1] != 'repeat': stack.pop()
            if not stack:
                end_token = t
                break
    if not end_token:
        return None
    if boundary:
        kind, bstart, bend = boundary
        yes = segment[head.end():bstart]
        if kind == 'else':
            no = segment[bend:end_token.start()]
        else:
            no = 'if ' + segment[bend:end_token.start()].lstrip() + ' end'
    else:
        yes = segment[head.end():end_token.start()]
        no = ''
    return cond, yes, no


def _select_leaf(segment: str, pos: str, state: int):
    current = segment.strip()
    while True:
        split = _split_if(current)
        if not split:
            return current
        cond, yes, no = split
        decision = _simple_condition(cond, pos, state)
        if decision is None:
            return current
        current = (yes if decision else no).strip()


def analyze_vm(source: str) -> VmReport:
    found = _find_while(source)
    if not found:
        return VmReport()
    pos, _, body_start, body_end, _ = found
    body = mask_non_code(source[body_start:body_end])
    comparisons = len(re.findall(r'\b' + re.escape(pos) + r'\s*(?:<=|>=|==|~=|<|>)\s*-?\d+', body))
    assignments = set(int(x) for x in re.findall(r'\b' + re.escape(pos) + r'\s*=\s*(-?\d+)\b', body))
    return VmReport(comparisons > 0, pos, comparisons, len(assignments))


def lift_linear_dispatcher(source: str) -> PassResult:
    found = _find_while(source)
    if not found:
        return PassResult(source, details={'unresolved': False})
    pos, while_start, body_start, body_end, while_end = found
    before = source[:while_start]
    assigns = list(re.finditer(r'(?:\blocal\s+)?\b' + re.escape(pos) + r'\s*=\s*(-?\d+)\b\s*;?', mask_non_code(before)))
    if not assigns:
        return PassResult(source, details={'unresolved': True, 'reason': 'initial-state-not-found'})
    initial = assigns[-1]
    state = int(initial.group(1))
    dispatcher = source[body_start:body_end]
    emitted = []
    resolved = []
    visited = set()
    while state not in visited and len(visited) < 10000:
        visited.add(state); resolved.append(state)
        leaf = _select_leaf(dispatcher, pos, state)
        masked_leaf = mask_non_code(leaf)
        next_assigns = list(re.finditer(r'\b' + re.escape(pos) + r'\s*=\s*(nil|-?\d+)\b\s*;?', masked_leaf))
        if len(next_assigns) != 1:
            return PassResult(source, details={'unresolved': True, 'resolved_states': resolved, 'reason': 'runtime-dependent-transition'})
        a = next_assigns[0]
        clean = (leaf[:a.start()] + leaf[a.end():]).strip()
        if clean:
            emitted.append(clean)
        target = a.group(1)
        if target == 'nil':
            prefix = source[:initial.start()]
            suffix = source[while_end:]
            replacement = '\n'.join(emitted)
            return PassResult(prefix + replacement + suffix, 1, {'unresolved': False, 'resolved_states': resolved})
        state = int(target)
    return PassResult(source, details={'unresolved': True, 'resolved_states': resolved, 'reason': 'state-cycle'})
