from __future__ import annotations

import dataclasses
import random

import rich


@dataclasses.dataclass
class Range:
    """A range with a minimum and maximum value."""

    a: int
    b: int

    def pick(self) -> int:
        return random.randint(self.a, self.b)


def print_exception(e: Exception) -> None:
    rich.print(f"[red]Error:[/] {e} ([red bold]{type(e).__name__}[/])")


def print_error(s: str) -> None:
    rich.print(f"[red]Error:[/] {s}")


def bool_emoji(value: bool) -> str:
    return ":white_check_mark:" if value else ":x:"
