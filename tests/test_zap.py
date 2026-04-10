from __future__ import annotations

import http

import pytest
import pishock

from pishock.zap import httpapi, core, serialapi

from tests.conftest import (
    FakeCredentials,
    PiShockPatcher,
    HTTPPatcher,
)  # for type hints


def test_api_repr(
    pishock_api: httpapi.PiShockAPI, credentials: FakeCredentials
) -> None:
    assert (
        repr(pishock_api)
        == f"PiShockAPI(username='{credentials.USERNAME}', api_key=...)"
    )


def test_api_not_found(
    pishock_api: httpapi.PiShockAPI, http_patcher: HTTPPatcher
) -> None:
    status = http.HTTPStatus.NOT_FOUND
    http_patcher.account_raw(body=status.description, status=status)
    with pytest.raises(httpapi.HTTPError) as excinfo:
        pishock_api.get(endpoint="Account")

    assert excinfo.value.body == status.description
    assert excinfo.value.status_code == status


def test_vibrate(shocker: core.Shocker, patcher: PiShockPatcher) -> None:
    if not shocker.IS_SERIAL:
        patcher.info()
    patcher.operate(operation=httpapi.Operation.VIBRATE)
    shocker.vibrate(duration=1, intensity=2)


def test_shock(shocker: core.Shocker, patcher: PiShockPatcher) -> None:
    if not shocker.IS_SERIAL:
        patcher.info()
    patcher.operate(operation=httpapi.Operation.SHOCK)
    shocker.shock(duration=1, intensity=2)


def test_beep(shocker: core.Shocker, patcher: PiShockPatcher) -> None:
    if not shocker.IS_SERIAL:
        patcher.info()
    patcher.operate(operation=httpapi.Operation.BEEP, intensity=None)
    shocker.beep(duration=1)


@pytest.mark.parametrize("success_msg", httpapi.HTTPShocker._SUCCESS_MESSAGES)
def test_alternative_success_messages(
    api_shocker: httpapi.HTTPShocker, http_patcher: HTTPPatcher, success_msg: str
) -> None:
    http_patcher.info()
    http_patcher.operate(
        body=success_msg,
        operation=httpapi.Operation.VIBRATE,
    )
    api_shocker.vibrate(duration=1, intensity=2)


def test_log_name_override(
    pishock_api: httpapi.PiShockAPI,
    http_patcher: HTTPPatcher,
    credentials: FakeCredentials,
) -> None:
    http_patcher.info()
    http_patcher.operate(name="test")
    shocker = pishock_api.shocker(credentials.SHOCKER_ID, log_name="test")
    shocker.vibrate(duration=1, intensity=2)


@pytest.mark.parametrize("name", ["left-leg", None])
def test_shocker_str(
    pishock_api: httpapi.PiShockAPI,
    serial_api: serialapi.SerialAPI,
    patcher: PiShockPatcher,
    credentials: FakeCredentials,
    name: str | None,
) -> None:
    if isinstance(patcher, HTTPPatcher):
        patcher.account()
        if name is not None:
            patcher.shockers(
                [
                    {
                        "HubId": 0,
                        "ShockerId": credentials.SHOCKER_ID,
                        "Name": name,
                        "IsV3": True,
                        "CanBeep": True,
                        "CanVibrate": True,
                        "CanShock": True,
                        "CanPause": True,
                        "MaxDuration": 15,
                        "MaxIntensity": 100,
                    }
                ]
            )
        shocker = pishock_api.shocker(credentials.SHOCKER_ID, name=name)
        expected = name if name is not None else str(credentials.SHOCKER_ID)
    else:
        patcher.info()
        shocker = serial_api.shocker(shocker_id=credentials.SHOCKER_ID)
        expected = f"Serial shocker {credentials.SHOCKER_ID} (FAKE)"

    assert str(shocker) == expected

@pytest.mark.parametrize(
    "duration, api_duration",
    [
        (0, 16),
        (1, 1000),
        (15, 15),
        # floats
        (0.0, 16),
        (1.0, 1000),
        (15.0, 15000),
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
    if isinstance(patcher, HTTPPatcher):
        patcher.info()
        patcher.shockers()

    patcher.operate(
        duration=duration if shocker.IS_SERIAL else duration,
    )
    shocker.vibrate(duration=duration, intensity=2)


@pytest.mark.parametrize("duration", [-1, 16, -1.0, 16.0])
class TestInvalidDuration:
    def test_vibrate(self, shocker: core.Shocker, patcher: PiShockPatcher, duration: int) -> None:
        if shocker.IS_SERIAL and duration > 0:
            pytest.xfail("TODO: check if we have max duration via serial!")

        if isinstance(patcher, HTTPPatcher):
            patcher.info()
            patcher.shockers()
            patcher.operate(duration=duration)

        with pytest.raises(ValueError):
            shocker.vibrate(duration=duration, intensity=2)

    def test_shock(self, shocker: core.Shocker, patcher: PiShockPatcher, duration: int) -> None:
        if shocker.IS_SERIAL and duration > 0:
            pytest.xfail("TODO: check if we have max duration via serial!")

        if isinstance(patcher, HTTPPatcher):
            patcher.info()
            patcher.shockers()
            patcher.operate(duration=duration)

        with pytest.raises(ValueError):
            shocker.shock(duration=duration, intensity=2)

    def test_beep(self, shocker: core.Shocker, patcher: PiShockPatcher, duration: int) -> None:
        if shocker.IS_SERIAL and duration > 0:
            pytest.xfail("TODO: check if we have max duration via serial!")

        if isinstance(patcher, HTTPPatcher):
            patcher.info()
            patcher.shockers()
            patcher.operate(duration=duration)

        with pytest.raises(ValueError):
            shocker.beep(duration=duration)


@pytest.mark.parametrize("intensity", [-1, 101])
class TestInvalidIntensity:
    def test_vibrate(self, shocker: core.Shocker, patcher: PiShockPatcher, intensity: int) -> None:
        if isinstance(patcher, HTTPPatcher):
            patcher.info()
            patcher.shockers()
            patcher.operate(duration=1, intensity=intensity)

        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.vibrate(duration=1, intensity=intensity)

    def test_shock(self, shocker: core.Shocker, patcher: PiShockPatcher, intensity: int) -> None:
        if isinstance(patcher, HTTPPatcher):
            patcher.info()
            patcher.shockers()
            patcher.operate(duration=1, intensity=intensity)

        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.shock(duration=1, intensity=intensity)


class TestOperationsNotAllowed:
    def test_vibrate(
        self, api_shocker: httpapi.HTTPShocker, http_patcher: HTTPPatcher
    ) -> None:
        http_patcher.info()
        http_patcher.operate_raw(
            status=httpapi.UnsupportedOperationError.CODE,
        )
        with pytest.raises(httpapi.HTTPError):
            api_shocker.vibrate(duration=1, intensity=2)
            api_shocker.vibrate(duration=1, intensity=2)

    def test_shock(
        self, api_shocker: httpapi.HTTPShocker, http_patcher: HTTPPatcher
    ) -> None:
        http_patcher.info()
        http_patcher.operate_raw(
            status=httpapi.UnsupportedOperationError.CODE,
        )
        with pytest.raises(httpapi.HTTPError):
            api_shocker.shock(duration=1, intensity=2)

    def test_beep(
        self, api_shocker: httpapi.HTTPShocker, http_patcher: HTTPPatcher
    ) -> None:
        http_patcher.info()
        http_patcher.operate_raw(
            status=httpapi.UnsupportedOperationError.CODE,
        )
        with pytest.raises(httpapi.HTTPError):
            api_shocker.beep(duration=1)


def test_beep_no_intensity(shocker: core.Shocker) -> None:
    with pytest.raises(TypeError):
        shocker.beep(duration=1, intensity=2)  # type: ignore[call-arg]

def test_unauthorized(http_patcher: HTTPPatcher, credentials: FakeCredentials) -> None:
    http_patcher.account_raw(
        headers={
            "User-Agent": f"{httpapi.NAME}/{pishock.__version__}",
            'X-PiShock-Api-Key': 'wrong',
            'X-PiShock-UserId': 'PISHOCK-USERNAME',
            'Content-Type': 'application/json',
        },
        status=http.HTTPStatus.UNAUTHORIZED,
    )
    http_patcher.operate(
        body=httpapi.NotAuthorizedError.TEXT,
        apikey="wrong",
        code="wrong",
    )
    with pytest.raises(httpapi.HTTPError, match="Unauthorized for url"):
        httpapi.PiShockAPI(username=credentials.USERNAME, api_key="wrong")

class TestInfo:
    def test_info(
        self,
        shocker: core.Shocker,
        patcher: PiShockPatcher,
        credentials: FakeCredentials,
    ) -> None:
        patcher.info(
            shocker_id=credentials.SHOCKER_ID,  # FIXME remove after changing default
            client_id=FakeCredentials.CLIENT_ID,  # FIXME remove after changing default
        )
        info = shocker.info()

        if shocker.IS_SERIAL:
            expected_name = f"Serial shocker {credentials.SHOCKER_ID} (FAKE)"
        else:
            expected_name = "test shocker"

        assert info.name == expected_name
        if shocker.IS_SERIAL:
            assert info.client_id == credentials.CLIENT_ID
        assert info.shocker_id == credentials.SHOCKER_ID
        assert not info.is_paused
        if isinstance(info, core.ApiV3ShockerInfo):  # not serial
            assert info.max_intensity == 100
            assert info.max_duration == 15

    def test_invalid_body(
        self, api_shocker: httpapi.HTTPShocker, http_patcher: HTTPPatcher
    ) -> None:
        message = "Not JSON lol"
        http_patcher.info_raw(body=message, match=http_patcher.info_matchers())
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
        http_patcher: HTTPPatcher,
        status: http.HTTPStatus,
        exception: type[httpapi.APIError],
    ) -> None:
        http_patcher.info_raw(status=status)
        with pytest.raises(exception):
            api_shocker.info()


class TestGetShockers:
    def test_get_shockers(
        self, pishock_api: httpapi.PiShockAPI, http_patcher: HTTPPatcher
    ) -> None:
        http_patcher.info()
        http_patcher.shockers()
        shockers = pishock_api.get_shockers()
        assert shockers == [
            core.ApiV3ShockerInfo(
                name="test shocker",
                client_id=1000,
                shocker_id=1001,
                is_paused=False,
                hub_id=1000,
                isV3=True,
                can_beep=True,
                can_vibrate=True,
                can_shock=True,
                can_pause=False,
                max_duration=15,
                max_intensity=100,
            ),
            core.ApiV3ShockerInfo(
                name="test shocker 2",
                client_id=1000,
                shocker_id=1002,
                is_paused=False,
                hub_id=1000,
                isV3=True,
                can_beep=True,
                can_vibrate=True,
                can_shock=True,
                can_pause=False,
                max_duration=15,
                max_intensity=100,
            ),
        ]

    def test_invalid_body(
        self, pishock_api: httpapi.PiShockAPI, http_patcher: HTTPPatcher
    ) -> None:
        message = "Not JSON lol"
        http_patcher.shockers_raw(body=message)
        with pytest.raises(httpapi.UnknownError, match=message):
            pishock_api.get_shockers()

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
        http_patcher: HTTPPatcher,
        status: http.HTTPStatus,
        exception: type[httpapi.APIError],
    ) -> None:
        http_patcher.shockers_raw(status=status)
        with pytest.raises(exception):
            pishock_api.get_shockers()


@pytest.mark.parametrize("valid", [True, False])
def test_verify_credentials(
    pishock_api: httpapi.PiShockAPI, http_patcher: HTTPPatcher, valid: bool
) -> None:
    http_patcher.account_id(621)
    assert pishock_api.verify_credentials()


def test_verify_credentials_error(
    pishock_api: httpapi.PiShockAPI, http_patcher: HTTPPatcher
) -> None:
    http_patcher.account_id_raw(
        621,
        status=http.HTTPStatus.INTERNAL_SERVER_ERROR,
        match=http_patcher.account_id_matchers(),
    )
    with pytest.raises(httpapi.HTTPError):
        pishock_api.verify_credentials()
