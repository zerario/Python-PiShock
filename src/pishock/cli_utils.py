from __future__ import annotations

import dataclasses
import random
from typing import TypeVar

import rich

T = TypeVar("T", bound=float)

@dataclasses.dataclass
class Range:
    """A range with a minimum and maximum value."""

    a: T
    b: T

    def pick(self) -> T:
        return random.randint(self.a, self.b)


def print_error(e: type[zap.ApiError]) -> None:
    rich.print(f"[red]Error:[/] {e} ([red bold]{type(e).__name__}[/])")
