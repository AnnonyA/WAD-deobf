from __future__ import annotations

from dataclasses import dataclass

from .ir import VmProgram


@dataclass(frozen=True)
class StateGraph:
    states: tuple[int, ...]
    edges: tuple[tuple[int, int], ...]
    unresolved_targets: tuple[int, ...]
    truncated: bool = False


def build_state_graph(program: VmProgram, entry_state: int, max_steps: int = 10000) -> StateGraph:
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    queue = [entry_state]
    seen: set[int] = set()
    states: list[int] = []
    edges: list[tuple[int, int]] = []
    unresolved: list[int] = []
    truncated = False

    while queue:
        state = queue.pop(0)
        if state in seen:
            continue
        seen.add(state)
        states.append(state)
        block = program.block_for_state(state)
        if block is None:
            unresolved.append(state)
            continue
        if len(states) >= max_steps:
            if block.targets:
                truncated = True
            break
        for target in block.targets:
            edges.append((state, target))
            if program.block_for_state(target) is None:
                unresolved.append(target)
            elif target not in seen and target not in queue:
                queue.append(target)

    return StateGraph(
        states=tuple(states),
        edges=tuple(edges),
        unresolved_targets=tuple(dict.fromkeys(unresolved)),
        truncated=truncated,
    )
