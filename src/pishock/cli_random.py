import contextlib
import dataclasses
import random
import re
import time
from typing import Iterator, List, Optional, Union

import click
import rich
import typer
from typing_extensions import Annotated, TypeAlias

from pishock import cli_utils as utils, zap


class RangeParser(click.ParamType):
    name = "Range"

    def __init__(
        self, min: int, max: Optional[int] = None, float_ok: bool = False
    ) -> None:
        self.min = min
        self.max = max
        self.float_ok = float_ok

    def _parse_single(self, s: str) -> float:
        try:
            if self.float_ok and "." in s:
                n = float(s)
            else:
                n = int(s)
        except ValueError:
            self.fail(f"Value must be an integer or float: {s}")

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

        if b < a:
            self.fail("Min must be less than max.")
        return utils.Range(a, b)


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
        raise typer.BadParameter(
            f"Invalid duration: {duration} - " "expected XhYmZs or a number of seconds"
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
        api: zap.API,
        share_codes: List[str],
        duration: utils.Range,
        intensity: utils.Range,
        pause: utils.Range,
        spam_settings: SpamSettings,
        max_runtime: Optional[int],
        vibrate_duration: Optional[utils.Range],
        vibrate_intensity: Optional[utils.Range],
        shock: bool,
        vibrate: bool,
    ) -> None:
        self.api = api
        self.share_codes = share_codes
        self.duration = duration
        self.intensity = intensity
        self.pause = pause
        self.spam_settings = spam_settings
        self.max_runtime = max_runtime
        self.vibrate_duration = vibrate_duration
        self.vibrate_intensity = vibrate_intensity

        self.start_time = time.monotonic()
        self.operations = []
        if shock:
            self.operations.append(zap.Operation.SHOCK)
        if vibrate:
            self.operations.append(zap.Operation.VIBRATE)

    def _log(self, message: str) -> None:
        rich.print(message)  # TODO

    @contextlib.contextmanager
    def _handle_errors(self) -> Iterator[None]:
        try:
            yield
        except (zap.APIError, ValueError) as e:
            utils.print_error(e)

    def _spam(self) -> None:
        assert zap.Operation.SHOCK in self.operations
        self._log("[red bold]Spamming.[/]")
        for _ in range(self.spam_settings.operations.pick()):
            shocker = self.api.shocker(random.choice(self.share_codes))
            duration = self.spam_settings.duration.pick()
            intensity = (self.spam_settings.intensity or self.intensity).pick()

            try:
                shocker.shock(duration=duration, intensity=intensity)
            except (zap.APIError, ValueError):
                rich.print(":x:", end="", flush=True)
            else:
                rich.print(":zap:", end="", flush=True)
            time.sleep(duration + 0.3)

            pause = self.spam_settings.pause.pick()
            time.sleep(pause)

    def _shock(self, shocker: zap.Shocker) -> None:
        duration = self.duration.pick()
        intensity = self.intensity.pick()
        self._log(
            f":zap: [yellow]Shocking[/] [green]{shocker}[/] for [green]{duration}s[/] "
            f"at [green]{intensity}%[/]."
        )
        with self._handle_errors():
            shocker.shock(duration=duration, intensity=intensity)

    def _vibrate(self, shocker: zap.Shocker) -> None:
        duration = (self.vibrate_duration or self.duration).pick()
        intensity = (self.vibrate_intensity or self.intensity).pick()
        self._log(
            f":vibration_mode: [cyan]Vibrating[/] [green]{shocker}[/] for "
            f"[green]{duration}s[/] at [green]{intensity}%[/]."
        )
        with self._handle_errors():
            shocker.vibrate(duration=duration, intensity=intensity)

    def run(self) -> None:
        while (
            self.max_runtime is None
            or (time.monotonic() - self.start_time) < self.max_runtime
        ):
            self._tick()
            pause = self.pause.pick()
            self._log(f":zzz: [blue]Sleeping[/] for [green]{pause}[/] seconds.")
            time.sleep(pause)

    def _tick(self) -> None:
        if random.randint(0, 100) <= self.spam_settings.possibility:
            self._spam()
            return

        operation = random.choice(self.operations)
        shocker = self.api.shocker(random.choice(self.share_codes))

        if operation == zap.Operation.SHOCK:
            self._shock(shocker)
        elif operation == zap.Operation.VIBRATE:
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
        click_type=RangeParser(min=0, max=15, float_ok=True),
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
        click_type=RangeParser(min=0, max=100, float_ok=False),
    ),
]

PauseArg: TypeAlias = Annotated[
    utils.Range,
    typer.Option(
        "-p",
        "--pause",
        help="Delay between operations in seconds, as a single value or min-max range.",
        click_type=RangeParser(min=0, float_ok=False),
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
        click_type=RangeParser(min=1, float_ok=False),
    ),
]

SpamPauseArg: TypeAlias = Annotated[
    utils.Range,
    typer.Option(
        help=(
            "Delay between spam operations in seconds, as a single value or min-max "
            "range."
        ),
        click_type=RangeParser(min=0, float_ok=False),
    ),
]

SpamDurationArg: TypeAlias = Annotated[
    utils.Range,
    typer.Option(
        help=(
            "Duration of spam operations in seconds, as a single value or min-max "
            "range."
        ),
        click_type=RangeParser(min=0, max=15, float_ok=True),
    ),
]

SpamIntensityArg: TypeAlias = Annotated[
    Optional[utils.Range],
    typer.Option(
        help=(
            "Intensity of spam operations in percent, as a single value or min-max "
            "range. If not given, normal intensity is used."
        ),
        click_type=RangeParser(min=0, max=100, float_ok=False),
    ),
]

MaxRuntimeArg: TypeAlias = Annotated[
    Optional[int],
    typer.Option(
        help=(
            "Maximum runtime in seconds or a string like 1h2m3s (with h/m being "
            "optional)."
        ),
        parser=parse_duration,
    ),
]

VibrateDurationArg: TypeAlias = Annotated[
    Optional[utils.Range],
    typer.Option(
        help=(
            "Duration for vibration in seconds, as a single value or a min-max "
            "range (0-15 respectively). If not given, --duration is used."
        ),
        click_type=RangeParser(min=0, max=15, float_ok=True),
    ),
]

VibrateIntensityArg: TypeAlias = Annotated[
    Optional[utils.Range],
    typer.Option(
        help=(
            "Intensity in percent, as a single value or min-max range (0-100 "
            "respectively). If not given, --intensity is used."
        ),
        click_type=RangeParser(min=0, max=100, float_ok=False),
    ),
]

ShockArg: TypeAlias = Annotated[
    bool, typer.Option("-s", "--shock", help="Send shocks.")
]

VibrateArg: TypeAlias = Annotated[
    bool,
    typer.Option("-v", "--vibrate", help="Send vibrations in addition to shocks."),
]
