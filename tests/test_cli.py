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
        "has_user, has_key, filename",
        [
            (True, False, "user-only"),
            (False, True, "key-only"),
            (False, False, "none"),
        ],
    )
    def test_no_config(
        self,
        runner_noenv: Runner,
        monkeypatch: pytest.MonkeyPatch,
        credentials: FakeCredentials,
        golden: GoldenTestFixture,
        has_user: bool,
        has_key: bool,
        filename: str,
    ) -> None:
        if has_key:
            monkeypatch.setenv("PISHOCK_API_KEY", credentials.API_KEY)
        if has_user:
            monkeypatch.setenv("PISHOCK_API_USER", credentials.USERNAME)

        golden = golden.open(f"golden/no-config/{filename}.yml")

        result = runner_noenv.run("verify")
        assert result.output == golden.out["output"]
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
def test_info(
    runner: Runner,
    golden: GoldenTestFixture,
    patcher: PiShockPatcher,
    online: bool,
    paused: bool,
) -> None:
    filename = "info"
    if not online:
        filename += "-offline"
    if paused:
        filename += "-paused"
    golden = golden.open(f"golden/info/{filename}.yml")

    patcher.info(online=online, paused=paused)
    result = runner.run("info", runner.sharecode)
    assert result.output == golden.out["output"]


@pytest.mark.golden_test("golden/info/info-error.yml")
def test_info_error(
    runner: Runner, patcher: PiShockPatcher, golden: GoldenTestFixture
) -> None:
    patcher.info_raw(body="Not JSON lol")
    result = runner.run("info", runner.sharecode)
    assert result.output == golden.out["output"]
    assert result.exit_code == 1


@pytest.mark.parametrize(
    "duration, api_duration",
    [(0.3, 300), (1, 1), (2, 2)],
)
@pytest.mark.parametrize("keysmash", [True, False])
def test_shock(
    runner: Runner,
    patcher: PiShockPatcher,
    golden: GoldenTestFixture,
    monkeypatch: pytest.MonkeyPatch,
    duration: float,
    api_duration: int,
    keysmash: bool,
) -> None:
    filename = "shock"
    if duration > 1:
        filename += "-long"
    if keysmash:
        filename += "-keysmash"

    golden = golden.open(f"golden/shock/{filename}.yml")
    patcher.operate(duration=api_duration, op=zap._Operation.SHOCK.value)
    monkeypatch.setattr(random, "random", lambda: 0.01 if keysmash else 0.2)
    monkeypatch.setattr(random, "choices", lambda values, k: "asdfg")

    result = runner.run("shock", runner.sharecode, "-d", str(duration), "-i", "2")
    assert result.output == golden.out["output"]


@pytest.mark.golden_test("golden/vibrate/vibrate.yml")
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
    assert result.output == golden.out["output"]


@pytest.mark.golden_test("golden/beep/beep.yml")
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
    assert result.output == golden.out["output"]


@pytest.mark.parametrize("op", list(zap._Operation))
def test_errors(
    runner: Runner,
    patcher: PiShockPatcher,
    golden: GoldenTestFixture,
    op: zap._Operation,
) -> None:
    cmd = op.name.lower()
    golden = golden.open(f"golden/{cmd}/{cmd}-error.yml")

    intensity = None if op == zap._Operation.BEEP else 2
    patcher.operate(body=zap.NotAuthorizedError.TEXT, op=op.value, intensity=intensity)

    args = [cmd, runner.sharecode, "-d", "1"]
    if op != zap._Operation.BEEP:
        args += ["-i", "2"]
    result = runner.run(*args)

    assert result.output == golden.out["output"]
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
def test_pause_unauthorized(
    cmd: str,
    paused: bool,
    runner: Runner,
    patcher: PiShockPatcher,
) -> None:
    patcher.info()
    patcher.pause(paused, body=zap.NotAuthorizedError.TEXT)
    result = runner.run(cmd, runner.sharecode)
    assert result.exit_code == 1


@pytest.mark.golden_test("golden/shockers.yml")
def test_shockers(
    runner: Runner,
    patcher: PiShockPatcher,
    golden: GoldenTestFixture,
) -> None:
    patcher.get_shockers()
    result = runner.run("shockers", "1000")
    assert result.output == golden.out["output"]


@pytest.mark.parametrize("valid", [True, False])
def test_verify_credentials(
    runner: Runner,
    patcher: PiShockPatcher,
    golden: GoldenTestFixture,
    valid: bool,
) -> None:
    patcher.verify_credentials(valid)
    filename = "valid" if valid else "invalid"
    golden = golden.open(f"golden/verify-credentials/{filename}.yml")

    result = runner.run("verify")
    assert result.output == golden.out["output"]
    assert result.exit_code == (0 if valid else 1)


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
    def test_invalid_code(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
        has_codes: bool,
    ) -> None:
        filename = "with-codes" if has_codes else "no-codes"
        golden = golden.open(f"golden/sharecodes/invalid-{filename}.yml")

        result = runner.run("info", "tset1")
        assert result.output == golden.out["output"]
        assert result.exit_code == 1

    @pytest.mark.empty_config
    @pytest.mark.golden_test("golden/sharecodes/list-empty.yml")
    def test_list_info_empty(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
    ) -> None:
        result = runner.run("code-list", "--info")
        assert result.output == golden.out["output"]
        assert result.exit_code == 0

    @pytest.mark.golden_test("golden/sharecodes/list-info-not-authorized.yml")
    def test_list_info_not_authorized(
        self,
        runner: Runner,
        patcher: PiShockPatcher,
        golden: GoldenTestFixture,
    ) -> None:
        patcher.verify_credentials(False)
        result = runner.run("code-list", "--info")
        assert result.output == golden.out["output"]
        assert result.exit_code == 1

    @pytest.mark.golden_test("golden/sharecodes/list-info.yml")
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
        assert result.output == golden.out["output"]
        assert result.exit_code == 0

    @has_codes_parametrize
    def test_list(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
        has_codes: bool,
    ) -> None:
        suffix = "" if has_codes else "-empty"
        golden = golden.open(f"golden/sharecodes/list{suffix}.yml")
        result = runner.run("code-list")
        assert result.output == golden.out["output"]
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
        assert result.output == golden.out["output"]
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
        golden = golden.open(f"golden/sharecodes/add-overwrite-{suffix}.yml")

        force_arg = ["--force"] if confirmed == "--force" else []
        result = runner.run("code-add", "test1", "62142069AB1", *force_arg)
        assert result.output == golden.out["output"]
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

    @pytest.mark.golden_test("golden/sharecodes/add-invalid.yml")
    def test_add_invalid(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
        config_path: pathlib.Path,
    ) -> None:
        result = runner.run("code-add", "test1", "62142069ABX")
        assert result.output == golden.out["output"]
        assert result.exit_code == 1

        with config_path.open("r") as f:
            data = json.load(f)
        assert data["sharecodes"] == {
            "test1": "62142069AA1",
            "test3": "62142069AA3",
            "test2": "62142069AA2",
        }

    @has_codes_parametrize
    def test_del(
        self,
        runner: Runner,
        golden: GoldenTestFixture,
        config_path: pathlib.Path,
        has_codes: bool,
    ) -> None:
        suffix = "" if has_codes else "-empty"
        golden = golden.open(f"golden/sharecodes/del{suffix}.yml")

        result = runner.run("code-del", "test1")

        assert result.output == golden.out["output"]
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

    @pytest.mark.parametrize("old_name, new_name, overwrite, suffix, successful", [
        ("test1", "test4", None, "ok", True),
        ("test1", "test3", True, "exists-overwrite", True),
        ("test1", "test3", "--force", "exists-force", True),
        ("test1", "test3", False, "exists-abort", False),
        ("test1", "test1", None, "same", False),
        ("test4", "test5", None, "not-found", False),
    ])
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

        golden = golden.open(f"golden/sharecodes/rename-{suffix}.yml")
        assert result.output == golden.out["output"]
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
