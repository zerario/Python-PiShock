from __future__ import annotations

import re
import dataclasses
import random
import pathlib
import json

import platformdirs
import rich
import typer

from pishock.zap import serialapi, httpapi

SHARE_CODE_REGEX = re.compile(r"^[0-9A-F]{11}$")  # 11 upper case hex digits


class Config:
    def __init__(self) -> None:
        self._path = pathlib.Path(
            platformdirs.user_config_dir(appname="PiShock-CLI", appauthor="PiShock"),
            "config.json",
        )

        self.username: str | None = None
        self.api_key: str | None = None
        self.sharecodes: dict[str, str] = {}

    def load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r") as f:
            data = json.load(f)

        self.username = data["api"]["username"]
        self.api_key = data["api"]["key"]
        self.sharecodes = data.get("sharecodes", {})

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "api": {
                "username": self.username,
                "key": self.api_key,
            },
            "sharecodes": self.sharecodes,
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
