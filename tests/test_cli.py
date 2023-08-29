import random

import click.testing
import pytest
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
    monkeypatch.setenv("PISHOCK_API_KEY", credentials.APIKEY)
    return Runner(credentials.SHARECODE)


@pytest.fixture(autouse=True)
def patcher_cli_name(patcher: PiShockPatcher, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up the correct name sent to the API for CLI invocations."""
    monkeypatch.setattr(patcher, "NAME", f"{zap.NAME} CLI")


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

    result = runner.run("verify-credentials")
    assert result.output == golden.out["output"]
    assert result.exit_code == (0 if valid else 1)
