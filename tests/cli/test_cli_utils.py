from __future__ import annotations

import pathlib
import json
from typing import Callable

import pytest
import click.exceptions

from pishock.zap.cli import cli_utils
from pishock.zap import httpapi, serialapi

# for type hints
from tests.conftest import FakeCredentials, ConfigDataType


@pytest.fixture
def config(config_path: pathlib.Path) -> cli_utils.Config:
    cfg = cli_utils.Config()
    assert cfg._path == config_path
    return cfg


@pytest.fixture(autouse=True)
def dumb_term(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no terminal escape codes are used in output."""
    monkeypatch.setenv("TERM", "dumb")


class TestConfig:
    def test_load_does_not_exist(self, config: cli_utils.Config) -> None:
        config.load()
        assert config.username is None
        assert config.api_key is None

    def test_load(
        self,
        config: cli_utils.Config,
        config_path: pathlib.Path,
        config_data: ConfigDataType,
        credentials: FakeCredentials,
    ) -> None:
        with config_path.open("w") as f:
            json.dump(config_data, f)

        config.load()
        assert config.username == credentials.USERNAME
        assert config.api_key == credentials.API_KEY

    def test_save(
        self,
        config: cli_utils.Config,
        config_path: pathlib.Path,
        config_data: ConfigDataType,
        credentials: FakeCredentials,
    ) -> None:
        config.username = credentials.USERNAME
        config.api_key = credentials.API_KEY
        config.save()

        with config_path.open("r") as f:
            data = json.load(f)
        assert data == config_data

    def test_load_shockers(
        self,
        config: cli_utils.Config,
        config_path: pathlib.Path,
        config_data: ConfigDataType,
        credentials: FakeCredentials,
    ) -> None:
        config_data["shockers"]["test"] = {
            "sharecode": credentials.SHARECODE,
            "shocker_id": credentials.SHOCKER_ID,
        }
        with config_path.open("w") as f:
            json.dump(config_data, f)

        config.load()
        assert config.shockers == {
            "test": cli_utils.ShockerInfo(
                sharecode=credentials.SHARECODE,
                shocker_id=credentials.SHOCKER_ID,
            )
        }

    def test_load_shockers_migrate(
        self,
        config: cli_utils.Config,
        config_path: pathlib.Path,
        config_data: ConfigDataType,
        credentials: FakeCredentials,
    ) -> None:
        config_data["sharecodes"] = {"test": credentials.SHARECODE}
        with config_path.open("w") as f:
            json.dump(config_data, f)

        config.load()
        assert config.shockers == {
            "test": cli_utils.ShockerInfo(
                sharecode=credentials.SHARECODE,
                shocker_id=None,
            )
        }

    def test_load_shockers_empty(
        self,
        config: cli_utils.Config,
        config_path: pathlib.Path,
        config_data: ConfigDataType,
    ) -> None:
        del config_data["shockers"]
        with config_path.open("w") as f:
            json.dump(config_data, f)

        config.load()
        assert config.shockers == {}


class TestAppContext:
    @pytest.fixture
    def app_context(self, config: cli_utils.Config) -> cli_utils.AppContext:
        return cli_utils.AppContext(
            config=config,
            pishock_api=None,
            serial_api=None,
        )

    def test_ensure_pishock_api(
        self,
        config: cli_utils.Config,
        pishock_api: httpapi.PiShockAPI,
    ) -> None:
        app_context = cli_utils.AppContext(
            config=config,
            pishock_api=pishock_api,
            serial_api=None,
        )
        assert app_context.ensure_pishock_api() is pishock_api

    def test_ensure_pishock_api_not_available(
        self,
        app_context: cli_utils.AppContext,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        app_context.pishock_api = None
        with pytest.raises(click.exceptions.Exit):
            app_context.ensure_pishock_api()

        out, _err = capsys.readouterr()
        assert out == "Error: This command is only available with the HTTP API.\n"

    def test_ensure_serial_api(
        self, config: cli_utils.Config, serial_api: serialapi.SerialAPI
    ) -> None:
        app_context = cli_utils.AppContext(
            config=config,
            pishock_api=None,
            serial_api=serial_api,
        )
        assert app_context.ensure_serial_api() is serial_api

    def test_ensure_serial_api_not_available(
        self,
        app_context: cli_utils.AppContext,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        app_context.serial_api = None
        with pytest.raises(click.exceptions.Exit):
            app_context.ensure_serial_api()

        out, _err = capsys.readouterr()
        assert out == "Error: This command is only available with the serial API.\n"


class TestRange:
    def test_pick(self) -> None:
        r = cli_utils.Range(a=1, b=2)
        assert r.pick() in (1, 2)

    def test_invalid(self) -> None:
        with pytest.raises(ValueError):
            cli_utils.Range(a=2, b=1)


def test_print_exception(capsys: pytest.CaptureFixture[str]) -> None:
    cli_utils.print_exception(ValueError("wrong value"))
    out, _err = capsys.readouterr()
    assert out == "Error: wrong value (ValueError)\n"


def test_print_error(capsys: pytest.CaptureFixture[str]) -> None:
    cli_utils.print_error("something went wrong")
    out, _err = capsys.readouterr()
    assert out == "Error: something went wrong\n"


@pytest.mark.parametrize(
    "func, value, expected",
    [
        (cli_utils.bool_emoji, True, ":white_check_mark:"),
        (cli_utils.bool_emoji, False, ":x:"),
        (cli_utils.paused_emoji, True, ":double_vertical_bar:"),
        (cli_utils.paused_emoji, False, ":arrow_forward:"),
    ],
)
def test_emoji(func: Callable[[bool], str], value: bool, expected: str) -> None:
    assert func(value) == expected
