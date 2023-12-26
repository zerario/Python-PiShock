from __future__ import annotations

import copy
import json
import http
import pathlib

import pytest
import rich.console
import rich.prompt
from pytest_golden.plugin import GoldenTestFixture  # type: ignore[import-untyped]

from tests.conftest import HTTPPatcher, Runner, ConfigDataType  # for type hints


pytestmark = pytest.mark.skipif(
    rich.console.WINDOWS, reason="Output looks different on Windows"
)


@pytest.fixture(autouse=True)
def init_config(
    config_data: ConfigDataType,
    config_path: pathlib.Path,
    request: pytest.FixtureRequest,
) -> None:
    """Prepopulate the config with some share codes."""
    data = copy.deepcopy(config_data)

    if not request.node.get_closest_marker("empty_config"):
        data["shockers"] = {
            "test1": {"sharecode": "62142069AA1", "shocker_id": 1001},
            # unsorted to test sorting too
            "test3": {"sharecode": "62142069AA3", "shocker_id": 1003},
            "test2": {"sharecode": "62142069AA2", "shocker_id": 1002},
        }

    with config_path.open("w") as f:
        json.dump(data, f)


has_codes_parametrize = pytest.mark.parametrize(
    "has_codes", [True, pytest.param(False, marks=pytest.mark.empty_config)]
)


def test_using_saved_code(runner: Runner, http_patcher: HTTPPatcher) -> None:
    http_patcher.info(sharecode="62142069AA1")
    result = runner.run("info", "test1")
    assert result.exit_code == 0


@has_codes_parametrize
@pytest.mark.golden_test("golden/sharecodes/invalid.yml")
def test_invalid_code(
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
    runner: Runner,
    golden: GoldenTestFixture,
) -> None:
    result = runner.run("code", "list", "--info")
    assert result.output == golden.out["output_empty"]
    assert result.exit_code == 0


@pytest.mark.golden_test("golden/sharecodes/list.yml")
def test_list_info_not_authorized(
    runner: Runner,
    http_patcher: HTTPPatcher,
    golden: GoldenTestFixture,
) -> None:
    http_patcher.verify_credentials(False)
    result = runner.run("code", "list", "--info")
    assert result.output == golden.out["output_info_not_authorized"]
    assert result.exit_code == 1


@pytest.mark.golden_test("golden/sharecodes/list.yml")
def test_list_info(
    runner: Runner,
    http_patcher: HTTPPatcher,
    golden: GoldenTestFixture,
) -> None:
    http_patcher.verify_credentials(True)
    http_patcher.info(sharecode="62142069AA1")
    http_patcher.info_raw(status=http.HTTPStatus.NOT_FOUND)  # for ...AA2
    http_patcher.info(sharecode="62142069AA3")
    result = runner.run("code", "list", "--info")
    assert result.output == golden.out["output_info"]
    assert result.exit_code == 0


@has_codes_parametrize
@pytest.mark.golden_test("golden/sharecodes/list.yml")
def test_list(
    runner: Runner,
    golden: GoldenTestFixture,
    has_codes: bool,
) -> None:
    suffix = "" if has_codes else "_empty"
    result = runner.run("code", "list")
    assert result.output == golden.out[f"output{suffix}"]
    assert result.exit_code == 0


@has_codes_parametrize
@pytest.mark.golden_test("golden/sharecodes/add.yml")
@pytest.mark.parametrize("force", [True, False])
def test_add(
    runner: Runner,
    golden: GoldenTestFixture,
    http_patcher: HTTPPatcher,
    config_path: pathlib.Path,
    has_codes: bool,
    force: bool,
) -> None:
    new_code = "62142069AA4"
    force_arg = ["--force"] if force else []

    http_patcher.info(sharecode=new_code, shocker_id=1004)
    result = runner.run("code", "add", "test4", new_code, *force_arg)

    suffix = "_force" if force else ""
    if not has_codes:
        suffix += "_empty"

    assert result.output == golden.out[f"output{suffix}"]
    assert result.exit_code == 0

    with config_path.open("r") as f:
        data = json.load(f)

    if has_codes:
        assert data["shockers"] == {
            "test1": {"sharecode": "62142069AA1", "shocker_id": 1001},
            "test3": {"sharecode": "62142069AA3", "shocker_id": 1003},
            "test2": {"sharecode": "62142069AA2", "shocker_id": 1002},
            "test4": {"sharecode": new_code, "shocker_id": 1004},
        }
    else:
        assert data["shockers"] == {
            "test4": {"sharecode": new_code, "shocker_id": 1004}
        }


@pytest.mark.empty_config
@pytest.mark.golden_test("golden/sharecodes/add-not-found.yml")
def test_add_code_not_found(
    runner: Runner,
    golden: GoldenTestFixture,
    http_patcher: HTTPPatcher,
    config_path: pathlib.Path,
) -> None:
    http_patcher.info_raw(status=http.HTTPStatus.NOT_FOUND)
    result = runner.run("code", "add", "test4", "62142069AA4")
    assert result.output == golden.out["output"]
    assert result.exit_code == 1
    with config_path.open("r") as f:
        data = json.load(f)
    assert not data["shockers"]


@pytest.mark.parametrize("confirmed", [True, False, "--force"])
@pytest.mark.golden_test("golden/sharecodes/add.yml")
def test_add_overwrite(
    runner: Runner,
    config_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    golden: GoldenTestFixture,
    http_patcher: HTTPPatcher,
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

    new_code = "62142069AB1"
    force_arg = ["--force"] if confirmed == "--force" else []

    if confirmed:
        http_patcher.info(sharecode=new_code)
    result = runner.run("code", "add", "test1", new_code, *force_arg)
    assert result.output == golden.out[f"output_overwrite_{suffix}"]
    assert result.exit_code == (0 if confirmed else 1)

    with config_path.open("r") as f:
        data = json.load(f)
    if confirmed:
        assert data["shockers"] == {
            "test1": {"sharecode": new_code, "shocker_id": 1001},
            "test3": {"sharecode": "62142069AA3", "shocker_id": 1003},
            "test2": {"sharecode": "62142069AA2", "shocker_id": 1002},
        }
    else:
        assert data["shockers"] == {
            "test1": {"sharecode": "62142069AA1", "shocker_id": 1001},
            "test3": {"sharecode": "62142069AA3", "shocker_id": 1003},
            "test2": {"sharecode": "62142069AA2", "shocker_id": 1002},
        }


@pytest.mark.golden_test("golden/sharecodes/add.yml")
def test_add_invalid(
    runner: Runner,
    golden: GoldenTestFixture,
    config_path: pathlib.Path,
) -> None:
    result = runner.run("code", "add", "test1", "62142069ABX")
    assert result.output == golden.out["output_invalid"]
    assert result.exit_code == 1

    with config_path.open("r") as f:
        data = json.load(f)
    assert data["shockers"] == {
        "test1": {"sharecode": "62142069AA1", "shocker_id": 1001},
        "test3": {"sharecode": "62142069AA3", "shocker_id": 1003},
        "test2": {"sharecode": "62142069AA2", "shocker_id": 1002},
    }


@has_codes_parametrize
@pytest.mark.golden_test("golden/sharecodes/del.yml")
def test_del(
    runner: Runner,
    golden: GoldenTestFixture,
    config_path: pathlib.Path,
    has_codes: bool,
) -> None:
    suffix = "" if has_codes else "_empty"

    result = runner.run("code", "del", "test1")

    assert result.output == golden.out[f"output{suffix}"]
    assert result.exit_code == 0 if has_codes else 1

    with config_path.open("r") as f:
        data = json.load(f)

    if has_codes:
        assert data["shockers"] == {
            "test3": {"sharecode": "62142069AA3", "shocker_id": 1003},
            "test2": {"sharecode": "62142069AA2", "shocker_id": 1002},
        }
    else:
        assert data["shockers"] == {}


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
    result = runner.run("code", "rename", old_name, new_name, *force_arg)

    assert result.output == golden.out[f"output_{suffix}"]
    assert result.exit_code == (0 if successful else 1)

    with config_path.open("r") as f:
        data = json.load(f)

    if successful and overwrite:
        assert data["shockers"] == {
            "test3": {"sharecode": "62142069AA1", "shocker_id": 1001},
            "test2": {"sharecode": "62142069AA2", "shocker_id": 1002},
        }
    elif successful:
        assert data["shockers"] == {
            "test4": {"sharecode": "62142069AA1", "shocker_id": 1001},
            "test3": {"sharecode": "62142069AA3", "shocker_id": 1003},
            "test2": {"sharecode": "62142069AA2", "shocker_id": 1002},
        }
    else:
        assert data["shockers"] == {
            "test1": {"sharecode": "62142069AA1", "shocker_id": 1001},
            "test3": {"sharecode": "62142069AA3", "shocker_id": 1003},
            "test2": {"sharecode": "62142069AA2", "shocker_id": 1002},
        }
