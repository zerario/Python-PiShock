from __future__ import annotations

import http
import io
import json
import re
import pathlib
from typing import Any, Callable, Iterator

import pytest
import rich
import platformdirs
import click.testing
import typer.testing
from responses import RequestsMock, matchers
from typing_extensions import TypeAlias

from pishock.zap import httpapi, core
from pishock.zap.cli import cli

_MatcherType: TypeAlias = Callable[..., Any]
ConfigDataType: TypeAlias = dict[str, dict[str, str]]


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
        "sharecodes": {},
    }


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
    rich.reconfigure(width=80)
    monkeypatch.setenv("COLUMNS", "80")  # for future console instances
    monkeypatch.setenv("PISHOCK_API_USER", credentials.USERNAME)
    monkeypatch.setenv("PISHOCK_API_KEY", credentials.API_KEY)
    return Runner(credentials.SHARECODE)


class FakeCredentials:
    USERNAME = "PISHOCK-USERNAME"
    API_KEY = "PISHOCK-APIKEY"
    SHARECODE = "62169420AAA"
    SERIAL_PORT = "/dev/ttyFAKE"
    SHOCKER_ID = 1234


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
        "User-Agent": f"{httpapi.NAME}/{core.__version__}",
        "Content-Type": "application/json",
    }
    NAME = httpapi.NAME

    def __init__(self, responses: RequestsMock) -> None:
        self.responses = responses
        self.expected_serial_data: Any = None

    def check_serial(self, dev: io.BytesIO) -> None:
        """Check that the serial data matches what we expect."""
        if self.expected_serial_data is None:
            assert not dev.getvalue()
        else:
            data = json.loads(dev.getvalue().decode("utf-8"))
            assert data == self.expected_serial_data

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
        body: str = httpapi.HTTPShocker.SUCCESS_MESSAGES[0],
        operation: httpapi.Operation = httpapi.Operation.VIBRATE,
        duration: int | float = 1,
        intensity: int | None = 2,
        name: str | None = None,
        apikey: str | None = None,
        code: str | None = None,
        is_serial: bool = False,
    ) -> None:
        if is_serial:
            assert name is None
            assert apikey is None
            assert code is None
            value = {
                "id": FakeCredentials.SHOCKER_ID,
                "op": operation.name.lower(),
                "duration": duration * 1000,
            }
            if intensity is not None:
                value["intensity"] = intensity
            self.expected_serial_data = {"cmd": "operate", "value": value}
        else:
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
        sharecode: str = FakeCredentials.SHARECODE,
        paused: bool = False,
        online: bool = True,
    ) -> None:
        self.info_raw(
            json={
                "name": "test shocker",
                "clientId": 1000,
                "id": 1001,
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
                "ShockerId": 1001,
                "Pause": pause,
            }),
            matchers.header_matcher(self.HEADERS),
        ]

    def pause_raw(self, **kwargs: Any) -> None:
        self.responses.post(APIURLs.PAUSE, **kwargs)

    def pause(
        self, pause: bool, body: str = httpapi.HTTPShocker.SUCCESS_MESSAGE_PAUSE
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
                {"name": "test shocker", "id": 1001, "paused": False},
                {"name": "test shocker 2", "id": 1002, "paused": True},
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


@pytest.fixture
def fake_serial_dev() -> io.BytesIO:
    return io.BytesIO()


@pytest.fixture
def patcher(
    responses: RequestsMock, fake_serial_dev: io.BytesIO
) -> Iterator[PiShockPatcher]:
    """Helper to patch the PiShock API using responses."""
    patcher = PiShockPatcher(responses)
    yield patcher
    patcher.check_serial(fake_serial_dev)
