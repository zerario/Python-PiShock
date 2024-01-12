from __future__ import annotations

import copy
import http
import json
import pathlib
import random

import pytest
import rich
import rich.prompt
import rich.console
import serial.tools.list_ports  # type: ignore[import-untyped]
from pytest_golden.plugin import GoldenTestFixture  # type: ignore[import-untyped]

from pishock.zap import httpapi, core, serialapi
from pishock.zap.cli import cli

from tests.conftest import (
    FakeCredentials,
    PiShockPatcher,
    HTTPPatcher,
    SerialPatcher,
    Runner,
    ConfigDataType,
)  # for type hints


pytestmark = pytest.mark.skipif(
    rich.console.WINDOWS, reason="Output looks different on Windows"
)


@pytest.fixture(autouse=True)
def patcher_cli_name(
    http_patcher: HTTPPatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Set up the correct name sent to the API for CLI invocations."""
    monkeypatch.setattr(http_patcher, "NAME", f"{httpapi.NAME} CLI")


class TestInit:
    @pytest.fixture
    def runner_noenv(self, runner: Runner, monkeypatch: pytest.MonkeyPatch) -> Runner:
        """Runner with no auth env variables set."""
        monkeypatch.delenv(cli.API_USER_ENV_VAR)
        monkeypatch.delenv(cli.API_KEY_ENV_VAR)
        return runner

    @pytest.mark.parametrize("valid", [True, False])
    def test_init(
        self,
        config_path: pathlib.Path,
        config_data: ConfigDataType,
        runner_noenv: Runner,
        http_patcher: HTTPPatcher,
        monkeypatch: pytest.MonkeyPatch,
        credentials: FakeCredentials,
        valid: bool,
    ) -> None:
        answers = iter([credentials.USERNAME, credentials.API_KEY])
        monkeypatch.setattr(rich.prompt.Prompt, "ask", lambda text: next(answers))
        http_patcher.verify_credentials(valid)

        result = runner_noenv.run("init")
        assert result.exit_code == (0 if valid else 1)

        if valid:
            assert result.output == "✅ Credentials saved.\n"
            with config_path.open("r") as f:
                data = json.load(f)
            assert data == config_data
        else:
            assert result.output == "❌ Credentials are invalid.\n"
            assert not config_path.exists()

    def test_init_via_args(
        self,
        config_path: pathlib.Path,
        config_data: ConfigDataType,
        runner: Runner,
        http_patcher: HTTPPatcher,
    ) -> None:
        http_patcher.verify_credentials(True)
        result = runner.run("init")  # credentials given
        assert result.exit_code == 0
        assert result.output == "✅ Credentials saved.\n"

        with config_path.open("r") as f:
            data = json.load(f)
        assert data == config_data

    @pytest.mark.parametrize("confirmed", [True, False, "--force"])
    def test_init_overwrite(
        self,
        config_path: pathlib.Path,
        config_data: ConfigDataType,
        runner_noenv: Runner,
        http_patcher: HTTPPatcher,
        monkeypatch: pytest.MonkeyPatch,
        credentials: FakeCredentials,
        confirmed: bool | str,
    ) -> None:
        new_username = credentials.USERNAME + "-NEW"

        if confirmed != "--force":
            monkeypatch.setattr(rich.prompt.Confirm, "ask", lambda text: confirmed)

        if confirmed:
            answers = iter([new_username, credentials.API_KEY])
            monkeypatch.setattr(rich.prompt.Prompt, "ask", lambda text: next(answers))
            http_patcher.verify_credentials(True, username=new_username)

        with config_path.open("w") as f:
            json.dump(config_data, f)

        force_arg = ["--force"] if confirmed == "--force" else []
        result = runner_noenv.run("init", *force_arg)
        assert result.exit_code == (0 if confirmed else 1)

        expected_data = copy.deepcopy(config_data)
        if confirmed:
            expected_data["api"]["username"] = new_username

        with config_path.open("r") as f:
            data = json.load(f)
        assert data == expected_data

    @pytest.mark.parametrize(
        "has_user, has_key, suffix",
        [
            (True, False, "user_only"),
            (False, True, "key_only"),
            (False, False, "none"),
        ],
    )
    @pytest.mark.golden_test("golden/no-config.yml")
    def test_no_config(
        self,
        runner_noenv: Runner,
        monkeypatch: pytest.MonkeyPatch,
        credentials: FakeCredentials,
        golden: GoldenTestFixture,
        has_user: bool,
        has_key: bool,
        suffix: str,
    ) -> None:
        if has_key:
            monkeypatch.setenv(cli.API_KEY_ENV_VAR, credentials.API_KEY)
        if has_user:
            monkeypatch.setenv(cli.API_USER_ENV_VAR, credentials.USERNAME)

        result = runner_noenv.run("verify")
        assert result.output == golden.out[f"output_{suffix}"]
        assert result.exit_code == 1

    def test_from_config(
        self,
        runner_noenv: Runner,
        config_path: pathlib.Path,
        config_data: ConfigDataType,
        http_patcher: HTTPPatcher,
    ) -> None:
        with config_path.open("w") as f:
            json.dump(config_data, f)
        http_patcher.verify_credentials(True)

        result = runner_noenv.run("verify")
        assert result.exit_code == 0


@pytest.mark.parametrize("online", [True, False])
@pytest.mark.parametrize("paused", [True, False])
@pytest.mark.golden_test("golden/info.yml")
def test_info(
    runner: Runner,
    golden: GoldenTestFixture,
    patcher: PiShockPatcher,
    online: bool,
    credentials: FakeCredentials,
    paused: bool,
) -> None:
    if isinstance(patcher, HTTPPatcher):
        patcher.info(online=online, paused=paused)
        shocker_arg = credentials.SHARECODE
        serial_flag = []
    elif not online:
        pytest.skip("Serial API does not support offline status")
        assert False  # for mypy
    else:
        patcher.info(paused=paused)  # for initial get_shocker()
        patcher.info(paused=paused)
        shocker_arg = str(credentials.SHOCKER_ID)
        serial_flag = ["--serial"]

    key = "output"
    if not online:
        key += "_offline"
    if paused:
        key += "_paused"
    if isinstance(patcher, SerialPatcher):
        key += "_serial"

    result = runner.run(*serial_flag, "info", shocker_arg)
    assert result.output == golden.out[key]


@pytest.mark.golden_test("golden/info.yml")
def test_info_error(
    runner: Runner, http_patcher: HTTPPatcher, golden: GoldenTestFixture
) -> None:
    http_patcher.info_raw(body="Not JSON lol")
    result = runner.run("info", runner.sharecode)
    assert result.output == golden.out["output_error"]
    assert result.exit_code == 1


class TestOperations:
    @pytest.fixture
    def serial_flag(self, shocker: core.Shocker) -> list[str]:
        return ["--serial"] if shocker.IS_SERIAL else []

    @pytest.fixture
    def shocker_arg(self, shocker: core.Shocker, credentials: FakeCredentials) -> str:
        if shocker.IS_SERIAL:
            return str(credentials.SHOCKER_ID)
        return credentials.SHARECODE

    @pytest.fixture(autouse=True)
    def expect_serial_info(self, patcher: PiShockPatcher) -> None:
        if isinstance(patcher, SerialPatcher):
            patcher.info()

    @pytest.mark.parametrize(
        "duration, api_duration",
        [(0.3, 300), (1, 1), (2, 2)],
    )
    @pytest.mark.parametrize("keysmash", [True, False])
    @pytest.mark.golden_test("golden/shock.yml")
    def test_shock(
        self,
        runner: Runner,
        patcher: PiShockPatcher,
        serial_flag: str,
        shocker_arg: str,
        golden: GoldenTestFixture,
        monkeypatch: pytest.MonkeyPatch,
        duration: float,
        api_duration: int,
        keysmash: bool,
    ) -> None:
        key = "output"
        if duration > 1:
            key += "_long"
        if keysmash:
            key += "_keysmash"

        patcher.operate(
            duration=duration if serial_flag else api_duration,
            operation=httpapi.Operation.SHOCK,
        )
        monkeypatch.setattr(random, "random", lambda: 0.01 if keysmash else 0.2)
        monkeypatch.setattr(random, "choices", lambda values, k: "asdfg")

        result = runner.run(
            *serial_flag, "shock", shocker_arg, "-d", str(duration), "-i", "2"
        )
        assert result.output == golden.out[key]

    @pytest.mark.golden_test("golden/beep-vibrate.yml")
    @pytest.mark.parametrize(
        "duration, api_duration",
        [(0.3, 300), (1, 1)],
    )
    def test_vibrate(
        self,
        runner: Runner,
        patcher: PiShockPatcher,
        serial_flag: str,
        shocker_arg: str,
        golden: GoldenTestFixture,
        duration: float,
        api_duration: int,
    ) -> None:
        patcher.operate(
            duration=duration if serial_flag else api_duration,
            operation=httpapi.Operation.VIBRATE,
        )
        result = runner.run(
            *serial_flag, "vibrate", shocker_arg, "-d", str(duration), "-i", "2"
        )
        assert result.output == golden.out["output_vibrate"]

    @pytest.mark.golden_test("golden/beep-vibrate.yml")
    @pytest.mark.parametrize(
        "duration, api_duration",
        [(0.3, 300), (1, 1)],
    )
    def test_beep(
        self,
        runner: Runner,
        patcher: PiShockPatcher,
        serial_flag: str,
        shocker_arg: str,
        golden: GoldenTestFixture,
        duration: float,
        api_duration: int,
    ) -> None:
        patcher.operate(
            operation=httpapi.Operation.BEEP,
            intensity=None,
            duration=duration if serial_flag else api_duration,
        )
        result = runner.run(*serial_flag, "beep", shocker_arg, "-d", str(duration))
        assert result.output == golden.out["output_beep"]

    @pytest.mark.golden_test("golden/end.yml")
    def test_end(
        self,
        runner: Runner,
        patcher: PiShockPatcher,
        serial_flag: str,
        shocker_arg: str,
        credentials: FakeCredentials,
        golden: GoldenTestFixture,
    ) -> None:
        if isinstance(patcher, SerialPatcher):
            patcher.operate(
                operation=serialapi.SerialOperation.END,
                intensity=None,
                duration=0,
            )
        result = runner.run(*serial_flag, "end", shocker_arg)
        suffix = "serial" if serial_flag else "http"
        assert result.output == golden.out[f"output_{suffix}"]
        assert result.exit_code == (0 if serial_flag else 1)


@pytest.mark.parametrize(
    "operation, duration, intensity",
    [
        # invalid durations
        ("vibrate", "-1", "2"),
        ("vibrate", "a", "2"),
        ("vibrate", "16", "2"),
        ("vibrate", "0.05", "2"),
        # invalid intensities
        ("vibrate", "1", "-1"),
        ("vibrate", "1", "101"),
        ("vibrate", "1", "10.5"),
        # invalid duratinos
        ("shock", "-1", "2"),
        ("shock", "a", "2"),
        ("shock", "16", "2"),
        ("shock", "0.05", "2"),
        # invalid intensities
        ("shock", "1", "-1"),
        ("shock", "1", "101"),
        ("shock", "1", "10.5"),
        # invalid durations
        ("beep", "-1", None),
        ("beep", "a", None),
        ("beep", "16", None),
        ("beep", "0.05", None),
        # invalid intensites
        ("beep", "1", "2"),
    ],
)
@pytest.mark.golden_test("golden/invalid-inputs.yml")
def test_invalid_inputs(
    runner: Runner,
    golden: GoldenTestFixture,
    operation: str,
    duration: str,
    intensity: str | None,
) -> None:
    args = [operation, runner.sharecode, "-d", duration]
    if intensity is not None:
        args += ["-i", intensity]
    result = runner.run(*args)
    assert result.output == golden.out[f"output_{operation}_{duration}_{intensity}"]
    assert result.exit_code in [1, 2]


@pytest.mark.parametrize("op", list(httpapi.Operation))
@pytest.mark.parametrize(
    "name, text",
    [
        ("not_authorized", httpapi.NotAuthorizedError.TEXT),
        ("unknown_error", "Frobnicating the zap failed"),
    ],
)
@pytest.mark.golden_test("golden/errors.yml")
def test_errors(
    runner: Runner,
    http_patcher: HTTPPatcher,
    golden: GoldenTestFixture,
    op: httpapi.Operation,
    name: str,
    text: str,
) -> None:
    cmd = op.name.lower()

    intensity = None if op == httpapi.Operation.BEEP else 2
    http_patcher.operate(body=text, operation=op, intensity=intensity)

    args = [cmd, runner.sharecode, "-d", "1"]
    if op != httpapi.Operation.BEEP:
        args += ["-i", "2"]
    result = runner.run(*args)

    assert result.output == golden.out[f"output_{name}"]
    assert result.exit_code == 1


@pytest.mark.parametrize("cmd, paused", [("pause", True), ("unpause", False)])
def test_pause_unpause(
    cmd: str,
    paused: bool,
    runner: Runner,
    http_patcher: HTTPPatcher,
) -> None:
    http_patcher.info()
    http_patcher.pause(paused)
    result = runner.run(cmd, runner.sharecode)
    assert not result.output


@pytest.mark.parametrize("cmd, paused", [("pause", True), ("unpause", False)])
@pytest.mark.parametrize(
    "name, text",
    [
        ("not_authorized", httpapi.NotAuthorizedError.TEXT),
        ("unknown_error", "Frobnicating the zap failed"),
    ],
)
@pytest.mark.golden_test("golden/errors.yml")
def test_pause_error(
    cmd: str,
    paused: bool,
    runner: Runner,
    http_patcher: HTTPPatcher,
    golden: GoldenTestFixture,
    name: str,
    text: str,
) -> None:
    http_patcher.info()
    http_patcher.pause(paused, body=text)
    result = runner.run(cmd, runner.sharecode)
    assert result.output == golden.out[f"output_{name}"]
    assert result.exit_code == 1


@pytest.mark.golden_test("golden/shockers.yml")
@pytest.mark.parametrize(
    "outcome", ["ok", "not_authorized", "http_error", "invalid_data"]
)
def test_shockers(
    runner: Runner,
    http_patcher: HTTPPatcher,
    golden: GoldenTestFixture,
    outcome: str,
) -> None:
    if outcome == "ok":
        http_patcher.get_shockers()
    elif outcome == "not_authorized":
        http_patcher.get_shockers_raw(status=http.HTTPStatus.FORBIDDEN)
    elif outcome == "http_error":
        http_patcher.get_shockers_raw(status=http.HTTPStatus.INTERNAL_SERVER_ERROR)
    elif outcome == "invalid_data":
        http_patcher.get_shockers_raw(body="Not JSON lol")

    result = runner.run("shockers", "1000")
    assert result.output == golden.out[f"output_{outcome}"]


@pytest.mark.golden_test("golden/verify.yml")
@pytest.mark.parametrize("outcome", ["ok", "not_authorized", "http_error"])
def test_verify(
    runner: Runner,
    http_patcher: HTTPPatcher,
    golden: GoldenTestFixture,
    outcome: str,
) -> None:
    if outcome == "ok":
        http_patcher.verify_credentials(True)
    elif outcome == "not_authorized":
        http_patcher.verify_credentials(False)
    else:
        http_patcher.verify_credentials_raw(
            status=http.HTTPStatus.INTERNAL_SERVER_ERROR
        )

    result = runner.run("verify")
    assert result.output == golden.out[f"output_{outcome}"]
    assert result.exit_code == (0 if outcome == "ok" else 1)


@pytest.mark.golden_test("golden/misc.yml")
def test_http_shocker_with_id(
    runner: Runner, golden: GoldenTestFixture, credentials: FakeCredentials
) -> None:
    result = runner.run("info", str(credentials.SHOCKER_ID))
    assert result.output == golden.out["output_http_with_id"]


@pytest.mark.golden_test("golden/misc.yml")
def test_serial_shocker_with_sharecode(
    runner: Runner,
    golden: GoldenTestFixture,
    http_patcher: HTTPPatcher,
    serial_patcher: SerialPatcher,
    credentials: FakeCredentials,
) -> None:
    http_patcher.info()  # to resolve share code
    serial_patcher.info()  # for initial get_shocker()
    serial_patcher.info()  # actual info call
    result = runner.run("--serial", "info", credentials.SHARECODE)
    assert result.output == golden.out["output_serial_with_sharecode"]


@pytest.mark.golden_test("golden/misc.yml")
def test_serial_autodetect_error(
    runner: Runner,
    golden: GoldenTestFixture,
    monkeypatch: pytest.MonkeyPatch,
    credentials: FakeCredentials,
) -> None:
    monkeypatch.setattr(serial.tools.list_ports, "comports", lambda: [])
    result = runner.run("--serial", "info", credentials.SHARECODE)
    assert result.output == golden.out["output_serial_error"]
    assert result.exit_code == 1


@pytest.mark.golden_test("golden/misc.yml")
def test_port_without_serial(
    runner: Runner,
    golden: GoldenTestFixture,
    credentials: FakeCredentials,
) -> None:
    result = runner.run(
        "--port", credentials.SERIAL_PORT, "info", credentials.SHARECODE
    )
    assert result.output == golden.out["output_serial_port_without_serial"]
    assert result.exit_code == 1
