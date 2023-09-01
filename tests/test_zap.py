from __future__ import annotations

import http

import pytest

from pishock import zap

from tests.conftest import FakeCredentials, PiShockPatcher  # for type hints


@pytest.fixture
def api(credentials: FakeCredentials) -> zap.API:
    return zap.API(username=credentials.USERNAME, api_key=credentials.API_KEY)


@pytest.fixture
def shocker(api: zap.API, credentials: FakeCredentials) -> zap.Shocker:
    return api.shocker(credentials.SHARECODE)


def test_api_repr(api: zap.API, credentials: FakeCredentials) -> None:
    assert repr(api) == f"API(username='{credentials.USERNAME}', api_key=...)"


def test_api_not_found(api: zap.API, patcher: PiShockPatcher) -> None:
    status = http.HTTPStatus.NOT_FOUND
    patcher.operate_raw(body=status.description, status=status)
    with pytest.raises(zap.HTTPError) as excinfo:
        api.request("apioperate", {})

    assert excinfo.value.body == status.description
    assert excinfo.value.status_code == status


@pytest.mark.parametrize("success_msg", zap.Shocker.SUCCESS_MESSAGES)
def test_vibrate(
    shocker: zap.Shocker, patcher: PiShockPatcher, success_msg: str
) -> None:
    patcher.operate(body=success_msg)
    shocker.vibrate(duration=1, intensity=2)


@pytest.mark.parametrize("success_msg", zap.Shocker.SUCCESS_MESSAGES)
def test_shock(shocker: zap.Shocker, patcher: PiShockPatcher, success_msg: str) -> None:
    patcher.operate(
        body=success_msg,
        op=zap.Operation.SHOCK.value,
    )
    shocker.shock(duration=1, intensity=2)


@pytest.mark.parametrize("success_msg", zap.Shocker.SUCCESS_MESSAGES)
def test_beep(shocker: zap.Shocker, patcher: PiShockPatcher, success_msg: str) -> None:
    patcher.operate(
        body=success_msg,
        op=zap.Operation.BEEP.value,
        intensity=None,
    )
    shocker.beep(duration=1)


def test_log_name_override(
    api: zap.API,
    patcher: PiShockPatcher,
    credentials: FakeCredentials,
) -> None:
    patcher.operate(name="test")
    shocker = api.shocker(credentials.SHARECODE, log_name="test")
    shocker.vibrate(duration=1, intensity=2)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("left-leg", "left-leg"),
        (None, FakeCredentials.SHARECODE),
    ],
)
def test_shocker_str(
    api: zap.API,
    patcher: PiShockPatcher,
    credentials: FakeCredentials,
    name: str | None,
    expected: str,
) -> None:
    shocker = api.shocker(credentials.SHARECODE, name=name)
    assert str(shocker) == expected


@pytest.mark.parametrize(
    "duration, expected",
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
    shocker: zap.Shocker, patcher: PiShockPatcher, duration: float, expected: int
) -> None:
    patcher.operate(duration=expected)
    shocker.vibrate(duration=duration, intensity=2)


@pytest.mark.parametrize("duration", [-1, 16, -1.0, 16.0, 1.6])
class TestInvalidDuration:
    def test_vibrate(self, shocker: zap.Shocker, duration: int) -> None:
        with pytest.raises(ValueError, match="duration needs to be between"):
            shocker.vibrate(duration=duration, intensity=2)

    def test_shock(self, shocker: zap.Shocker, duration: int) -> None:
        with pytest.raises(ValueError, match="duration needs to be between"):
            shocker.shock(duration=duration, intensity=2)

    def test_beep(self, shocker: zap.Shocker, duration: int) -> None:
        with pytest.raises(ValueError, match="duration needs to be between"):
            shocker.beep(duration=duration)


@pytest.mark.parametrize("intensity", [-1, 101])
class TestInvalidIntensity:
    def test_vibrate(self, shocker: zap.Shocker, intensity: int) -> None:
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.vibrate(duration=1, intensity=intensity)

    def test_shock(self, shocker: zap.Shocker, intensity: int) -> None:
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.shock(duration=1, intensity=intensity)


class TestOperationsNotAllowed:
    def test_vibrate(self, shocker: zap.Shocker, patcher: PiShockPatcher) -> None:
        patcher.operate(
            body=zap.VibrateNotAllowedError.TEXT,
            op=zap.Operation.VIBRATE.value,
        )
        with pytest.raises(zap.VibrateNotAllowedError):
            shocker.vibrate(duration=1, intensity=2)

    def test_shock(self, shocker: zap.Shocker, patcher: PiShockPatcher) -> None:
        patcher.operate(
            body=zap.ShockNotAllowedError.TEXT,
            op=zap.Operation.SHOCK.value,
        )
        with pytest.raises(zap.ShockNotAllowedError):
            shocker.shock(duration=1, intensity=2)

    def test_beep(self, shocker: zap.Shocker, patcher: PiShockPatcher) -> None:
        patcher.operate(
            body=zap.BeepNotAllowedError.TEXT,
            op=zap.Operation.BEEP.value,
            intensity=None,
        )
        with pytest.raises(zap.BeepNotAllowedError):
            shocker.beep(duration=1)


def test_beep_no_intensity(shocker: zap.Shocker) -> None:
    with pytest.raises(TypeError):
        shocker.beep(duration=1, intensity=2)  # type: ignore[call-arg]


def test_device_in_use(shocker: zap.Shocker, patcher: PiShockPatcher) -> None:
    patcher.operate(body=zap.DeviceInUseError.TEXT)
    with pytest.raises(zap.DeviceInUseError):
        shocker.vibrate(duration=1, intensity=2)


def test_unauthorized(patcher: PiShockPatcher, credentials: FakeCredentials) -> None:
    patcher.operate(
        body=zap.NotAuthorizedError.TEXT,
        apikey="wrong",
        code="wrong",
    )
    api = zap.API(username=credentials.USERNAME, api_key="wrong")
    shocker = api.shocker(sharecode="wrong")
    with pytest.raises(zap.NotAuthorizedError):
        shocker.vibrate(duration=1, intensity=2)


def test_unknown_share_code(api: zap.API, patcher: PiShockPatcher) -> None:
    patcher.operate(
        body=zap.ShareCodeNotFoundError.TEXT,
        code="wrong",
    )
    shocker = api.shocker(sharecode="wrong")
    with pytest.raises(zap.ShareCodeNotFoundError):
        shocker.vibrate(duration=1, intensity=2)


def test_unknown_error(
    shocker: zap.Shocker, api: zap.API, patcher: PiShockPatcher
) -> None:
    message = "Failed to frobnicate the zap."
    patcher.operate(body=message)
    with pytest.raises(zap.UnknownError, match=message):
        shocker.vibrate(duration=1, intensity=2)


@pytest.mark.parametrize("pause", [True, False])
def test_pause(shocker: zap.Shocker, patcher: PiShockPatcher, pause: bool) -> None:
    patcher.info()
    patcher.pause(pause)
    shocker.pause(pause)


def test_pause_unauthorized(shocker: zap.Shocker, patcher: PiShockPatcher) -> None:
    patcher.info()
    patcher.pause(True, body=zap.NotAuthorizedError.TEXT)
    with pytest.raises(zap.NotAuthorizedError):
        shocker.pause(True)


def test_pause_unknown_error(shocker: zap.Shocker, patcher: PiShockPatcher) -> None:
    message = "Shocker wanna go brrrrr."
    patcher.info()
    patcher.pause(True, body=message)
    with pytest.raises(zap.UnknownError, match=message):
        shocker.pause(True)


class TestInfo:
    def test_info(self, shocker: zap.Shocker, patcher: PiShockPatcher) -> None:
        patcher.info()
        info = shocker.info()
        assert info.name == "test shocker"
        assert info.client_id == 1000
        assert info.shocker_id == 1001
        assert not info.is_paused
        assert info.is_online
        assert info.max_intensity == 100
        assert info.max_duration == 15

    def test_invalid_body(self, shocker: zap.Shocker, patcher: PiShockPatcher) -> None:
        message = "Not JSON lol"
        patcher.info_raw(body=message, match=patcher.info_matchers())
        with pytest.raises(zap.UnknownError, match=message):
            shocker.info()

    @pytest.mark.parametrize(
        "status, exception",
        [
            (http.HTTPStatus.NOT_FOUND, zap.ShareCodeNotFoundError),
            (http.HTTPStatus.FORBIDDEN, zap.NotAuthorizedError),
            (http.HTTPStatus.IM_A_TEAPOT, zap.HTTPError),
        ],
    )
    def test_http_errors(
        self,
        shocker: zap.Shocker,
        patcher: PiShockPatcher,
        status: http.HTTPStatus,
        exception: type[zap.APIError],
    ) -> None:
        patcher.info_raw(status=status)
        with pytest.raises(exception):
            shocker.info()


class TestGetShockers:
    def test_get_shockers(self, api: zap.API, patcher: PiShockPatcher) -> None:
        patcher.get_shockers()
        shockers = api.get_shockers(client_id=1000)
        assert shockers == [
            zap.BasicShockerInfo(
                name="test shocker",
                client_id=1000,
                shocker_id=1001,
                is_paused=False,
            ),
            zap.BasicShockerInfo(
                name="test shocker 2",
                client_id=1000,
                shocker_id=1002,
                is_paused=True,
            ),
        ]

    def test_invalid_body(self, api: zap.API, patcher: PiShockPatcher) -> None:
        message = "Not JSON lol"
        patcher.get_shockers_raw(body=message, match=patcher.get_shockers_matchers())
        with pytest.raises(zap.UnknownError, match=message):
            api.get_shockers(client_id=1000)

    @pytest.mark.parametrize(
        "status, exception",
        [
            (http.HTTPStatus.FORBIDDEN, zap.NotAuthorizedError),
            (http.HTTPStatus.IM_A_TEAPOT, zap.HTTPError),
        ],
    )
    def test_http_errors(
        self,
        api: zap.API,
        patcher: PiShockPatcher,
        status: http.HTTPStatus,
        exception: type[zap.APIError],
    ) -> None:
        patcher.get_shockers_raw(status=status)
        with pytest.raises(exception):
            api.get_shockers(client_id=1000)


@pytest.mark.parametrize("valid", [True, False])
def test_verify_credentials(api: zap.API, patcher: PiShockPatcher, valid: bool) -> None:
    patcher.verify_credentials(valid)
    assert api.verify_credentials() == valid


def test_verify_credentials_error(api: zap.API, patcher: PiShockPatcher) -> None:
    patcher.verify_credentials_raw(
        status=http.HTTPStatus.IM_A_TEAPOT,
        match=patcher.verify_credentials_matchers(),
    )
    with pytest.raises(zap.HTTPError):
        api.verify_credentials()
