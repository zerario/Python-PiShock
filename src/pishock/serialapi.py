from __future__ import annotations

import enum
import json
from typing import Any, Iterator

import serial  # type: ignore[import-untyped]
import serial.tools.list_ports  # type: ignore[import-untyped]

USB_IDS = [
    (0x1A86, 0x7523),  # CH340, PiShock Next
    (0x1A86, 0x55D4),  # CH9102, PiShock Lite
]


class AutodetectError(Exception):
    """Raised if there are multiple or no PiShocks found via port autodetection."""


def _autodetect_port() -> str:
    """Auto-detect possible PiShock ports."""
    candidates: list[str] = []
    for info in serial.tools.list_ports.comports():
        if (info.vid, info.pid) in USB_IDS:
            candidates.append(info.device)

    if len(candidates) == 1:
        return candidates[0]
    elif not candidates:
        raise AutodetectError("No PiShock found via port autodetection.")
    else:
        raise AutodetectError(
            "Multiple (possibly) PiShocks found via port autodetection: "
            f"{', '.join(candidates)}. Use --port to select one."
        )


class SerialOperation(enum.Enum):
    SHOCK = "shock"
    VIBRATE = "vibrate"
    BEEP = "beep"
    END = "end"


class SerialAPI:
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

    def info(self) -> dict[str, Any]:
        """Get device info."""
        self._send_cmd("info")
        return self.wait_info()

    def wait_info(self) -> dict[str, Any]:
        """Wait for device info without sending an info command.

        FIXME: Timeout?
        """
        while True:
            line = self.dev.readline()
            if line.startswith(self.INFO_PREFIX):
                return self.decode_info(line)

    def decode_info(self, line: bytes) -> dict[str, Any]:
        """Decode a TERMINALINFO line."""
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

    def operate(
        self,
        shocker_id: int,
        operation: SerialOperation,
        duration: int | float,
        intensity: int | None = None,
    ) -> None:
        """Operate a shocker."""
        if intensity is not None and not 0 <= intensity <= 100:
            raise ValueError(
                f"intensity needs to be between 0 and 100, not {intensity}"
            )
        if not 0 <= duration <= 2**32:
            # FIXME do we have an upper bound on duration (other than uint32)?
            raise ValueError(
                f"duration needs to be between 0 and 2**32, not {duration}"
            )

        value = {
            "id": shocker_id,
            "op": operation.value,
            "duration": int(duration * 1000),
        }
        if intensity is not None:
            value["intensity"] = intensity

        self._send_cmd("operate", value)

    def monitor(self) -> Iterator[bytes]:
        """Monitor serial output."""
        while True:
            yield self.dev.readline()
