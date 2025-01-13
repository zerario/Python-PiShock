"""
Session mode allows you to tailor automation of a longer session.
You can ramp up and down the intensity or use built-in randomizers
to choose between ranges of durations, intensity and how the shockers
interact over a given timeframe using JSON
"""
import contextlib
from enum import Enum
from functools import reduce
import math
import random
import time
from typing import Iterator, List, Optional
from typing_extensions import TypeAlias
import rich
from pishock.zap import httpapi, core
from pishock.zap.cli import cli_utils as utils

JSON: TypeAlias = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None
allowed_sync_modes = [
    "random-shocker",
    "round-robin",
    "sync",
    "dealers-choice"
]
class ProgamModes(Enum):
    SHOCK = 1
    VIBRATE = 2
    BEEP = 3
    SPAM = 4

DURATION_BETWEEN_EVENTS = 0.3
DEFAULT_JSON_BREAK_DURATION = "1-10"
DEFAULT_VIBRATION_DURATION_RANGE = "1-5"
DEFAULT_VIBRATION_INTENSITY_RANGE = "0-100"
DEFAULT_SYNC_MODE = "random-shocker"

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
        self.sync_mode = "random-shocker"
        self.default_vibration_intensity = self._parse_duration(DEFAULT_VIBRATION_INTENSITY_RANGE)
        self.default_vibration_duration = self._parse_duration(DEFAULT_VIBRATION_DURATION_RANGE)


    def _log(self, message: str) -> None:
        rich.print(message)

    def _get_event_params(self, seconds):
        """Get an event for the specific timeframe"""
        pointer = 0
        items = self.data.get("events")
        length = len(items)
        prev_time = 0
        prev_val = None

        for v in items:
            cur_time = utils.parse_duration(v.get("time"))

            if prev_time < seconds < cur_time:
                if pointer == 0:
                    return v

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
        """Handle HTTP errors and bad input to the shockers"""
        try:
            yield
        except (httpapi.APIError, ValueError) as e:
            utils.print_exception(e)

    def _get_shockers_for_event(self) -> List[core.Shocker]:
        if len(self.shockers) == 1:
            return [self.shockers[0]]

        if self.sync_mode == "dealers-choice":
            self.sync_mode = random.choice(allowed_sync_modes[:3])

        match self.sync_mode:
            case "sync":
                return self.shockers
            case "round-robin":
                self.shockers = self.shockers[1:] + self.shockers[:1]
                return [self.shockers[0]]
            case "random-shocker":
                return [random.choice(self.shockers)]

    def _shock(self, duration: int, intensity: int) -> None:
        """Shock the user"""
        shockers = self._get_shockers_for_event()

        for shocker in shockers:
            self._log(
                f":zap: [yellow]Shocking[/] [green]{shocker.info().name}[/] for [green]{duration}s[/] "
                f"at [green]{intensity}%[/]"
            )
            #with self._handle_errors():
            #    shocker.shock(duration=duration, intensity=intensity)

    def _vibrate(self, duration: int, intensity: int) -> None:
        """Vibrate the user"""
        shockers = self._get_shockers_for_event()

        for shocker in shockers:
            self._log(
                f":vibration_mode: [cyan]Vibrating[/] [green]{shocker.info().name}[/] for "
                f"[green]{duration}s[/] at [green]{intensity}%[/]"
            )
            #with self._handle_errors():
            #    shocker.vibrate(duration=duration, intensity=intensity)

    def _beep(self, duration: int) -> None:
        """Emit a loud beep"""
        shockers = self._get_shockers_for_event()

        for shocker in shockers:
            self._log(
                f":bell: [cyan]Beeping[/] [green]{shocker.info().name}[/] for "
                f"[green]{duration}s[/]"
            )
            #with self._handle_errors():
            #    shocker.beep(duration=duration)

    def spam(self, event: dict) -> None:
        """Send consecutive shocks to the user"""

    def _execute_count_in(self) -> None:
        """Alert user that the session is about to start using beep or haptics"""
        if self.count_in_mode == "vibrate":
            for _ in range(3):
                self._vibrate(1, 100)
                time.sleep(1)
        else:
            for _ in range(3):
                self._beep(1)
                time.sleep(1)

    def _parse_duration(self, val: str) -> utils.Range:
        """Parse json duration ranges to a Range"""
        return utils.RangeParser(min=0, converter=utils.parse_duration).convert(val, ctx=None, param=None)

    def _parse_intensity(self, val: str) -> utils.Range:
        """Parse json 0-100 ranges into a Range"""
        return utils.RangeParser(min=0, max=100).convert(val, ctx=None, param=None)

    def _parse_sync_mode(self, sync_mode:str) -> str:
        """Convert shocker sync modes from JSON to domain values"""
        if sync_mode:
            if sync_mode in allowed_sync_modes:
                return sync_mode

            raise ValueError(f"the JSON field: root.events.sync_mode: {sync_mode} is invalid")

        return DEFAULT_SYNC_MODE

    def _parse_shocker_info(self, cls: str, val: JSON) -> Optional[dict]:
        """Get shared shocker characteristics"""
        if not val:
            return None

        intensity = duration = None

        if cls != "beep":
            if val.get("intensity"):
                intensity = self._parse_intensity(val.get("intensity"))
            else:
                raise ValueError(f"the JSON field: root.events.{cls}.intensity is missing")

        if val.get("duration"):
            duration = self._parse_duration(val.get("duration"))
        else:
            raise ValueError(f"the JSON field: root.events.{cls}.duration is missing")

        return {
            "possibility": val.get("possibility"),
            "intensity": intensity,
            "duration": duration
        }

    def _parse_spam_info(self, cls: str, val: JSON) -> Optional[dict]:
        """Spam requires some extra details beyond intensity, duration and possibility"""
        if not val:
            return None

        operations = delay = None
        info = self._parse_shocker_info("spam", val)

        if val.get("operations"):
            operations = self._parse_intensity(val.get("operations"))
        else:
            raise ValueError(f"the JSON field: root.events.{cls}.operations is missing")

        if val.get("delay"):
            delay = float(val.get("delay"))
        else:
            raise ValueError(f"the JSON field: root.events.{cls}.delay is missing")

        info["operations"] = operations
        info["delay"] = delay

        return info

    def _parse_event(self, val: JSON) -> dict:
        """Create domain values from JSON"""
        return {
            "sync_mode": self._parse_sync_mode(val.get("sync_mode")),
            "break_duration": self._parse_duration(val.get("break_duration", DEFAULT_JSON_BREAK_DURATION)),
            "vibrate": self._parse_shocker_info("vibrate", val.get("vibrate")),
            "shock": self._parse_shocker_info("shock", val.get("shock")),
            "beep": self._parse_shocker_info("beep", val.get("beep")),
            "spam": self._parse_spam_info("spam", val.get("spam"))
        }

    def _get(self, dictionary:dict, keys:str, default=None) -> int:
        return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys.split("."), dictionary)

    def _get_int(self, dictionary:dict, keys:str) -> int:
        val = self._get(dictionary, keys)

        if val is None:
            return 0

        return val

    def _get_possibility_map(self, event: dict):
        """create a list of 100 operation possibilities based on the event data and then
        shuffle it to simulate a percent chance when chosen at random"""
        spam = self._get_int(event, "spam.possibility")
        shock = self._get_int(event, "shock.possibility")
        beep = self._get_int(event, "beep.possibility")
        vibrate = self._get_int(event, "vibrate.possibility")
        vibrate_possibility = self._get(event, "vibrate.possibility")

        if spam + shock + beep + vibrate > 100:
            raise ValueError(f"the JSON field: root.events.evt.possibility exceeds 100%: {event}")

        modes = [ProgamModes.SPAM]*spam\
            + [ProgamModes.SHOCK]*shock\
            + [ProgamModes.BEEP]*beep\
            + [ProgamModes.VIBRATE]*vibrate

        if vibrate_possibility is None:
            pad = modes + [ProgamModes.VIBRATE]*(100-len(modes))
        else:
            pad = modes + [None]*(100-len(modes))

        random.shuffle(pad)

        return pad

    def _tick(self) -> None:
        """event handler loop"""
        event = self._parse_event(self._get_event_params(time.monotonic() - self.start_time))
        event_choice = random.choice(self._get_possibility_map(event))
        break_duration = event["break_duration"]
        self.sync_mode = event["sync_mode"]

        match event_choice:
            case(ProgamModes.SHOCK):
                self._shock(event["shock"]["duration"].pick(), event["shock"]["intensity"].pick())
            case(ProgamModes.SPAM):
                print("spam")
            case(ProgamModes.VIBRATE):
                if event.get("vibrate") is not None:
                    self._vibrate(event["vibrate"]["duration"].pick(), event["vibrate"]["intensity"].pick())
                else:
                    self._vibrate(self.default_vibration_duration.pick(), self.default_vibration_intensity.pick())

            case(ProgamModes.BEEP):
                self._beep(event["beep"]["duration"].pick())

        #time.sleep(break_duration.pick() + DURATION_BETWEEN_EVENTS)
        time.sleep(0.1)

    def run(self):
        """entry point for the session command"""
        self._log(":arrow_forward: [white]Session started[/]")

        self.declared_shockers = self.data.get("shocker_names")
        if not self.declared_shockers or len(self.declared_shockers) == 0:
            raise ValueError("the JSON field: root.shockers can not be blank or empty")

        self.count_in_mode = self.data.get("count_in_mode")
        if self.count_in_mode is not None:
            self._log(f":green_square: [blue]Count in Mode[/] is set to [green]{self.count_in_mode}[/]")

        if self.data.get("init_delay"):
            self.init_delay = self._parse_duration(self.data.get("init_delay", 0)).pick()
            self._log(f":zzz: [blue]Initial delay[/] of [green]{self.init_delay}[/] seconds")
            #time.sleep(self.init_delay)

        if self.count_in_mode is not None:
            self._execute_count_in()

        if self.data.get("max_runtime"):
            self.max_runtime = self._parse_duration(self.data.get("max_runtime", 0)).pick()
            self._log(f":clock1: [blue]Max runtime[/] is [green]{self.max_runtime}[/] seconds")

        while self.max_runtime is None or (time.monotonic() - self.start_time) < self.max_runtime:
            self._tick()

        self._log(f":checkered_flag: [white]Session ended at[/] [green]{math.ceil(time.monotonic()-self.start_time)}[/] seconds (excluding initial delay)")

    def validate_events(self):
        """Check the events list can be parsed beginning to end and output the plan"""
        self._log(":heavy_check_mark: [blue]Validating events[/]")

        items = self.data.get("events")

        if not items:
            raise ValueError("The JSON field: root.events cannot be empty and must be an array")

        for val in items:
            event = self._parse_event(val)
            self._get_possibility_map(event)

        self._log(":heavy_check_mark: [blue]Event list is valid[/]")
