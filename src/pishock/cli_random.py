import re
import time
import dataclasses
from typing import Optional, Tuple, List, TYPE_CHECKING
from typing_extensions import Annotated, TypeAlias

import rich
import typer

from pishock import zap


class RangeParser:
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
            raise typer.BadParameter(f"Value must be an integer or float: {s}")

        if self.max is None and n < self.min:
            raise typer.BadParameter(f"Value must be at least {self.min}: {n}")
        if self.max is not None and not (self.min <= n <= self.max):
            raise typer.BadParameter(
                f"Value must be between {self.min} and {self.max}: {n}"
            )

        return n

    def __call__(self, value: str) -> Tuple[float, float]:
        if "-" not in value:
            n = self._parse_single(value)
            return n, n

        if value.count("-") > 1:
            raise typer.BadParameter("Range must be in the form min-max.")

        a = self._parse_single(a_str)
        b = self._parse_single(b_str)

        if b > a:
            raise typer.BadParameter("Min must be less than max.")
        return a, b


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
    return int((seconds + minutes * 60 + hours * 3600))


@dataclasses.dataclass
class SpamSettings:

    possibility: int
    operations: Tuple[int, int]
    pause: Tuple[int, int]
    duration: Tuple[float, float]
    intensity: Optional[Tuple[int, int]]


class RandomShocker:
    def __init__(
        self,
        api: zap.API,
        share_codes: List[str],
        duration: Tuple[float, float],
        intensity: Tuple[int, int],
        pause: Tuple[int, int],
        spam_settings: SpamSettings,
        max_runtime: Optional[int],
        vibrate_duration: Optional[Tuple[float, float]],
        vibrate_intensity: Optional[Tuple[int, int]],
        shock: bool,
        vibrate: bool,
    ) -> None:
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

    def _spam(self) -> None:
        assert zap.Operation.SHOCK in self.operations
        self._log("Spamming.")
        for _ in range(random.randint(*self.spam_settings.operations)):
            duration = random.randint(*self.spam_settings.duration)
            intensity_arg = self.spam_settings.intensity or self.intensity
            intensity = random.randint(*intensity_arg)

            rich.print(":zap:", end="", flush=True)
            shocker.shock(duration, intensity)
            time.sleep(duration + 0.3)

            pause = random.randint(*self.spam_settings.pause)
            time.sleep(pause)

    def _log(self, message: str) -> None:
        print(message)  # TODO

    def _shock(self, shocker: zap.Shocker) -> None:
        duration = random.randint(*self.duration)
        intensity = random.randint(*self.intensity)
        self._log(f"Shocking for {duration}s at {intensity}%.")
        shocker.shock(duration, intensity)

    def _vibrate(self, shocker: zap.Shocker) -> None:
        duration_arg = self.vibrate_duration or self.duration
        intensity_arg = self.vibrate_intensity or self.intensity
        duration = random.randint(*duration_arg)
        intensity = random.randint(*intensity_arg)
        self._log(f"Vibrating for {duration}s at {intensity}%.")
        shocker.vibrate(duration, intensity)

    def run(self) -> None:
        while (
            self.max_runtime is None
            or (time.monotonic() - self.start_time) < self.max_runtime
        ):
            self._tick()
            pause = random.randint(*self.pause)
            self._log(f"Sleeping for {pause} seconds.")
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
        else:
            raise ValueError(f"Invalid operation: {operation}")  # pragma: no cover


DurationArg: TypeAlias = Annotated[
    Tuple[float, float],
    typer.Option(
        "-d",
        "--duration",
        help=(
            "Duration in seconds, as a single value or a min-max range (0-15 "
            "respectively)."
        ),
        parser=RangeParser(min=0, max=15, float_ok=True),
    ),
]

IntensityArg: TypeAlias = Annotated[
    Tuple[int, int],
    typer.Option(
        "-i",
        "--intensity",
        help=(
            "Intensity in percent, as a single value or min-max range (0-100 "
            "respectively)."
        ),
        parser=RangeParser(min=0, max=100, float_ok=False),
    ),
]

PauseArg: TypeAlias = Annotated[
    Tuple[int, int],
    typer.Option(
        "-p",
        "--pause",
        help="Delay between operations in seconds, as a single value or min-max range.",
        parser=RangeParser(min=0, float_ok=False),
    ),
],

SpamPossibilityArg: TypeAlias = Annotated[
    int,
    typer.Option(
        help="Possibility of spamming in percent (0-100).",
        min=0,
        max=100,
    ),
]

SpamOperationsArg: TypeAlias = Annotated[
    Tuple[int, int],
    typer.Option(
        help="Number of operations to spam, as a single value or min-max range.",
        parser=RangeParser(min=1, float_ok=False),
    ),
]

SpamPauseArg: TypeAlias = Annotated[
    Tuple[int, int],
    typer.Option(
        help="Delay between spam operations in seconds, as a single value or min-max range.",
        parser=RangeParser(min=0, float_ok=False),
    ),
]

SpamDurationArg: TypeAlias = Annotated[
    Tuple[float, float],
    typer.Option(
        help="Duration of spam operations in seconds, as a single value or min-max range.",
        parser=RangeParser(min=0, max=15, float_ok=True),
    ),
]

SpamIntensityArg: TypeAlias = Annotated[
    Optional[Tuple[int, int]],
    typer.Option(
        help=(
            "Intensity of spam operations in percent, as a single value or min-max "
            "range. If not given, normal intensity is used."
        ),
        parser=RangeParser(min=0, max=100, float_ok=False),
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
    Optional[Tuple[float, float]],
    typer.Option(
        help=(
            "Duration for vibration in seconds, as a single value or a min-max "
            "range (0-15 respectively). If not given, --duration is used."
        ),
        parser=RangeParser(min=0, max=15, float_ok=True),
    ),
]

VibrateIntensityArg: TypeAlias = Annotated[
    Optional[Tuple[int, int]],
    typer.Option(
        help=(
            "Intensity in percent, as a single value or min-max range (0-100 "
            "respectively). If not given, --intensity is used."
        ),
        parser=RangeParser(min=0, max=100, float_ok=False),
    ),
]

ShockArg: TypeAlias = Annotated[bool, typer.Option("-s", "--shock", help="Send shocks.")]

VibrateArg: TypeAlias = Annotated[
    bool,
    typer.Option("-v", "--vibrate", help="Send vibrations in addition to shocks."),
]
