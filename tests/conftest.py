from __future__ import annotations

import http
import io
import json
import re
import pathlib
from typing import Any, Callable, Iterator, Dict, cast

import pytest
import rich
import serial  # type: ignore[import-untyped]
import platformdirs
import click.testing
import typer.testing
from responses import RequestsMock, matchers
from typing_extensions import TypeAlias

import pishock
from pishock.zap import httpapi, serialapi, core
from pishock.zap.cli import cli

_MatcherType: TypeAlias = Callable[..., Any]
ConfigDataType: TypeAlias = Dict[str, Dict[str, Any]]


@pytest.fixture(autouse=True)
def config_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> pathlib.Path:
    monkeypatch.setattr(
        platformdirs,
        "user_config_dir",
        lambda appname, appauthor: tmp_path,
    )
    return tmp_path / "config.json"


@pytest.fixture
def config_data(credentials: FakeCredentials) -> ConfigDataType:
    return {
        "api": {
            "username": credentials.USERNAME,
            "key": credentials.API_KEY,
        },
        "shockers": {},
    }


@pytest.fixture
def pishock_api(credentials: FakeCredentials) -> httpapi.PiShockAPI:
    return httpapi.PiShockAPI(
        username=credentials.USERNAME, api_key=credentials.API_KEY
    )


@pytest.fixture
def serial_api(
    fake_serial: FakeSerial,
    monkeypatch: pytest.MonkeyPatch,
    credentials: FakeCredentials,
) -> serialapi.SerialAPI:
    monkeypatch.setattr(serialapi, "_autodetect_port", lambda: credentials.SERIAL_PORT)
    monkeypatch.setattr(serial, "Serial", lambda port, baudrate, timeout: fake_serial)
    return serialapi.SerialAPI(credentials.SERIAL_PORT)


class Runner:
    def __init__(self, sharecode: str) -> None:
        self._runner = typer.testing.CliRunner()
        self.sharecode = sharecode  # for ease of access

    def run(self, *args: str) -> click.testing.Result:
        result = self._runner.invoke(cli.app, args, catch_exceptions=False)
        print(result.output)
        return result


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch, credentials: FakeCredentials) -> Runner:
    rich.reconfigure(width=80, force_terminal=False)
    # for future console instances
    monkeypatch.setenv("COLUMNS", "80")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv(cli.API_USER_ENV_VAR, credentials.USERNAME)
    monkeypatch.setenv(cli.API_KEY_ENV_VAR, credentials.API_KEY)
    return Runner(credentials.SHARECODE)


class FakeCredentials:
    USERNAME = "PISHOCK-USERNAME"
    API_KEY = "PISHOCK-APIKEY"
    SHARECODE = "62169420AAA"
    SERIAL_PORT = "/dev/ttyFAKE"
    SHOCKER_ID = 1001
    CLIENT_ID = 621


class APIURLs:
    BASE = "https://do.pishock.com/api"
    OPERATE = f"{BASE}/apioperate"
    PAUSE = f"{BASE}/PauseShocker"
    SHOCKER_INFO = f"{BASE}/GetShockerInfo"
    GET_SHOCKERS = f"{BASE}/GetShockers"
    VERIFY_CREDENTIALS = f"{BASE}/VerifyApiCredentials"


@pytest.fixture
def credentials() -> FakeCredentials:
    return FakeCredentials()


class PiShockPatcher:
    """Base class for HTTPPatcher and SerialPatcher."""

    def operate(
        self,
        *,
        operation: httpapi.Operation = httpapi.Operation.VIBRATE,
        duration: int | float = 1,
        intensity: int | None = 2,
    ) -> None:
        raise NotImplementedError

    def info(
        self,
        *,
        paused: bool = False,
        shocker_id: int = FakeCredentials.SHOCKER_ID,
        client_id: int = 1000,  # FIXME use FakeCredentials.CLIENT_ID?
    ) -> None:
        raise NotImplementedError


class HTTPPatcher(PiShockPatcher):
    """Helper class which fakes the PiShock API using responses.

    Each API endpoint has three methods here, e.g. for ApiOperate:

    - operate_matchers: Returns the responses matchers to use for requests to
      this endpoint, matching all the data our client sent. This might be
      configurable via keyword arguments, but only to the extent used by the
      tests.
    - operate_raw: Do a raw responses call for the operate endpoint.
    - operate: Configure responses for an ApiOperate request, with some sensible
      defaults for how a request will usually look.
    """

    HEADERS: dict[str, str | re.Pattern[str]] = {
        "User-Agent": f"{httpapi.NAME}/{pishock.__version__}",
        "Content-Type": "application/json",
    }
    NAME = httpapi.NAME

    def __init__(
        self,
        *,
        responses: RequestsMock,
    ) -> None:
        self.responses = responses

    # ApiOperate

    def operate_matchers(self, **kwargs: Any) -> list[_MatcherType]:
        data = {
            "Username": FakeCredentials.USERNAME,
        }
        for k, v in kwargs.items():
            k = k.capitalize()
            if v is not None:
                data[k] = v
        return [
            matchers.json_params_matcher(data),
            matchers.header_matcher(self.HEADERS),
        ]

    def operate_raw(self, **kwargs: Any) -> None:
        self.responses.post(APIURLs.OPERATE, **kwargs)

    def operate(
        self,
        *,
        body: str = httpapi.HTTPShocker._SUCCESS_MESSAGES[0],
        operation: httpapi.Operation = httpapi.Operation.VIBRATE,
        duration: int | float = 1,
        intensity: int | None = 2,
        name: str | None = None,
        apikey: str | None = None,
        code: str | None = None,
    ) -> None:
        self.operate_raw(
            body=body,
            match=self.operate_matchers(
                op=operation.value,
                duration=duration,
                intensity=intensity,
                name=name or self.NAME,
                apikey=apikey or FakeCredentials.API_KEY,
                code=code or FakeCredentials.SHARECODE,
            ),
        )

    # GetShockerInfo

    def info_matchers(
        self, sharecode: str = FakeCredentials.SHARECODE
    ) -> list[_MatcherType]:
        return [
            matchers.json_params_matcher({
                "Username": FakeCredentials.USERNAME,
                "Apikey": FakeCredentials.API_KEY,
                "Code": sharecode,
            }),
            matchers.header_matcher(self.HEADERS),
        ]

    def info_raw(self, **kwargs: Any) -> None:
        self.responses.post(APIURLs.SHOCKER_INFO, **kwargs)

    def info(
        self,
        *,
        sharecode: str = FakeCredentials.SHARECODE,
        paused: bool = False,
        online: bool = True,
        shocker_id: int = FakeCredentials.SHOCKER_ID,
        client_id: int = 1000,  # FIXME use FakeCredentials.CLIENT_ID?
    ) -> None:
        self.info_raw(
            json={
                "name": "test shocker",
                "clientId": client_id,
                "id": shocker_id,
                "paused": paused,
                "online": online,
                "maxIntensity": 100,
                "maxDuration": 15,
            },
            match=self.info_matchers(sharecode=sharecode),
        )

    # PauseShocker

    def pause_matchers(self, pause: bool) -> list[_MatcherType]:
        return [
            matchers.json_params_matcher({
                "Username": FakeCredentials.USERNAME,
                "Apikey": FakeCredentials.API_KEY,
                "ShockerId": FakeCredentials.SHOCKER_ID,
                "Pause": pause,
            }),
            matchers.header_matcher(self.HEADERS),
        ]

    def pause_raw(self, **kwargs: Any) -> None:
        self.responses.post(APIURLs.PAUSE, **kwargs)

    def pause(
        self, pause: bool, body: str = httpapi.HTTPShocker._SUCCESS_MESSAGE_PAUSE
    ) -> None:
        self.pause_raw(body=body, match=self.pause_matchers(pause))

    # GetShockers

    def get_shockers_matchers(self) -> list[_MatcherType]:
        return [
            matchers.json_params_matcher({
                "Username": FakeCredentials.USERNAME,
                "Apikey": FakeCredentials.API_KEY,
                "ClientId": 1000,
            }),
            matchers.header_matcher(self.HEADERS),
        ]

    def get_shockers_raw(self, **kwargs: Any) -> None:
        self.responses.post(
            APIURLs.GET_SHOCKERS,
            **kwargs,
        )

    def get_shockers(self) -> None:
        self.get_shockers_raw(
            json=[
                {
                    "name": "test shocker",
                    "id": FakeCredentials.SHOCKER_ID,
                    "paused": False,
                },
                {
                    "name": "test shocker 2",
                    "id": FakeCredentials.SHOCKER_ID + 1,
                    "paused": True,
                },
            ],
            match=self.get_shockers_matchers(),
        )

    # VerifyApiCredentials

    def verify_credentials_matchers(
        self,
        username: str = FakeCredentials.USERNAME,
    ) -> list[_MatcherType]:
        return [
            matchers.json_params_matcher({
                "Username": username,
                "Apikey": FakeCredentials.API_KEY,
            }),
            matchers.header_matcher(self.HEADERS),
        ]

    def verify_credentials_raw(self, **kwargs: Any) -> None:
        self.responses.post(
            APIURLs.VERIFY_CREDENTIALS,
            **kwargs,
        )

    def verify_credentials(
        self,
        valid: bool,
        username: str = FakeCredentials.USERNAME,
    ) -> None:
        self.verify_credentials_raw(
            status=http.HTTPStatus.OK if valid else http.HTTPStatus.FORBIDDEN,
            match=self.verify_credentials_matchers(username=username),
        )


class SerialPatcher(PiShockPatcher):
    """Patcher for serial interface."""

    def __init__(
        self,
        serial_api: serialapi.SerialAPI,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self.serial_api = serial_api
        self.monkeypatch = monkeypatch
        self.expected_serial_data: list[dict[str, Any]] = []

    @property
    def fake_dev(self) -> FakeSerial:
        assert isinstance(self.serial_api.dev, FakeSerial)
        return self.serial_api.dev

    def check_serial(self) -> None:
        """Check that the serial data matches what we expect."""
        lines = self.fake_dev.get_written().decode("ascii").splitlines()
        assert [json.loads(line) for line in lines] == self.expected_serial_data

    def operate(
        self,
        *,
        operation: (
            httpapi.Operation | serialapi.SerialOperation
        ) = httpapi.Operation.VIBRATE,
        duration: int | float = 1,
        intensity: int | None = 2,
    ) -> None:
        value = {
            "id": FakeCredentials.SHOCKER_ID,
            "op": operation.name.lower(),
            "duration": duration * 1000,
        }
        if intensity is not None:
            value["intensity"] = intensity
        self.expected_serial_data.append({"cmd": "operate", "value": value})

    def info(
        self,
        *,
        paused: bool = False,
        shocker_id: int = FakeCredentials.SHOCKER_ID,
        client_id: int = 1000,  # FIXME use FakeCredentials.CLIENT_ID?
    ) -> None:
        self.expected_serial_data.append({"cmd": "info"})
        self.fake_dev.set_info_data(
            client_id=client_id,
            shocker_id=shocker_id,
            paused=paused,
        )


class FakeSerial:
    """Helper class which fakes the serial port."""

    def __init__(self) -> None:
        self._written = io.BytesIO()
        self.port = "FAKE"
        self.next_read: list[bytes] = []
        self._info_data: list[dict[str, Any]] = []

    def set_info_data(
        self,
        client_id: int = 1000,  # FIXME use FakeCredentials.CLIENT_ID?
        shocker_id: int = FakeCredentials.SHOCKER_ID,
        paused: bool = False,
    ) -> None:
        self._info_data.append({
            "clientId": client_id,
            "shockers": [{"id": shocker_id, "paused": paused}],
        })

    def write(self, data: bytes) -> None:
        self._written.write(data)
        info_cmd = json.dumps({"cmd": "info"}).encode("ascii") + b"\n"
        if data == info_cmd:
            info_reply = json.dumps(self._info_data.pop(0))
            self.next_read.append(f"TERMINALINFO: {info_reply}".encode("ascii"))

    def read(self, size: int) -> bytes:
        raise NotImplementedError

    def readline(self) -> bytes:
        return self.next_read.pop(0)

    def get_written(self) -> bytes:
        return self._written.getvalue()


@pytest.fixture
def fake_serial() -> FakeSerial:
    return FakeSerial()


@pytest.fixture
def http_patcher(responses: RequestsMock) -> HTTPPatcher:
    return HTTPPatcher(responses=responses)


@pytest.fixture
def serial_patcher(
    serial_api: serialapi.SerialAPI, monkeypatch: pytest.MonkeyPatch
) -> Iterator[SerialPatcher]:
    patcher = SerialPatcher(serial_api=serial_api, monkeypatch=monkeypatch)
    yield patcher
    patcher.check_serial()


@pytest.fixture(params=["api_shocker", "serial_shocker"])
def shocker(request: pytest.FixtureRequest) -> core.Shocker:
    return cast(core.Shocker, request.getfixturevalue(request.param))


@pytest.fixture
def serial_shocker(
    serial_api: serialapi.SerialAPI,
    serial_patcher: SerialPatcher,
    credentials: FakeCredentials,
) -> serialapi.SerialShocker:
    serial_patcher.info()  # for initial info call
    return serial_api.shocker(shocker_id=credentials.SHOCKER_ID)


@pytest.fixture
def api_shocker(
    pishock_api: httpapi.PiShockAPI, credentials: FakeCredentials
) -> httpapi.HTTPShocker:
    return pishock_api.shocker(credentials.SHARECODE)


@pytest.fixture
def patcher(
    request: pytest.FixtureRequest,
    shocker: core.Shocker,
) -> PiShockPatcher:
    """Patcher to patch the PiShock HTTP or serial API.

    We do sommething somewhat unorthodox here: We access the 'shocker' fixture
    to decide what kind of patcher to return. This means things are always in
    sync: If a test gets a HTTP shocker, it gets a HTTP patcher; and if a test
    gets a serial shocker, it gets a serial patcher.
    """
    if isinstance(shocker, httpapi.HTTPShocker):
        return cast(HTTPPatcher, request.getfixturevalue("http_patcher"))
    else:
        assert isinstance(shocker, serialapi.SerialShocker)
        return cast(SerialPatcher, request.getfixturevalue("serial_patcher"))
