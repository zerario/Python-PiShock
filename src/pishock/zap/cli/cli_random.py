import contextlib
import dataclasses
import random
import re
import time
from typing import Iterator, List, Optional, Union, Callable

import click
import rich
import typer
from typing_extensions import Annotated, TypeAlias

from pishock.zap import httpapi, core
from pishock.zap.cli import cli_utils as utils


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
        value: Union[str, utils.Range],
        param: Optional[click.Parameter],
        ctx: Optional[click.Context],
    ) -> utils.Range:
        if isinstance(value, utils.Range):  # default value
            return value

        if "-" not in value:
            n = self._parse_single(value)
            return utils.Range(n, n)

        if value.count("-") > 1:
            self.fail("Range must be in the form min-max.")

        a_str, b_str = value.split("-")
        a = self._parse_single(a_str)
        b = self._parse_single(b_str)

        try:
            return utils.Range(a, b)
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


@dataclasses.dataclass
class SpamSettings:
    possibility: int
    operations: utils.Range
    pause: utils.Range
    duration: utils.Range
    intensity: Optional[utils.Range]


class RandomShocker:
    def __init__(
        self,
        shockers: List[core.Shocker],
        duration: utils.Range,
        intensity: utils.Range,
        pause: utils.Range,
        init_delay: utils.Range,
        spam_settings: SpamSettings,
        max_runtime: Optional[utils.Range],
        vibrate_duration: Optional[utils.Range],
        vibrate_intensity: Optional[utils.Range],
        shock: bool,
        vibrate: bool,
    ) -> None:
        self.shockers = shockers
        self.duration = duration
        self.intensity = intensity
        self.pause = pause
        self.init_delay = init_delay
        self.spam_settings = spam_settings
        self.max_runtime = max_runtime
        self.vibrate_duration = vibrate_duration
        self.vibrate_intensity = vibrate_intensity

        self.start_time = time.monotonic()
        self.operations = []
        if shock:
            self.operations.append(httpapi.Operation.SHOCK)
        if vibrate:
            self.operations.append(httpapi.Operation.VIBRATE)

    def _log(self, message: str) -> None:
        rich.print(message)  # TODO

    @contextlib.contextmanager
    def _handle_errors(self) -> Iterator[None]:
        try:
            yield
        except (httpapi.APIError, ValueError) as e:
            utils.print_exception(e)

    def _spam(self) -> None:
        assert httpapi.Operation.SHOCK in self.operations
        self._log("[red bold]Spamming.[/]")
        for _ in range(self.spam_settings.operations.pick()):
            shocker = random.choice(self.shockers)
            duration = self.spam_settings.duration.pick()
            intensity = (self.spam_settings.intensity or self.intensity).pick()

            try:
                shocker.shock(duration=duration, intensity=intensity)
            except (httpapi.APIError, ValueError):
                rich.print(":x:", end="", flush=True)
            else:
                rich.print(f":zap: [green]{intensity}[/green] ", end="", flush=True)
            time.sleep(duration + 0.3)

            pause = self.spam_settings.pause.pick()
            time.sleep(pause)

        rich.print()

    def _shock(self, shocker: core.Shocker) -> None:
        duration = self.duration.pick()
        intensity = self.intensity.pick()
        self._log(
            f":zap: [yellow]Shocking[/] [green]{shocker}[/] for [green]{duration}s[/] "
            f"at [green]{intensity}%[/]."
        )
        with self._handle_errors():
            shocker.shock(duration=duration, intensity=intensity)
        time.sleep(duration)

    def _vibrate(self, shocker: core.Shocker) -> None:
        duration = (self.vibrate_duration or self.duration).pick()
        intensity = (self.vibrate_intensity or self.intensity).pick()
        self._log(
            f":vibration_mode: [cyan]Vibrating[/] [green]{shocker}[/] for "
            f"[green]{duration}s[/] at [green]{intensity}%[/]."
        )
        with self._handle_errors():
            shocker.vibrate(duration=duration, intensity=intensity)
        time.sleep(duration)

    def run(self) -> None:
        if self.init_delay:
            delay = self.init_delay.pick()
            self._log(f":zzz: [blue]Initial delay[/] of [green]{delay}[/] seconds.")
            time.sleep(delay)

        max_runtime = self.max_runtime.pick() if self.max_runtime else None
        self._log(f":clock1: [blue]Max runtime[/] is [green]{max_runtime}[/] seconds.")

        while max_runtime is None or (time.monotonic() - self.start_time) < max_runtime:
            self._tick()
            pause = self.pause.pick()
            self._log(f":zzz: [blue]Sleeping[/] for [green]{pause}[/] seconds.")
            time.sleep(pause)

    def _tick(self) -> None:
        if random.randint(1, 100) <= self.spam_settings.possibility:
            self._spam()
            return

        operation = random.choice(self.operations)
        shocker = random.choice(self.shockers)

        if operation == httpapi.Operation.SHOCK:
            self._shock(shocker)
        elif operation == httpapi.Operation.VIBRATE:
            self._vibrate(shocker)
        else:  # pragma: no cover
            raise ValueError(f"Invalid operation: {operation}")


DurationArg: TypeAlias = Annotated[
    utils.Range,
    typer.Option(
        "-d",
        "--duration",
        help=(
            "Duration in seconds, as a single value or a min-max range (0-15 "
            "respectively)."
        ),
        click_type=RangeParser(min=0, max=15),
    ),
]

IntensityArg: TypeAlias = Annotated[
    utils.Range,
    typer.Option(
        "-i",
        "--intensity",
        help=(
            "Intensity in percent, as a single value or min-max range (0-100 "
            "respectively)."
        ),
        click_type=RangeParser(min=0, max=100),
    ),
]

PauseArg: TypeAlias = Annotated[
    utils.Range,
    typer.Option(
        "-p",
        "--pause",
        help="Delay between operations, in seconds or a string like "
        "1h2m3s (with h/m being optional). With a min-max range of such values, "
        "picked randomly.",
        click_type=RangeParser(min=0, converter=parse_duration),
    ),
]

InitDelayArg: TypeAlias = Annotated[
    utils.Range,
    typer.Option(
        "--init-delay",
        help="Initial delay before the first operation, in seconds or a string like "
        "1h2m3s (with h/m being optional). With a min-max range of such values, "
        "picked randomly.",
        click_type=RangeParser(min=0, converter=parse_duration),
    ),
]

SpamPossibilityArg: TypeAlias = Annotated[
    int,
    typer.Option(
        help="Possibility of spamming in percent (0-100).",
        min=0,
        max=100,
    ),
]

SpamOperationsArg: TypeAlias = Annotated[
    utils.Range,
    typer.Option(
        help="Number of operations to spam, as a single value or min-max range.",
        click_type=RangeParser(min=1),
    ),
]

SpamPauseArg: TypeAlias = Annotated[
    utils.Range,
    typer.Option(
        help="Delay between spam operations, in seconds or a string like "
        "1h2m3s (with h/m being optional). With a min-max range of such values, "
        "picked randomly.",
        click_type=RangeParser(min=0, converter=parse_duration),
    ),
]

SpamDurationArg: TypeAlias = Annotated[
    utils.Range,
    typer.Option(
        help=(
            "Duration of spam operations in seconds, as a single value or min-max "
            "range."
        ),
        click_type=RangeParser(min=0, max=15),
    ),
]

SpamIntensityArg: TypeAlias = Annotated[
    Optional[utils.Range],
    typer.Option(
        help=(
            "Intensity of spam operations in percent, as a single value or min-max "
            "range. If not given, normal intensity is used."
        ),
        click_type=RangeParser(min=0, max=100),
    ),
]

MaxRuntimeArg: TypeAlias = Annotated[
    Optional[utils.Range],
    typer.Option(
        help=(
            "Maximum runtime in seconds or a string like 1h2m3s (with h/m being "
            "optional). With a min-max range of such values, picked randomly."
        ),
        click_type=RangeParser(min=0, converter=parse_duration),
    ),
]

VibrateDurationArg: TypeAlias = Annotated[
    Optional[utils.Range],
    typer.Option(
        help=(
            "Duration for vibration in seconds, as a single value or a min-max "
            "range (0-15 respectively). If not given, --duration is used."
        ),
        click_type=RangeParser(min=0, max=15),
    ),
]

VibrateIntensityArg: TypeAlias = Annotated[
    Optional[utils.Range],
    typer.Option(
        help=(
            "Intensity in percent, as a single value or min-max range (0-100 "
            "respectively). If not given, --intensity is used."
        ),
        click_type=RangeParser(min=0, max=100),
    ),
]

ShockArg: TypeAlias = Annotated[bool, typer.Option(help="Send shocks.")]

VibrateArg: TypeAlias = Annotated[
    bool,
    typer.Option(help="Send vibrations in addition to shocks."),
]
