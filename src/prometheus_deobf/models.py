from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PassResult:
    source: str
    changes: int = 0
    details: dict = field(default_factory=dict)
