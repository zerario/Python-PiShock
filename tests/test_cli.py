from __future__ import annotations

import http
import copy
import json
import pathlib
import random

import click.testing
import platformdirs
import pytest
import rich.prompt
import typer.testing
from pytest_golden.plugin import GoldenTestFixture  # type: ignore[import]

from pishock import cli, zap

from tests.conftest import FakeCredentials, PiShockPatcher  # for type hints


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
    monkeypatch.setenv("PISHOCK_API_USER", credentials.USERNAME)
    monkeypatch.setenv("PISHOCK_API_KEY", credentials.API_KEY)
    # so they get reset after every test
    monkeypatch.setattr(cli, "api", None)
    monkeypatch.setattr(cli, "config", None)
    return Runner(credentials.SHARECODE)


@pytest.fixture(autouse=True)
def patcher_cli_name(patcher: PiShockPatcher, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up the correct name sent to the API for CLI invocations."""
    monkeypatch.setattr(patcher, "NAME", f"{zap.NAME} CLI")


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


CONFIG_DATA = {
    "api": {
        "username": FakeCredentials.USERNAME,
        "key": FakeCredentials.API_KEY,
    },
    "sharecodes": {},
}


class TestConfig:
    @pytest.fixture
    def config(self, config_path: pathlib.Path) -> cli.Config:
        cfg = cli.Config()
        assert cfg._path == config_path
        return cfg

    def test_load_does_not_exist(self, config: cli.Config) -> None:
        config.load()
        assert config.username is None
        assert config.api_key is None

    def test_load(
        self,
        config: cli.Config,
        config_path: pathlib.Path,
        credentials: FakeCredentials,
    ) -> None:
        with config_path.open("w") as f:
            json.dump(CONFIG_DATA, f)

        config.load()
        assert config.username == credentials.USERNAME
        assert config.api_key == credentials.API_KEY

    def test_save(
        self,
        config: cli.Config,
        config_path: pathlib.Path,
        credentials: FakeCredentials,
    ) -> None:
        config.username = credentials.USERNAME
        config.api_key = credentials.API_KEY
        config.save()

        with config_path.open("r") as f:
            data = json.load(f)
        assert data == CONFIG_DATA


class TestInit:
    @pytest.fixture
    def runner_noenv(self, credentials: FakeCredentials) -> Runner:
        """Runner with no env variables set."""
        return Runner(credentials.SHARECODE)

    @pytest.mark.parametrize("valid", [True, False])
    def test_init(
        self,
        config_path: pathlib.Path,
        runner_noenv: Runner,
        patcher: PiShockPatcher,
        monkeypatch: pytest.MonkeyPatch,
        credentials: FakeCredentials,
        valid: bool,
    ) -> None:
        answers = iter([credentials.USERNAME, credentials.API_KEY])
        monkeypatch.setattr(rich.prompt.Prompt, "ask", lambda text: next(answers))
        patcher.verify_credentials(valid)

        result = runner_noenv.run("init")
        assert result.exit_code == (0 if valid else 1)

        if valid:
            assert result.output == "✅ Credentials saved.\n"
            with config_path.open("r") as f:
                data = json.load(f)
            assert data == CONFIG_DATA
        else:
            assert result.output == "❌ Credentials are invalid.\n"
            assert not config_path.exists()

    def test_init_via_args(
        self,
        config_path: pathlib.Path,
        runner: Runner,
        patcher: PiShockPatcher,
    ) -> None:
        patcher.verify_credentials(True)
        result = runner.run("init")  # credentials given
        assert result.exit_code == 0
        assert result.output == "✅ Credentials saved.\n"

        with config_path.open("r") as f:
            data = json.load(f)
        assert data == CONFIG_DATA

    @pytest.mark.parametrize("confirmed", [True, False, "--force"])
    def test_init_overwrite(
        self,
        config_path: pathlib.Path,
        runner_noenv: Runner,
        patcher: PiShockPatcher,
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
            patcher.verify_credentials(True, username=new_username)

        with config_path.open("w") as f:
            json.dump(CONFIG_DATA, f)

        force_arg = ["--force"] if confirmed == "--force" else []
        result = runner_noenv.run("init", *force_arg)
        assert result.exit_code == (0 if confirmed else 1)

        expected_data = copy.deepcopy(CONFIG_DATA)
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
            monkeypatch.setenv("PISHOCK_API_KEY", credentials.API_KEY)
        if has_user:
            monkeypatch.setenv("PISHOCK_API_USER", credentials.USERNAME)

        result = runner_noenv.run("verify")
        assert result.output == golden.out[f"output_{suffix}"]
        assert result.exit_code == 1

    def test_from_config(
        self,
        runner_noenv: Runner,
        config_path: pathlib.Path,
        patcher: PiShockPatcher,
    ) -> None:
        with config_path.open("w") as f:
            json.dump(CONFIG_DATA, f)
        patcher.verify_credentials(True)

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
    paused: bool,
) -> None:
    key = "output"
    if not online:
        key += "_offline"
    if paused:
        key += "_paused"

    patcher.info(online=online, paused=paused)
    result = runner.run("info", runner.sharecode)
    assert result.output == golden.out[key]


@pytest.mark.golden_test("golden/info.yml")
def test_info_error(
    runner: Runner, patcher: PiShockPatcher, golden: GoldenTestFixture
) -> None:
    patcher.info_raw(body="Not JSON lol")
    result = runner.run("info", runner.sharecode)
    assert result.output == golden.out["output_error"]
    assert result.exit_code == 1


@pytest.mark.parametrize(
    "duration, api_duration",
    [(0.3, 300), (1, 1), (2, 2)],
)
@pytest.mark.parametrize("keysmash", [True, False])
@pytest.mark.golden_test("golden/shock.yml")
def test_shock(
    runner: Runner,
    patcher: PiShockPatcher,
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

    patcher.operate(duration=api_duration, op=zap._Operation.SHOCK.value)
    monkeypatch.setattr(random, "random", lambda: 0.01 if keysmash else 0.2)
    monkeypatch.setattr(random, "choices", lambda values, k: "asdfg")

    result = runner.run("shock", runner.sharecode, "-d", str(duration), "-i", "2")
    assert result.output == golden.out[key]


@pytest.mark.golden_test("golden/beep-vibrate.yml")
@pytest.mark.parametrize(
    "duration, api_duration",
    [(0.3, 300), (1, 1)],
)
def test_vibrate(
    runner: Runner,
    patcher: PiShockPatcher,
    golden: GoldenTestFixture,
    duration: float,
    api_duration: int,
) -> None:
    patcher.operate(duration=api_duration, op=zap._Operation.VIBRATE.value)
    result = runner.run("vibrate", runner.sharecode, "-d", str(duration), "-i", "2")
    assert result.output == golden.out["output_vibrate"]


@pytest.mark.golden_test("golden/beep-vibrate.yml")
@pytest.mark.parametrize(
    "duration, api_duration",
    [(0.3, 300), (1, 1)],
)
def test_beep(
    runner: Runner,
    patcher: PiShockPatcher,
    golden: GoldenTestFixture,
    duration: float,
    api_duration: int,
) -> None:
    patcher.operate(op=zap._Operation.BEEP.value, intensity=None, duration=api_duration)
    result = runner.run("beep", runner.sharecode, "-d", str(duration))
    assert result.output == golden.out["output_beep"]


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


@pytest.mark.parametrize("op", list(zap._Operation))
@pytest.mark.parametrize("name, text", [
    ("not_authorized", zap.NotAuthorizedError.TEXT),
    ("unknown_error", "Frobnicating the zap failed"),
])
@pytest.mark.golden_test("golden/errors.yml")
def test_errors(
    runner: Runner,
    patcher: PiShockPatcher,
    golden: GoldenTestFixture,
    op: zap._Operation,
    name: str,
    text: str,
) -> None:
    cmd = op.name.lower()

    intensity = None if op == zap._Operation.BEEP else 2
    patcher.operate(body=text, op=op.value, intensity=intensity)

    args = [cmd, runner.sharecode, "-d", "1"]
    if op != zap._Operation.BEEP:
        args += ["-i", "2"]
    result = runner.run(*args)

    assert result.output == golden.out[f"output_{name}"]
    assert result.exit_code == 1


@pytest.mark.parametrize("cmd, paused", [("pause", True), ("unpause", False)])
def test_pause_unpause(
    cmd: str,
    paused: bool,
    runner: Runner,
    patcher: PiShockPatcher,
) -> None:
    patcher.info()
    patcher.pause(paused)
    result = runner.run(cmd, runner.sharecode)
    assert not result.output


@pytest.mark.parametrize("cmd, paused", [("pause", True), ("unpause", False)])
@pytest.mark.parametrize("name, text", [
    ("not_authorized", zap.NotAuthorizedError.TEXT),
    ("unknown_error", "Frobnicating the zap failed"),
])
@pytest.mark.golden_test("golden/errors.yml")
def test_pause_error(
    cmd: str,
    paused: bool,
    runner: Runner,
    patcher: PiShockPatcher,
    golden: GoldenTestFixture,
    name: str,
    text: str,
) -> None:
    patcher.info()
    patcher.pause(paused, body=text)
    result = runner.run(cmd, runner.sharecode)
    assert result.output == golden.out[f"output_{name}"]
    assert result.exit_code == 1


@pytest.mark.golden_test("golden/shockers.yml")
@pytest.mark.parametrize(
    "outcome", ["ok", "not_authorized", "http_error", "invalid_data"]
)
def test_shockers(
    runner: Runner,
    patcher: PiShockPatcher,
    golden: GoldenTestFixture,
    outcome: str,
) -> None:
    if outcome == "ok":
        patcher.get_shockers()
    elif outcome == "not_authorized":
        patcher.get_shockers_raw(status=http.HTTPStatus.FORBIDDEN)
    elif outcome == "http_error":
        patcher.get_shockers_raw(status=http.HTTPStatus.IM_A_TEAPOT)
    elif outcome == "invalid_data":
        patcher.get_shockers_raw(body="Not JSON lol")

    result = runner.run("shockers", "1000")
    assert result.output == golden.out[f"output_{outcome}"]


@pytest.mark.golden_test("golden/verify.yml")
@pytest.mark.parametrize("outcome", ["ok", "not_authorized", "http_error"])
def test_verify(
    runner: Runner,
    patcher: PiShockPatcher,
    golden: GoldenTestFixture,
    outcome: str,
) -> None:
    if outcome == "ok":
        patcher.verify_credentials(True)
    elif outcome == "not_authorized":
        patcher.verify_credentials(False)
    else:
        patcher.verify_credentials_raw(status=http.HTTPStatus.IM_A_TEAPOT)

    result = runner.run("verify")
    assert result.output == golden.out[f"output_{outcome}"]
    assert result.exit_code == (0 if outcome == "ok" else 1)


class TestSharecodes:
    @pytest.fixture(autouse=True)
    def init_config(
        self, config_path: pathlib.Path, request: pytest.FixtureRequest
    ) -> None:
        """Prepopulate the config with some share codes."""
        data = copy.deepcopy(CONFIG_DATA)

        if not request.node.get_closest_marker("empty_config"):
            data["sharecodes"] = {
                "test1": "62142069AA1",
                "test3": "62142069AA3",  # unsorted to test sorting too
                "test2": "62142069AA2",
            }

        with config_path.open("w") as f:
            json.dump(data, f)

    has_codes_parametrize = pytest.mark.parametrize(
        "has_codes", [True, pytest.param(False, marks=pytest.mark.empty_config)]
    )

    def test_using_saved_code(self, runner: Runner, patcher: PiShockPatcher) -> None:
        patcher.info(sharecode="62142069AA1")
        result = runner.run("info", "test1")
        assert result.exit_code == 0

    @has_codes_parametrize
    @pytest.mark.golden_test("golden/sharecodes/invalid.yml")
    def test_invalid_code(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
        has_codes: bool,
    ) -> None:
        suffix = "with_codes" if has_codes else "no_codes"
        result = runner.run("info", "tset1")
        assert result.output == golden.out[f"output_{suffix}"]
        assert result.exit_code == 1

    @pytest.mark.empty_config
    @pytest.mark.golden_test("golden/sharecodes/list.yml")
    def test_list_info_empty(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
    ) -> None:
        result = runner.run("code-list", "--info")
        assert result.output == golden.out["output_empty"]
        assert result.exit_code == 0

    @pytest.mark.golden_test("golden/sharecodes/list.yml")
    def test_list_info_not_authorized(
        self,
        runner: Runner,
        patcher: PiShockPatcher,
        golden: GoldenTestFixture,
    ) -> None:
        patcher.verify_credentials(False)
        result = runner.run("code-list", "--info")
        assert result.output == golden.out["output_info_not_authorized"]
        assert result.exit_code == 1

    @pytest.mark.golden_test("golden/sharecodes/list.yml")
    def test_list_info(
        self,
        runner: Runner,
        patcher: PiShockPatcher,
        golden: GoldenTestFixture,
    ) -> None:
        patcher.verify_credentials(True)
        patcher.info(sharecode="62142069AA1")
        patcher.info_raw(status=http.HTTPStatus.NOT_FOUND)  # for ...AA2
        patcher.info(sharecode="62142069AA3")
        result = runner.run("code-list", "--info")
        assert result.output == golden.out["output_info"]
        assert result.exit_code == 0

    @has_codes_parametrize
    @pytest.mark.golden_test("golden/sharecodes/list.yml")
    def test_list(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
        has_codes: bool,
    ) -> None:
        suffix = "" if has_codes else "_empty"
        result = runner.run("code-list")
        assert result.output == golden.out[f"output{suffix}"]
        assert result.exit_code == 0

    @has_codes_parametrize
    @pytest.mark.golden_test("golden/sharecodes/add.yml")
    @pytest.mark.parametrize("force", [True, False])
    def test_add(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
        config_path: pathlib.Path,
        has_codes: bool,
        force: bool,
    ):
        force_arg = ["--force"] if force else []
        result = runner.run("code-add", "test4", "62142069AA4", *force_arg)

        suffix = "_force" if force else ""
        assert result.output == golden.out[f"output{suffix}"]
        assert result.exit_code == 0

        with config_path.open("r") as f:
            data = json.load(f)

        if has_codes:
            assert data["sharecodes"] == {
                "test1": "62142069AA1",
                "test3": "62142069AA3",
                "test2": "62142069AA2",
                "test4": "62142069AA4",
            }
        else:
            assert data["sharecodes"] == {"test4": "62142069AA4"}

    @pytest.mark.parametrize("confirmed", [True, False, "--force"])
    @pytest.mark.golden_test("golden/sharecodes/add.yml")
    def test_add_overwrite(
        self,
        runner: Runner,
        config_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        golden: GoldenTestFixture,
        confirmed: bool | str,
    ) -> None:
        if confirmed != "--force":
            monkeypatch.setattr(rich.prompt.Confirm, "ask", lambda text: confirmed)

        suffixes = {
            "--force": "force",
            True: "yes",
            False: "no",
        }
        suffix = suffixes[confirmed]

        force_arg = ["--force"] if confirmed == "--force" else []
        result = runner.run("code-add", "test1", "62142069AB1", *force_arg)
        assert result.output == golden.out[f"output_overwrite_{suffix}"]
        assert result.exit_code == (0 if confirmed else 1)

        with config_path.open("r") as f:
            data = json.load(f)
        if confirmed:
            assert data["sharecodes"] == {
                "test1": "62142069AB1",
                "test3": "62142069AA3",
                "test2": "62142069AA2",
            }
        else:
            assert data["sharecodes"] == {
                "test1": "62142069AA1",
                "test3": "62142069AA3",
                "test2": "62142069AA2",
            }

    @pytest.mark.golden_test("golden/sharecodes/add.yml")
    def test_add_invalid(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
        config_path: pathlib.Path,
    ) -> None:
        result = runner.run("code-add", "test1", "62142069ABX")
        assert result.output == golden.out["output_invalid"]
        assert result.exit_code == 1

        with config_path.open("r") as f:
            data = json.load(f)
        assert data["sharecodes"] == {
            "test1": "62142069AA1",
            "test3": "62142069AA3",
            "test2": "62142069AA2",
        }

    @has_codes_parametrize
    @pytest.mark.golden_test("golden/sharecodes/del.yml")
    def test_del(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
        config_path: pathlib.Path,
        has_codes: bool,
    ) -> None:
        suffix = "" if has_codes else "_empty"

        result = runner.run("code-del", "test1")

        assert result.output == golden.out[f"output{suffix}"]
        assert result.exit_code == 0 if has_codes else 1

        with config_path.open("r") as f:
            data = json.load(f)

        if has_codes:
            assert data["sharecodes"] == {
                "test3": "62142069AA3",
                "test2": "62142069AA2",
            }
        else:
            assert data["sharecodes"] == {}

    @pytest.mark.parametrize(
        "old_name, new_name, overwrite, suffix, successful",
        [
            ("test1", "test4", None, "ok", True),
            ("test1", "test3", True, "exists-overwrite", True),
            ("test1", "test3", "--force", "exists-force", True),
            ("test1", "test3", False, "exists-abort", False),
            ("test1", "test1", None, "same", False),
            ("test4", "test5", None, "not_found", False),
        ],
    )
    @pytest.mark.golden_test("golden/sharecodes/rename.yml")
    def test_rename(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
        config_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        old_name: str,
        new_name: str,
        overwrite: bool | str | None,
        suffix: str,
        successful: bool,
    ) -> None:
        if overwrite in [True, False]:
            monkeypatch.setattr(rich.prompt.Confirm, "ask", lambda text: overwrite)

        force_arg = ["--force"] if overwrite == "--force" else []
        result = runner.run("code-rename", old_name, new_name, *force_arg)

        assert result.output == golden.out[f"output_{suffix}"]
        assert result.exit_code == (0 if successful else 1)

        with config_path.open("r") as f:
            data = json.load(f)

        if successful and overwrite:
            assert data["sharecodes"] == {
                "test3": "62142069AA1",
                "test2": "62142069AA2",
            }
        elif successful:
            assert data["sharecodes"] == {
                "test4": "62142069AA1",
                "test3": "62142069AA3",
                "test2": "62142069AA2",
            }
        else:
            assert data["sharecodes"] == {
                "test1": "62142069AA1",
                "test3": "62142069AA3",
                "test2": "62142069AA2",
            }
