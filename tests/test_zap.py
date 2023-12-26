from __future__ import annotations

import http
from typing import cast

import pytest

from pishock.zap import serialapi, httpapi, core

from tests.conftest import FakeCredentials, PiShockPatcher  # for type hints


@pytest.fixture(params=["api_shocker", "serial_shocker"])
def shocker(request: pytest.FixtureRequest) -> core.Shocker:
    return cast(core.Shocker, request.getfixturevalue(request.param))


@pytest.fixture
def serial_shocker(
    serial_api: serialapi.SerialAPI, credentials: FakeCredentials
) -> serialapi.SerialShocker:
    return serial_api.shocker(shocker_id=credentials.SHOCKER_ID)


@pytest.fixture
def api_shocker(
    pishock_api: httpapi.PiShockAPI, credentials: FakeCredentials
) -> httpapi.HTTPShocker:
    return pishock_api.shocker(credentials.SHARECODE)


def test_api_repr(
    pishock_api: httpapi.PiShockAPI, credentials: FakeCredentials
) -> None:
    assert (
        repr(pishock_api)
        == f"PiShockAPI(username='{credentials.USERNAME}', api_key=...)"
    )


def test_api_not_found(
    pishock_api: httpapi.PiShockAPI, patcher: PiShockPatcher
) -> None:
    status = http.HTTPStatus.NOT_FOUND
    patcher.operate_raw(body=status.description, status=status)
    with pytest.raises(httpapi.HTTPError) as excinfo:
        pishock_api.request("apioperate", {})

    assert excinfo.value.body == status.description
    assert excinfo.value.status_code == status


@pytest.mark.parametrize("success_msg", httpapi.HTTPShocker._SUCCESS_MESSAGES)
def test_vibrate(
    shocker: core.Shocker, patcher: PiShockPatcher, success_msg: str
) -> None:
    patcher.operate(
        body=success_msg,
        operation=httpapi.Operation.VIBRATE,
        is_serial=shocker.IS_SERIAL,
    )
    shocker.vibrate(duration=1, intensity=2)


@pytest.mark.parametrize("success_msg", httpapi.HTTPShocker._SUCCESS_MESSAGES)
def test_shock(
    shocker: core.Shocker, patcher: PiShockPatcher, success_msg: str
) -> None:
    patcher.operate(
        body=success_msg,
        operation=httpapi.Operation.SHOCK,
        is_serial=shocker.IS_SERIAL,
    )
    shocker.shock(duration=1, intensity=2)


@pytest.mark.parametrize("success_msg", httpapi.HTTPShocker._SUCCESS_MESSAGES)
def test_beep(shocker: core.Shocker, patcher: PiShockPatcher, success_msg: str) -> None:
    patcher.operate(
        body=success_msg,
        operation=httpapi.Operation.BEEP,
        intensity=None,
        is_serial=shocker.IS_SERIAL,
    )
    shocker.beep(duration=1)


def test_log_name_override(
    pishock_api: httpapi.PiShockAPI,
    patcher: PiShockPatcher,
    credentials: FakeCredentials,
) -> None:
    patcher.operate(name="test")
    shocker = pishock_api.shocker(credentials.SHARECODE, log_name="test")
    shocker.vibrate(duration=1, intensity=2)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("left-leg", "left-leg"),
        (None, FakeCredentials.SHARECODE),
    ],
)
def test_shocker_str(
    pishock_api: httpapi.PiShockAPI,
    patcher: PiShockPatcher,
    credentials: FakeCredentials,
    name: str | None,
    expected: str,
) -> None:
    shocker = pishock_api.shocker(credentials.SHARECODE, name=name)
    assert str(shocker) == expected


@pytest.mark.parametrize(
    "duration, api_duration",
    [
        (0, 0),
        (1, 1),
        (15, 15),
        # floats
        (0.0, 0),
        (1.0, 1),
        (15.0, 15),
        (0.1, 100),
        (0.3, 300),
        (1.1, 1100),
        (1.15, 1150),  # rounded down by API
        (1.51, 1510),  # rounded down by API
    ],
)
def test_valid_durations(
    shocker: core.Shocker, patcher: PiShockPatcher, duration: float, api_duration: int
) -> None:
    patcher.operate(
        duration=duration if shocker.IS_SERIAL else api_duration,
        is_serial=shocker.IS_SERIAL,
    )
    shocker.vibrate(duration=duration, intensity=2)


@pytest.mark.parametrize("duration", [-1, 16, -1.0, 16.0, 1.6])
class TestInvalidDuration:
    def test_vibrate(self, shocker: core.Shocker, duration: int) -> None:
        if shocker.IS_SERIAL and duration > 0:
            pytest.xfail("TODO: check if we have max duration via serial!")

        with pytest.raises(ValueError, match="duration needs to be between"):
            shocker.vibrate(duration=duration, intensity=2)

    def test_shock(self, shocker: core.Shocker, duration: int) -> None:
        if shocker.IS_SERIAL and duration > 0:
            pytest.xfail("TODO: check if we have max duration via serial!")

        with pytest.raises(ValueError, match="duration needs to be between"):
            shocker.shock(duration=duration, intensity=2)

    def test_beep(self, shocker: core.Shocker, duration: int) -> None:
        if shocker.IS_SERIAL and duration > 0:
            pytest.xfail("TODO: check if we have max duration via serial!")

        with pytest.raises(ValueError, match="duration needs to be between"):
            shocker.beep(duration=duration)


@pytest.mark.parametrize("intensity", [-1, 101])
class TestInvalidIntensity:
    def test_vibrate(self, shocker: core.Shocker, intensity: int) -> None:
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.vibrate(duration=1, intensity=intensity)

    def test_shock(self, shocker: core.Shocker, intensity: int) -> None:
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.shock(duration=1, intensity=intensity)


class TestOperationsNotAllowed:
    def test_vibrate(
        self, api_shocker: httpapi.HTTPShocker, patcher: PiShockPatcher
    ) -> None:
        patcher.operate(
            body=httpapi.VibrateNotAllowedError.TEXT,
            operation=httpapi.Operation.VIBRATE,
        )
        with pytest.raises(httpapi.VibrateNotAllowedError):
            api_shocker.vibrate(duration=1, intensity=2)

    def test_shock(
        self, api_shocker: httpapi.HTTPShocker, patcher: PiShockPatcher
    ) -> None:
        patcher.operate(
            body=httpapi.ShockNotAllowedError.TEXT,
            operation=httpapi.Operation.SHOCK,
        )
        with pytest.raises(httpapi.ShockNotAllowedError):
            api_shocker.shock(duration=1, intensity=2)

    def test_beep(
        self, api_shocker: httpapi.HTTPShocker, patcher: PiShockPatcher
    ) -> None:
        patcher.operate(
            body=httpapi.BeepNotAllowedError.TEXT,
            operation=httpapi.Operation.BEEP,
            intensity=None,
        )
        with pytest.raises(httpapi.BeepNotAllowedError):
            api_shocker.beep(duration=1)


def test_beep_no_intensity(shocker: core.Shocker) -> None:
    with pytest.raises(TypeError):
        shocker.beep(duration=1, intensity=2)  # type: ignore[call-arg]


def test_device_in_use(
    api_shocker: httpapi.HTTPShocker, patcher: PiShockPatcher
) -> None:
    patcher.operate(body=httpapi.DeviceInUseError.TEXT)
    with pytest.raises(httpapi.DeviceInUseError):
        api_shocker.vibrate(duration=1, intensity=2)


def test_unauthorized(patcher: PiShockPatcher, credentials: FakeCredentials) -> None:
    patcher.operate(
        body=httpapi.NotAuthorizedError.TEXT,
        apikey="wrong",
        code="wrong",
    )
    api = httpapi.PiShockAPI(username=credentials.USERNAME, api_key="wrong")
    shocker = api.shocker(sharecode="wrong")
    with pytest.raises(httpapi.NotAuthorizedError):
        shocker.vibrate(duration=1, intensity=2)


def test_unknown_share_code(
    pishock_api: httpapi.PiShockAPI, patcher: PiShockPatcher
) -> None:
    patcher.operate(
        body=httpapi.ShareCodeNotFoundError.TEXT,
        code="wrong",
    )
    shocker = pishock_api.shocker(sharecode="wrong")
    with pytest.raises(httpapi.ShareCodeNotFoundError):
        shocker.vibrate(duration=1, intensity=2)


def test_unknown_error(
    api_shocker: httpapi.HTTPShocker,
    pishock_api: httpapi.PiShockAPI,
    patcher: PiShockPatcher,
) -> None:
    message = "Failed to frobnicate the zap."
    patcher.operate(body=message)
    with pytest.raises(httpapi.UnknownError, match=message):
        api_shocker.vibrate(duration=1, intensity=2)


@pytest.mark.parametrize("pause", [True, False])
def test_pause(
    api_shocker: httpapi.HTTPShocker, patcher: PiShockPatcher, pause: bool
) -> None:
    patcher.info()
    patcher.pause(pause)
    api_shocker.pause(pause)


def test_pause_unauthorized(
    api_shocker: httpapi.HTTPShocker, patcher: PiShockPatcher
) -> None:
    patcher.info()
    patcher.pause(True, body=httpapi.NotAuthorizedError.TEXT)
    with pytest.raises(httpapi.NotAuthorizedError):
        api_shocker.pause(True)


def test_pause_unknown_error(
    api_shocker: httpapi.HTTPShocker, patcher: PiShockPatcher
) -> None:
    message = "Shocker wanna go brrrrr."
    patcher.info()
    patcher.pause(True, body=message)
    with pytest.raises(httpapi.UnknownError, match=message):
        api_shocker.pause(True)


class TestInfo:
    def test_info(
        self,
        shocker: core.Shocker,
        patcher: PiShockPatcher,
        credentials: FakeCredentials,
    ) -> None:
        patcher.info(
            is_serial=shocker.IS_SERIAL,
            shocker_id=credentials.SHOCKER_ID,  # FIXME remove after changing default
            client_id=FakeCredentials.CLIENT_ID,  # FIXME remove after changing default
        )
        info = shocker.info()

        expected_name = "Serial shocker (FAKE)" if shocker.IS_SERIAL else "test shocker"
        assert info.name == expected_name
        assert info.client_id == credentials.CLIENT_ID
        assert info.shocker_id == credentials.SHOCKER_ID
        assert not info.is_paused
        if isinstance(info, httpapi.DetailedShockerInfo):  # not serial
            assert info.max_intensity == 100
            assert info.max_duration == 15

    def test_invalid_body(self, api_shocker: httpapi.HTTPShocker, patcher: PiShockPatcher) -> None:
        message = "Not JSON lol"
        patcher.info_raw(body=message, match=patcher.info_matchers())
        with pytest.raises(httpapi.UnknownError, match=message):
            api_shocker.info()

    @pytest.mark.parametrize(
        "status, exception",
        [
            (http.HTTPStatus.NOT_FOUND, httpapi.ShareCodeNotFoundError),
            (http.HTTPStatus.FORBIDDEN, httpapi.NotAuthorizedError),
            (http.HTTPStatus.INTERNAL_SERVER_ERROR, httpapi.HTTPError),
        ],
    )
    def test_http_errors(
        self,
        api_shocker: httpapi.HTTPShocker,
        patcher: PiShockPatcher,
        status: http.HTTPStatus,
        exception: type[httpapi.APIError],
    ) -> None:
        patcher.info_raw(status=status)
        with pytest.raises(exception):
            api_shocker.info()


class TestGetShockers:
    def test_get_shockers(
        self, pishock_api: httpapi.PiShockAPI, patcher: PiShockPatcher
    ) -> None:
        patcher.get_shockers()
        shockers = pishock_api.get_shockers(client_id=1000)
        assert shockers == [
            core.BasicShockerInfo(
                name="test shocker",
                client_id=1000,
                shocker_id=1001,
                is_paused=False,
            ),
            core.BasicShockerInfo(
                name="test shocker 2",
                client_id=1000,
                shocker_id=1002,
                is_paused=True,
            ),
        ]

    def test_invalid_body(
        self, pishock_api: httpapi.PiShockAPI, patcher: PiShockPatcher
    ) -> None:
        message = "Not JSON lol"
        patcher.get_shockers_raw(body=message, match=patcher.get_shockers_matchers())
        with pytest.raises(httpapi.UnknownError, match=message):
            pishock_api.get_shockers(client_id=1000)

    @pytest.mark.parametrize(
        "status, exception",
        [
            (http.HTTPStatus.FORBIDDEN, httpapi.NotAuthorizedError),
            (http.HTTPStatus.INTERNAL_SERVER_ERROR, httpapi.HTTPError),
        ],
    )
    def test_http_errors(
        self,
        pishock_api: httpapi.PiShockAPI,
        patcher: PiShockPatcher,
        status: http.HTTPStatus,
        exception: type[httpapi.APIError],
    ) -> None:
        patcher.get_shockers_raw(status=status)
        with pytest.raises(exception):
            pishock_api.get_shockers(client_id=1000)


@pytest.mark.parametrize("valid", [True, False])
def test_verify_credentials(
    pishock_api: httpapi.PiShockAPI, patcher: PiShockPatcher, valid: bool
) -> None:
    patcher.verify_credentials(valid)
    assert pishock_api.verify_credentials() == valid


def test_verify_credentials_error(
    pishock_api: httpapi.PiShockAPI, patcher: PiShockPatcher
) -> None:
    patcher.verify_credentials_raw(
        status=http.HTTPStatus.INTERNAL_SERVER_ERROR,
        match=patcher.verify_credentials_matchers(),
    )
    with pytest.raises(httpapi.HTTPError):
        pishock_api.verify_credentials()
