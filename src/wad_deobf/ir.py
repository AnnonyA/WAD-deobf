from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VmBlock:
    lower: int | None
    upper: int | None
    source: str
    targets: tuple[int, ...]
    terminal: bool = False

    def contains(self, state: int) -> bool:
        return (self.lower is None or state >= self.lower) and (self.upper is None or state < self.upper)


@dataclass(frozen=True)
class VmProgram:
    state_var: str
    blocks: tuple[VmBlock, ...]

    def block_for_state(self, state: int) -> VmBlock | None:
        for block in self.blocks:
            if block.contains(state):
                return block
        return None
