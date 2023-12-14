from __future__ import annotations

import enum
import tempfile
from typing import Iterator

import pishock
from pishock.zap import httpapi, serialapi

import requests

try:
    import esptool  # type: ignore[import-untyped]
except ModuleNotFoundError:
    esptool = None


class FirmwareType(enum.Enum):
    V1_LITE = 0
    VAULT = 1  # untested!
    V1_NEXT = 2
    V3_NEXT = 3
    V3_LITE = 4


class FirmwareUpdateError(Exception):
    """Raised if a firmware update fails."""


def is_compatible(
    firmware_type: FirmwareType, device_type: serialapi.DeviceType
) -> bool:
    """Check if the firmware should be compatible with this device."""
    if device_type == serialapi.DeviceType.LITE:
        return firmware_type in [FirmwareType.V1_LITE, FirmwareType.V3_LITE]
    elif device_type == serialapi.DeviceType.NEXT:
        return firmware_type in [FirmwareType.V1_NEXT, FirmwareType.V3_NEXT]
    else:
        raise ValueError(f"Unknown device type: {device_type}")


def download_firmware(firmware_type: FirmwareType) -> tuple[int, Iterator[bytes]]:
    """Get the latest firmware for the given device.

    Returns:
        A tuple of the firmware size, and an iterator over the firmware data.

    Raises:
        requests.HTTPError: If the request fails.
    """
    headers = {"User-Agent": f"{httpapi.NAME}/{pishock.__version__}"}
    response = requests.get(
        "https://do.pishock.com/api/GetLatestFirmware",
        params={"type": firmware_type.value},
        headers=headers,
        stream=True,
    )
    response.raise_for_status()
    size = int(response.headers["Content-Length"])
    return size, response.iter_content(chunk_size=4096)


def truncate(data: bytes) -> bytes:
    """Truncate the firmware to the size supported by the device.

    Raises:
        FirmwareUpdateError: If the firmware is not all 0xff after the truncation point.
    """
    size = 0x3FF000
    truncated = data[:size]
    rest = data[size:]
    if set(rest) != {0xFF}:
        raise FirmwareUpdateError(f"Truncated part is not all 0xff:\n{rest.hex(' ')}")
    return truncated


def flash(port: str, data: bytes) -> None:
    """Flash the firmware to the device.

    Raises:
        FirmwareUpdateError: If esptool is not available, or esptool exited.
        esptool.FatalError: Raised by esptool if flashing fails.
        serial.SerialException: Raised by esptool if flashing fails.
        StopIteration: Raised by esptool if flashing fails.
        OSError: If writing temporary file failed.
    """
    if esptool is None:
        raise FirmwareUpdateError(
            "Optional esptool dependency is required for firmware updates"
        )

    with tempfile.NamedTemporaryFile(prefix="pishock-firmware-", suffix=".bin") as f:
        f.write(data)
        f.flush()
        try:
            esptool.main([
                "--port",
                port,
                "--chip",
                "esp32",
                "--baud",
                "115200",
                "write_flash",
                "--flash_freq",
                "40m",
                "-z",
                "0x1000",
                f.name,
            ])
        except SystemExit as e:
            raise FirmwareUpdateError(f"esptool exited: {e}") from e
