from __future__ import annotations

import re
import dataclasses
import random
import pathlib
import json
from typing import Any, Optional, Union, Callable

import platformdirs
import click
import rich
import typer

from pishock.zap import serialapi, httpapi

SHARE_CODE_REGEX = re.compile(r"^[0-9A-F]{11}$")  # 11 upper case hex digits
SHOCKER_ID_REGEX = re.compile(r"^[0-9]{3,5}$")  # 3-5 decimal digits


@dataclasses.dataclass
class ShockerInfo:
    sharecode: str
    shocker_id: int | None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def __str__(self) -> str:
        return str(self.sharecode or self.shocker_id or "???")


class Config:
    def __init__(self) -> None:
        self._path = pathlib.Path(
            platformdirs.user_config_dir(appname="PiShock-CLI", appauthor="PiShock"),
            "config.json",
        )

        self.username: str | None = None
        self.api_key: str | None = None
        self.shockers: dict[str, ShockerInfo] = {}

    def load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r") as f:
            data = json.load(f)

        self.username = data["api"]["username"]
        self.api_key = data["api"]["key"]

        if "sharecodes" in data:
            self.shockers = {
                name: ShockerInfo(sharecode=sharecode, shocker_id=None)
                for name, sharecode in data["sharecodes"].items()
            }
        elif "shockers" in data:
            self.shockers = {
                name: ShockerInfo(**info) for name, info in data["shockers"].items()
            }
        else:
            self.shockers = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "api": {
                "username": self.username,
                "key": self.api_key,
            },
            "shockers": {name: info.to_dict() for name, info in self.shockers.items()},
        }
        with self._path.open("w") as f:
            json.dump(data, f)


@dataclasses.dataclass
class AppContext:
    config: Config
    pishock_api: httpapi.PiShockAPI | None
    serial_api: serialapi.SerialAPI | None

    def ensure_serial_api(self) -> serialapi.SerialAPI:
        if self.serial_api is None:
            print_error("This command is only available with the serial API.")
            raise typer.Exit(1)
        return self.serial_api

    def ensure_pishock_api(self) -> httpapi.PiShockAPI:
        if self.pishock_api is None:
            print_error("This command is only available with the HTTP API.")
            raise typer.Exit(1)
        return self.pishock_api


@dataclasses.dataclass
class Range:
    """A range with a minimum and maximum value."""

    a: int
    b: int

    def __post_init__(self) -> None:
        if self.b < self.a:
            raise ValueError("Min must be less than max.")

    def pick(self) -> int:
        return random.randint(self.a, self.b)


def print_exception(e: Exception) -> None:
    rich.print(f"[red]Error:[/] {e} ([red bold]{type(e).__name__}[/])")


def print_error(s: str) -> None:
    rich.print(f"[red]Error:[/] {s}")


def bool_emoji(value: bool) -> str:
    return ":white_check_mark:" if value else ":x:"


def paused_emoji(is_paused: bool) -> str:
    return ":double_vertical_bar:" if is_paused else ":arrow_forward:"

class RangeParser(click.ParamType):
    name = "Range"

    def __init__(
        self, min: int, max: Optional[int] = None, converter: Callable[[str], int] = int
    ) -> None:
        self.min = min
        self.max = max
        self.converter = converter

    def _parse_single(self, s: str) -> int:
        try:
            n = self.converter(s)
        except ValueError:
            self.fail(f"Value must be a {self.converter.__name__}: {s}")

        if self.max is None and n < self.min:
            self.fail(f"Value must be at least {self.min}: {n}")
        if self.max is not None and not (self.min <= n <= self.max):
            self.fail(f"Value must be between {self.min} and {self.max}: {n}")

        return n

    def convert(
        self,
        value: Union[str, Range],
        param: Optional[click.Parameter],
        ctx: Optional[click.Context],
    ) -> Range:
        if isinstance(value, Range):  # default value
            return value

        if "-" not in value:
            n = self._parse_single(value)
            return Range(n, n)

        if value.count("-") > 1:
            self.fail("Range must be in the form min-max.")

        a_str, b_str = value.split("-")
        a = self._parse_single(a_str)
        b = self._parse_single(b_str)

        try:
            return Range(a, b)
        except ValueError as e:
            self.fail(str(e))

def parse_duration(duration: str) -> int:
    """Parse duration in format XhYmZs into second duration."""
    if duration.isdigit():
        return int(duration)

    match = re.fullmatch(
        r"(?P<hours>[0-9]+(\.[0-9])?h)?\s*"
        r"(?P<minutes>[0-9]+(\.[0-9])?m)?\s*"
        r"(?P<seconds>[0-9]+(\.[0-9])?s)?",
        duration,
    )

    if not match or not match.group(0):
        raise ValueError(
            f"Invalid duration: {duration} - expected XhYmZs or a number of seconds"
        )

    seconds_string = match.group("seconds") if match.group("seconds") else "0"
    seconds = float(seconds_string.rstrip("s"))
    minutes_string = match.group("minutes") if match.group("minutes") else "0"
    minutes = float(minutes_string.rstrip("m"))
    hours_string = match.group("hours") if match.group("hours") else "0"
    hours = float(hours_string.rstrip("h"))

    return int(seconds + minutes * 60 + hours * 3600)
