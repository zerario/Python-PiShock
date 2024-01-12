from __future__ import annotations

import pytest
import rich.console
from serial.tools.list_ports_common import ListPortInfo  # type: ignore[import-untyped]

from pytest_golden.plugin import GoldenTestFixture  # type: ignore[import-untyped]
from pishock.zap.cli import cli_serial


pytestmark = pytest.mark.skipif(
    rich.console.WINDOWS, reason="Output looks different on Windows"
)


@pytest.mark.golden_test("golden/misc.yml")
def test_print_serial_ports(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    golden: GoldenTestFixture,
) -> None:
    info = ListPortInfo("/dev/ttyUSBFAKE")
    info.description = "Fake device"
    info.vid = 0x1234
    info.pid = 0x5678
    info.serial_number = "12345678"
    info.manufacturer = "Fake Manufacturer"
    info.product = "Fake Product"
    monkeypatch.setattr("serial.tools.list_ports.comports", lambda: [info])

    cli_serial.print_serial_ports()
    out, _err = capsys.readouterr()
    assert out == golden.out["output_list_serials"]
