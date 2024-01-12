from __future__ import annotations

import sys
import enum
import json
from typing import Any, Iterator

import serial  # type: ignore[import-untyped]
import serial.tools.list_ports  # type: ignore[import-untyped]
import serial.tools.list_ports_common  # type: ignore[import-untyped]

from pishock.zap import core


USB_IDS = [
    (0x1A86, 0x7523),  # CH340, PiShock Next
    (0x1A86, 0x55D4),  # CH9102, PiShock Lite
]

INFO_TIMEOUT = 20


class DeviceType(enum.Enum):
    NEXT = 3
    LITE = 4


class SerialAutodetectError(Exception):
    """Raised if there are multiple or no PiShocks found via port autodetection."""


class ShockerNotFoundError(Exception):
    """Raised if a shocker ID is not found."""


def is_maybe_pishock(info: serial.tools.list_ports_common.ListPortInfo) -> bool:
    """Check if the given port might be a PiShock."""
    return (info.vid, info.pid) in USB_IDS


def _autodetect_port() -> str:
    """Auto-detect possible PiShock ports."""
    candidates: list[str] = []
    for info in serial.tools.list_ports.comports():
        if is_maybe_pishock(info):
            candidates.append(info.device)

    if len(candidates) == 1:
        return candidates[0]
    elif not candidates:
        raise SerialAutodetectError("No PiShock found via port autodetection.")
    else:
        raise SerialAutodetectError(
            "Multiple (possibly) PiShocks found via port autodetection: "
            f"{', '.join(candidates)}."
        )


class SerialOperation(enum.Enum):
    """The operation to perform for :meth:`SerialAPI.operate`.

    Attributes:
        SHOCK: Send a shock to the shocker.
        VIBRATE: Send a vibration to the shocker
        BEEP: Send a beep to the shocker.
        END: End the current operation.
    """

    SHOCK = "shock"
    VIBRATE = "vibrate"
    BEEP = "beep"
    END = "end"


class SerialAPI:
    """Low-level access to PiShock serial functionality.

    Arguments:
        port: Serial port to use, e.g. ``COM2`` or ``/dev/ttyUSB0``.
          If ``None``, auto-detection is attempted.

    Raises:
        SerialAutodetectError: No ``port`` was given, and either no PiShock was found, or
          multiple PiShocks were found.
    """

    INFO_PREFIX = b"TERMINALINFO: "

    def __init__(self, port: str | None) -> None:
        if port is None:
            port = _autodetect_port()
        self.dev = serial.Serial(port, 115200, timeout=1)

    def _build_cmd(self, cmd: str, value: Any = None) -> bytes:
        data = {"cmd": cmd}
        if value:
            data["value"] = value
        doc = json.dumps(data) + "\n"
        return doc.encode("utf-8")  # FIXME encoding?

    def _send_cmd(self, cmd: str, value: Any = None) -> None:
        """Send the given command/value over the serial port."""
        self.dev.write(self._build_cmd(cmd, value))

    def info(
        self, *, timeout: int | None = INFO_TIMEOUT, debug: bool = False
    ) -> dict[str, Any]:
        """Get device info.

        The exact contents of the returned dict might depend on the PiShock
        firmware version. At the time of writing, it looks like this (some data
        redacted):

        .. code-block:: python

            {
                'version': '3.1.1.231119.1556',
                'type': 4,  # 3 = Next, 4 = Lite
                'connected': False,
                'clientId': 621,
                'wifi': 'redacted-wifi-ssid',
                'server': 'eu1.pishock.com',
                'macAddress': '0C:B8:15:AB:CD:EF',
                'shockers': [
                    {'id': 420, 'type': 1, 'paused': False},  # 0 = Petrainer, 1 = SmallOne
                ],
                'networks': [
                    {'ssid': 'redacted-wifi-ssid', 'password': 'hunter2'},
                    {'ssid': 'PiShock', 'password': 'Zappy454'}
                ],
                'otk': 'e71d7b27-dc38-4774-bafc-c427757f0134',
                'claimed': True,
                'isDev': False,
                'publisher': False,
                'polled': True,
                'subscriber': True,
                'publicIp': '203.0.113.69',
                'internet': True,
                'ownerId': 6969
            }

        Arguments:
            timeout: How many seconds or serial lines to wait for the info response.
            debug: Print the raw serial output to stdout while waiting.

        Raises:
            TimeoutError: No info was received within the given timeout.
        """
        self._send_cmd("info")
        return self.wait_info(timeout=timeout, debug=debug)

    def wait_info(
        self, timeout: int | None = INFO_TIMEOUT, debug: bool = False
    ) -> dict[str, Any]:
        """Wait for device info without sending an info command.

        This will block until the next ``TERMINALINFO:`` line is received. You should
        normally call :meth:`info` instead. This is useful after sending a command
        that is expected to return info on its own, e.g. :meth:`add_network`.

        Arguments:
            timeout: How many seconds or serial lines to wait for the info response.
            debug: Print the raw serial output to stdout while waiting.

        Raises:
            TimeoutError: No info was received within the given timeout.
        """
        count = 0
        while timeout is None or count < timeout:
            line = self.dev.readline()
            if line.startswith(self.INFO_PREFIX):
                return self.decode_info(line)

            if debug:
                sys.stdout.buffer.write(line)

            count += 1

        raise TimeoutError(
            "No info received within timeout. Make sure the given device is indeed a PiShock."
        )

    def decode_info(self, line: bytes) -> dict[str, Any]:
        """Decode a ``TERMINALINFO:`` line.

        Normally, you should not need to call this manually, use :meth:`wait_info` or
        :meth:`info` instead.
        """
        data = json.loads(line[len(self.INFO_PREFIX) :])
        assert isinstance(data, dict)
        return data

    def add_network(self, ssid: str, password: str) -> None:
        """Add a new network to the PiShock config and reboot."""
        self._send_cmd("addnetwork", {"ssid": ssid, "password": password})

    def remove_network(self, ssid: str) -> None:
        """Remove a network from the PiShock config."""
        self._send_cmd("removenetwork", ssid)

    def try_connect(self, ssid: str, password: str) -> None:
        """Temporarily try connecting to the given network."""
        self._send_cmd("connect", {"ssid": ssid, "password": password})

    def restart(self) -> None:
        """Restart the PiShock."""
        self._send_cmd("restart")

    def shocker(self, shocker_id: int) -> SerialShocker:
        """Get a :class:`SerialShocker` instance for the given shocker code.

        This is the main entry point for operating a shocker via serial.

        Arguments:
            shocker_id: The shocker ID, as displayed under the
              cogwheels on the `PiShock website <https://pishock.com/#/control>`_, or
              available via :meth:`pishock.zap.httpapi.HTTPShocker.info()` or
              :meth:`SerialAPI.info()`.
        """
        return SerialShocker(api=self, shocker_id=shocker_id)

    def operate(
        self,
        shocker_id: int,
        operation: SerialOperation,
        duration: int | float,
        intensity: int | None = None,
    ) -> None:
        """Operate a shocker.

        Note that the firmware will silently ignore any commands for a
        non-existing shocker ID.

        You should not need to use this directly, use :meth:`shocker` to get
        access to the higher-level :class:`SerialShocker` instead.
        """
        if intensity is not None and not 0 <= intensity <= 100:
            raise ValueError(
                f"intensity needs to be between 0 and 100, not {intensity}"
            )

        duration_ms = int(duration * 1000)
        if not 0 <= duration_ms < 2**32:
            # FIXME do we have an upper bound on duration (other than uint32 ms)?
            raise ValueError(
                f"duration needs to be between 0 and 2**32 / 1000, not {duration}"
            )

        value = {
            "id": shocker_id,
            "op": operation.value,
            "duration": duration_ms,
        }
        if intensity is not None:
            value["intensity"] = intensity

        self._send_cmd("operate", value)

    def monitor(self) -> Iterator[bytes]:
        """Monitor serial output."""
        while True:
            yield self.dev.readline()


class SerialShocker(core.Shocker):
    """Represents a single shocker accessed via serial port.

    Normally, there should be no need to instanciate this manually, use
    :meth:`SerialAPI.shocker()` instead.

    Arguments:
        api: The :class:`SerialAPI` instance to use.
        shocker_id: The ID of the shocker to operate.

    Raises:
        ShockerNotFoundError: The given ``shocker_id`` was not found.
    """

    IS_SERIAL = True

    def __init__(self, api: SerialAPI, shocker_id: int) -> None:
        self.shocker_id = shocker_id
        self.api = api
        self.info()  # make sure the shocker exists

    def __str__(self) -> str:
        return f"Serial shocker {self.shocker_id} ({self.api.dev.port})"

    def shock(self, *, duration: int | float, intensity: int) -> None:
        """Send a shock with the given duration (seconds, >0) and intensity (0-100).

        Durations can also be floats for fractional seconds.

        Raises:
            ValueError: ``duration`` or ``intensity`` are out of range.
        """
        self.api.operate(
            shocker_id=self.shocker_id,
            operation=SerialOperation.SHOCK,
            duration=duration,
            intensity=intensity,
        )

    def vibrate(self, *, duration: int | float, intensity: int) -> None:
        """Send a vibration with the given duration (seconds, >0) and intensity (0-100).

        Durations can also be floats for fractional seconds.

        Raises:
            ValueError: ``duration`` or ``intensity`` are out of range.
        """
        self.api.operate(
            shocker_id=self.shocker_id,
            operation=SerialOperation.VIBRATE,
            duration=duration,
            intensity=intensity,
        )

    def beep(self, duration: int | float) -> None:
        """Send a beep with the given duration (seconds, >0).

        Durations can also be floats for fractional seconds.

        Raises:
            ValueError: ``duration`` is out of range.
        """
        self.api.operate(
            shocker_id=self.shocker_id,
            operation=SerialOperation.BEEP,
            duration=duration,
        )

    def end(self) -> None:
        """End the currently running operation."""
        self.api.operate(
            shocker_id=self.shocker_id,
            operation=SerialOperation.END,
            duration=0,
        )

    def info(self) -> core.BasicShockerInfo:
        """Get information about the shocker."""
        data = self.api.info()
        shockers = {s["id"]: s for s in data["shockers"]}
        if self.shocker_id not in shockers:
            available = ", ".join(str(s) for s in shockers)
            raise ShockerNotFoundError(
                f"Shocker {self.shocker_id} not found, available: {available}"
            )

        return core.BasicShockerInfo(
            name=str(self),
            client_id=data["clientId"],
            shocker_id=self.shocker_id,
            is_paused=shockers[self.shocker_id]["paused"],
        )
