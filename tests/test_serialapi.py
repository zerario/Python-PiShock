from __future__ import annotations

import re
from typing import Any

import pytest
import serial  # type: ignore[import-untyped]
from serial.tools.list_ports_common import ListPortInfo  # type: ignore[import-untyped]

# for type annotations
from tests.conftest import FakeSerial, FakeCredentials, SerialPatcher
from pishock.zap import serialapi


@pytest.fixture
def fake_info_match_1() -> ListPortInfo:
    info = ListPortInfo("/dev/ttyUSBFAKE1")
    info.vid, info.pid = serialapi.USB_IDS[0]
    return info


@pytest.fixture
def fake_info_match_2() -> ListPortInfo:
    info = ListPortInfo("/dev/ttyUSBFAKE2")
    info.vid, info.pid = serialapi.USB_IDS[1]
    return info


@pytest.fixture
def fake_info_no_match() -> ListPortInfo:
    return ListPortInfo("/dev/ttyUSBFAKE3")


class TestIsMaybePiShock:
    def test_match_1(self, fake_info_match_1: ListPortInfo) -> None:
        assert serialapi.is_maybe_pishock(fake_info_match_1)

    def test_match_2(self, fake_info_match_2: ListPortInfo) -> None:
        assert serialapi.is_maybe_pishock(fake_info_match_2)

    def test_no_match(self, fake_info_no_match: ListPortInfo) -> None:
        assert not serialapi.is_maybe_pishock(fake_info_no_match)


class TestAutodetectPort:
    def test_one_match(
        self,
        fake_info_match_1: ListPortInfo,
        fake_info_no_match: ListPortInfo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            serial.tools.list_ports,
            "comports",
            lambda: [fake_info_match_1, fake_info_no_match],
        )
        assert serialapi._autodetect_port() == fake_info_match_1.device

    def test_two_matches(
        self,
        fake_info_match_1: ListPortInfo,
        fake_info_match_2: ListPortInfo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            serial.tools.list_ports,
            "comports",
            lambda: [fake_info_match_1, fake_info_match_2],
        )
        with pytest.raises(
            serialapi.SerialAutodetectError,
            match=re.escape(
                "Multiple (possibly) PiShocks found via port autodetection: /dev/ttyUSBFAKE1, /dev/ttyUSBFAKE2."
            ),
        ):
            serialapi._autodetect_port()

    def test_no_match(
        self,
        fake_info_no_match: ListPortInfo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            serial.tools.list_ports,
            "comports",
            lambda: [fake_info_no_match],
        )
        with pytest.raises(
            serialapi.SerialAutodetectError,
            match=re.escape("No PiShock found via port autodetection."),
        ):
            serialapi._autodetect_port()


def test_init_autodetect(
    fake_serial: FakeSerial,
    monkeypatch: pytest.MonkeyPatch,
    credentials: FakeCredentials,
) -> None:
    monkeypatch.setattr(serialapi, "_autodetect_port", lambda: credentials.SERIAL_PORT)
    monkeypatch.setattr(serial, "Serial", lambda port, baudrate, timeout: fake_serial)
    api = serialapi.SerialAPI(port=None)
    assert api.dev is fake_serial


@pytest.mark.parametrize(
    "cmd, value, expected",
    [
        ("info", None, b'{"cmd": "info"}\n'),
        (
            "addnetwork",
            {"ssid": "test", "password": "hunter2"},
            b'{"cmd": "addnetwork", "value": {"ssid": "test", "password": "hunter2"}}\n',
        ),
        ("removenetwork", "test", b'{"cmd": "removenetwork", "value": "test"}\n'),
    ],
)
def test_build_cmd(
    serial_api: serialapi.SerialAPI, cmd: str, value: Any, expected: bytes
) -> None:
    assert serial_api._build_cmd(cmd, value) == expected


def test_send_cmd(serial_api: serialapi.SerialAPI, fake_serial: FakeSerial) -> None:
    serial_api._send_cmd("restart")
    assert fake_serial.get_written() == b'{"cmd": "restart"}\n'


def test_info(
    serial_patcher: SerialPatcher,
    serial_api: serialapi.SerialAPI,
    credentials: FakeCredentials,
) -> None:
    serial_patcher.info()
    assert serial_api.info() == {
        "clientId": 1000,  # FIXME use credentials.CLIENT_ID?
        "shockers": [{"id": credentials.SHOCKER_ID, "paused": False}],
    }


@pytest.mark.parametrize("debug", [True, False])
def test_wait_info(
    serial_api: serialapi.SerialAPI,
    fake_serial: FakeSerial,
    debug: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_serial.next_read = [b"not terminalinfo", b"TERMINALINFO: {}"]
    info = serial_api.wait_info(debug=debug)
    assert info == {}

    out, _err = capsys.readouterr()
    assert out == ("not terminalinfo" if debug else "")


def test_wait_info_timeout(
    serial_api: serialapi.SerialAPI, fake_serial: FakeSerial
) -> None:
    fake_serial.next_read = [b"not terminalinfo", b"TERMINALINFO: {}"]
    with pytest.raises(
        TimeoutError,
        match=re.escape(
            "No info received within timeout. "
            "Make sure the given device is indeed a PiShock."
        ),
    ):
        serial_api.wait_info(timeout=1)


def test_unknown_shocker(
    serial_patcher: SerialPatcher,
    serial_api: serialapi.SerialAPI,
    credentials: FakeCredentials,
) -> None:
    serial_patcher.info()
    with pytest.raises(
        serialapi.ShockerNotFoundError,
        match=r"Shocker 1002 not found, available: 1001",
    ):
        serial_api.shocker(credentials.SHOCKER_ID + 1)


def test_add_network(serial_api: serialapi.SerialAPI, fake_serial: FakeSerial) -> None:
    serial_api.add_network("test", "hunter2")
    data = b'{"cmd": "addnetwork", "value": {"ssid": "test", "password": "hunter2"}}\n'
    assert fake_serial.get_written() == data


def test_remove_network(
    serial_api: serialapi.SerialAPI, fake_serial: FakeSerial
) -> None:
    serial_api.remove_network("test")
    assert fake_serial.get_written() == b'{"cmd": "removenetwork", "value": "test"}\n'


def test_try_connect(serial_api: serialapi.SerialAPI, fake_serial: FakeSerial) -> None:
    serial_api.try_connect("test", "hunter2")
    data = b'{"cmd": "connect", "value": {"ssid": "test", "password": "hunter2"}}\n'
    assert fake_serial.get_written() == data


def test_restart(serial_api: serialapi.SerialAPI, fake_serial: FakeSerial) -> None:
    serial_api.restart()
    assert fake_serial.get_written() == b'{"cmd": "restart"}\n'


def test_monitor(serial_api: serialapi.SerialAPI, fake_serial: FakeSerial) -> None:
    data = [b"Hello", b"World"]
    fake_serial.next_read = data
    gen = serial_api.monitor()
    # raises due to us patching in a list instead of using an actual blocking device
    with pytest.raises(IndexError, match="pop from empty list"):
        assert list(gen) == data


def test_shocker_end(
    serial_shocker: serialapi.SerialShocker,
    serial_patcher: SerialPatcher,
) -> None:
    serial_patcher.operate(
        operation=serialapi.SerialOperation.END, duration=0, intensity=None
    )
    serial_shocker.end()
