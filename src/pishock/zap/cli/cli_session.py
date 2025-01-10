"""
Session mode allows you to tailor automation of a longer session.
You can ramp up and down the intensity or use built-in randomizers
to choose between ranges of durations, intensity and how the shockers
interact over a given timeframe using JSON
"""
import contextlib
from typing import Iterator, List
import time
import rich
from pishock.zap import httpapi, core
from pishock.zap.cli import cli_utils as utils

class Session():
    """Session state handler"""
    def __init__(
            self,
            shockers: List[core.Shocker],
            data: List):
        self.data = data
        self.shockers = shockers
        self.declared_shockers = None
        self.init_delay = 0
        self.max_runtime = None
        self.count_in_mode = None
        self.start_time = time.monotonic()

    def _log(self, message: str) -> None:
        rich.print(message)

    def _get_event_params(self, seconds):
        pointer = 0
        items = self.data.get("events")
        length = len(items)
        prev_time = 0
        prev_val = None

        for v in items:
            cur_time = int(v["time"])

            if prev_time < seconds < time:
                if pointer == 0:
                    return v
                else:
                    return prev_val

            if seconds > cur_time and pointer + 1 < length:
                prev_time = cur_time
                prev_val = v
                pointer = pointer + 1
                continue

            return v

        return None

    @contextlib.contextmanager
    def _handle_errors(self) -> Iterator[None]:
        try:
            yield
        except (httpapi.APIError, ValueError) as e:
            utils.print_exception(e)

    def _shock(self, shocker: core.Shocker, duration: int, intensity: int) -> None:
        """Shock the user"""
        self._log(
            f":zap: [yellow]Shocking[/] [green]{shocker}[/] for [green]{duration}s[/] "
            f"at [green]{intensity}%[/]."
        )
        with self._handle_errors():
            shocker.shock(duration=duration, intensity=intensity)

    def _vibrate(self, shocker: core.Shocker, duration: int, intensity: int) -> None:
        """Vibrate the shocker"""
        self._log(
            f":vibration_mode: [cyan]Vibrating[/] [green]{shocker}[/] for "
            f"[green]{duration}s[/] at [green]{intensity}%[/]."
        )
        with self._handle_errors():
            shocker.vibrate(duration=duration, intensity=intensity)

    def _beep(self, shocker: core.Shocker, duration: int) -> None:
        """Emit a loud beep"""
        self._log(
            f":bell: [cyan]Beeping[/] [green]{shocker}[/] for "
            f"[green]{duration}s[/]"
        )
        with self._handle_errors():
            shocker.beep(duration=duration)


    def _execute_count_in(self) -> None:
        """Alert user that the session is about to start using beep or haptics"""
        if self.count_in_mode == "vibrate":
            for _ in range(3):
                self._vibrate(self.shockers[0], 1, 100)
                time.sleep(1)
        else:
            for _ in range(3):
                self._beep(self.shockers[0], 1)
                time.sleep(1)

    def _parse_duration_range(self, val: str) -> utils.Range:
        """syntax for parsing json durations"""
        return utils.RangeParser(min=0, converter=utils.parse_duration).convert(val, ctx=None, param=None)

    def run(self):
        """entry point for the session command"""
        self.declared_shockers = self.data.get("shocker_names")
        if not self.declared_shockers or len(self.declared_shockers) == 0:
            raise ValueError("the JSON field: root.shockers can not be blank or empty")

        self.count_in_mode = self.data.get("count_in_mode")
        if self.count_in_mode is not None:
            self._log(f":clock1: [blue]Count in Mode[/] is set to [green]{self.count_in_mode}[/].")

        if self.data.get("init_delay"):
            self.init_delay = self._parse_duration_range(self.data.get("init_delay", 0)).pick()
            self._log(f":zzz: [blue]Initial delay[/] of [green]{self.init_delay}[/] seconds.")
            #time.sleep(self.init_delay)

        if self.count_in_mode is not None:
            self._execute_count_in()

        if self.data.get("max_runtime"):
            self.max_runtime = self._parse_duration_range(self.data.get("max_runtime", 0)).pick()
            self._log(f":clock1: [blue]Max runtime[/] is [green]{self.max_runtime}[/] seconds.")

        while self.max_runtime is None or (time.monotonic() - self.start_time) < self.max_runtime:
            self._tick()

    def _tick(self) -> None:
        pass
