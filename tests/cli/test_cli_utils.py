from __future__ import annotations

import pathlib
import json

import pytest

from pishock.zap.cli import cli_utils

from tests.conftest import (
    FakeCredentials,
    ConfigDataType,
)  # for type hints


@pytest.fixture
def config(config_path: pathlib.Path) -> cli_utils.Config:
    cfg = cli_utils.Config()
    assert cfg._path == config_path
    return cfg


def test_load_does_not_exist(config: cli_utils.Config) -> None:
    config.load()
    assert config.username is None
    assert config.api_key is None


def test_load(
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
