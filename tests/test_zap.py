import http

import pytest
from responses import RequestsMock, matchers

from pishock import zap


class FakeCredentials:
    USERNAME = "PISHOCK-USERNAME"
    APIKEY = "PISHOCK-APIKEY"
    SHARECODE = "PISHOCK-SHARECODE"


class APIURLs:
    BASE = "https://do.pishock.com/api"
    OPERATE = f"{BASE}/apioperate"
    PAUSE = f"{BASE}/PauseShocker"
    SHOCKER_INFO = f"{BASE}/GetShockerInfo"
    GET_SHOCKERS = f"{BASE}/GetShockers"


def get_operate_matchers(**kwargs):
    template = {
        "Username": FakeCredentials.USERNAME,
        "Apikey": FakeCredentials.APIKEY,
        "Code": FakeCredentials.SHARECODE,
        "Name": zap.NAME,
        "Op": zap._Operation.VIBRATE.value,
        "Duration": 1,
        "Intensity": 2,
    }
    for k, v in kwargs.items():
        k = k.capitalize()
        if v is None:
            del template[k]
        else:
            template[k] = v
    return [
        matchers.json_params_matcher(template),
        matchers.header_matcher({"User-Agent": f"{zap.NAME}/{zap.__version__}"}),
    ]


@pytest.fixture
def api() -> zap.API:
    return zap.API(username=FakeCredentials.USERNAME, apikey=FakeCredentials.APIKEY)


@pytest.fixture
def shocker(api: zap.API) -> zap.Shocker:
    return api.shocker(FakeCredentials.SHARECODE)


def test_api_repr(api: zap.API):
    assert repr(api) == f"API(username='{FakeCredentials.USERNAME}', apikey=...)"


def test_api_not_found(api: zap.API, responses: RequestsMock):
    status = http.HTTPStatus.NOT_FOUND
    responses.add(
        responses.POST,
        APIURLs.OPERATE,
        body=status.description,
        status=status,
    )
    with pytest.raises(zap.HTTPError) as excinfo:
        api.request("apioperate", {})

    assert excinfo.value.body == status.description
    assert excinfo.value.status_code == status


@pytest.mark.parametrize("success_msg", zap.Shocker.SUCCESS_MESSAGES)
def test_vibrate(shocker: zap.Shocker, responses: RequestsMock, success_msg: str):
    responses.post(
        APIURLs.OPERATE,
        body=success_msg,
        match=get_operate_matchers(),
    )
    shocker.vibrate(duration=1, intensity=2)


@pytest.mark.parametrize("success_msg", zap.Shocker.SUCCESS_MESSAGES)
def test_shock(shocker: zap.Shocker, responses: RequestsMock, success_msg: str):
    responses.post(
        APIURLs.OPERATE,
        body=success_msg,
        match=get_operate_matchers(op=zap._Operation.SHOCK.value),
    )
    shocker.shock(duration=1, intensity=2)


@pytest.mark.parametrize("success_msg", zap.Shocker.SUCCESS_MESSAGES)
def test_beep(shocker: zap.Shocker, responses: RequestsMock, success_msg: str):
    responses.post(
        APIURLs.OPERATE,
        body=success_msg,
        match=get_operate_matchers(op=zap._Operation.BEEP.value, intensity=None),
    )
    shocker.beep(duration=1)


def test_name_override(api: zap.API, responses: RequestsMock):
    responses.post(
        APIURLs.OPERATE,
        body=zap.Shocker.SUCCESS_MESSAGES[0],
        match=get_operate_matchers(name="test"),
    )
    shocker = api.shocker(FakeCredentials.SHARECODE, name="test")
    shocker.vibrate(duration=1, intensity=2)


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
    shocker: zap.Shocker, responses: RequestsMock, duration: float, expected: int
):
    responses.post(
        APIURLs.OPERATE,
        body=zap.Shocker.SUCCESS_MESSAGES[0],
        match=get_operate_matchers(duration=expected),
    )
    shocker.vibrate(duration=duration, intensity=2)


@pytest.mark.parametrize("duration", [-1, 16, -1.0, 16.0, 1.6])
class TestInvalidDuration:
    def test_vibrate(self, shocker: zap.Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between"):
            shocker.vibrate(duration=duration, intensity=2)

    def test_shock(self, shocker: zap.Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between"):
            shocker.shock(duration=duration, intensity=2)

    def test_beep(self, shocker: zap.Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between"):
            shocker.beep(duration=duration)


@pytest.mark.parametrize("intensity", [-1, 101])
class TestInvalidIntensity:
    def test_vibrate(self, shocker: zap.Shocker, intensity: int):
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.vibrate(duration=1, intensity=intensity)

    def test_shock(self, shocker: zap.Shocker, intensity: int):
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.shock(duration=1, intensity=intensity)


class TestOperationsNotAllowed:
    def test_vibrate(self, shocker: zap.Shocker, responses: RequestsMock):
        responses.post(
            APIURLs.OPERATE,
            body=zap.VibrateNotAllowedError.TEXT,
            match=get_operate_matchers(op=zap._Operation.VIBRATE.value),
        )
        with pytest.raises(zap.VibrateNotAllowedError):
            shocker.vibrate(duration=1, intensity=2)

    def test_shock(self, shocker: zap.Shocker, responses: RequestsMock):
        responses.post(
            APIURLs.OPERATE,
            body=zap.ShockNotAllowedError.TEXT,
            match=get_operate_matchers(op=zap._Operation.SHOCK.value),
        )
        with pytest.raises(zap.ShockNotAllowedError):
            shocker.shock(duration=1, intensity=2)

    def test_beep(self, shocker: zap.Shocker, responses: RequestsMock):
        responses.post(
            APIURLs.OPERATE,
            body=zap.BeepNotAllowedError.TEXT,
            match=get_operate_matchers(op=zap._Operation.BEEP.value, intensity=None),
        )
        with pytest.raises(zap.BeepNotAllowedError):
            shocker.beep(duration=1)


def test_beep_no_intensity(shocker: zap.Shocker):
    with pytest.raises(TypeError):
        shocker.beep(duration=1, intensity=2)


def test_device_in_use(shocker: zap.Shocker, responses: RequestsMock):
    responses.post(
        APIURLs.OPERATE,
        body=zap.DeviceInUseError.TEXT,
        match=get_operate_matchers(),
    )
    with pytest.raises(zap.DeviceInUseError):
        shocker.vibrate(duration=1, intensity=2)


def test_unauthorized(responses: RequestsMock):
    responses.post(
        APIURLs.OPERATE,
        body=zap.NotAuthorizedError.TEXT,
        match=get_operate_matchers(apikey="wrong", code="wrong"),
    )
    api = zap.API(username=FakeCredentials.USERNAME, apikey="wrong")
    shocker = api.shocker(sharecode="wrong")
    with pytest.raises(zap.NotAuthorizedError):
        shocker.vibrate(duration=1, intensity=2)


def test_unknown_share_code(api: zap.API, responses: RequestsMock):
    responses.post(
        APIURLs.OPERATE,
        body=zap.ShareCodeNotFoundError.TEXT,
        match=get_operate_matchers(code="wrong"),
    )
    shocker = api.shocker(sharecode="wrong")
    with pytest.raises(zap.ShareCodeNotFoundError):
        shocker.vibrate(duration=1, intensity=2)


def test_unknown_error(shocker: zap.Shocker, api: zap.API, responses: RequestsMock):
    message = "Failed to frobnicate the zap."
    responses.post(
        APIURLs.OPERATE,
        body=message,
        match=get_operate_matchers(),
    )
    with pytest.raises(zap.UnknownError, match=message):
        shocker.vibrate(duration=1, intensity=2)


@pytest.fixture
def info_setup(responses: RequestsMock) -> None:
    responses.post(
        APIURLs.SHOCKER_INFO,
        json={
            "name": "test shocker",
            "clientId": 1000,
            "id": 1001,
            "paused": False,
            "online": True,
            "maxIntensity": 100,
            "maxDuration": 15,
        },
        match=[
            matchers.json_params_matcher(
                {
                    "Username": FakeCredentials.USERNAME,
                    "Apikey": FakeCredentials.APIKEY,
                    "Code": FakeCredentials.SHARECODE,
                }
            )
        ],
    )


@pytest.mark.parametrize("pause", [True, False])
def test_pause(
    shocker: zap.Shocker,
    responses: RequestsMock,
    info_setup: None,
    pause: bool,
):
    responses.post(
        APIURLs.PAUSE,
        body=zap.Shocker.SUCCESS_MESSAGE_PAUSE,
        match=[
            matchers.json_params_matcher(
                {
                    "Username": FakeCredentials.USERNAME,
                    "Apikey": FakeCredentials.APIKEY,
                    "ShockerId": 1001,
                    "Pause": pause,
                }
            )
        ],
    )
    shocker.pause(pause)


def test_pause_unauthorized(
    shocker: zap.Shocker,
    responses: RequestsMock,
    info_setup: None,
):
    responses.post(
        APIURLs.PAUSE,
        body=zap.NotAuthorizedError.TEXT,
        match=[
            matchers.json_params_matcher(
                {
                    "Username": FakeCredentials.USERNAME,
                    "Apikey": FakeCredentials.APIKEY,
                    "ShockerId": 1001,
                    "Pause": True,
                }
            )
        ],
    )
    with pytest.raises(zap.NotAuthorizedError):
        shocker.pause(True)


def test_pause_unknown_error(
    shocker: zap.Shocker,
    responses: RequestsMock,
    info_setup: None,
):
    message = "Shocker wanna go brrrrr."
    responses.post(
        APIURLs.PAUSE,
        body=message,
        match=[
            matchers.json_params_matcher(
                {
                    "Username": FakeCredentials.USERNAME,
                    "Apikey": FakeCredentials.APIKEY,
                    "ShockerId": 1001,
                    "Pause": True,
                }
            )
        ],
    )
    with pytest.raises(zap.UnknownError, match=message):
        shocker.pause(True)


def test_info(shocker: zap.Shocker, info_setup: None):
    info = shocker.info()
    assert info.name == "test shocker"
    assert info.client_id == 1000
    assert info.shocker_id == 1001
    assert not info.is_paused
    assert info.is_online
    assert info.max_intensity == 100
    assert info.max_duration == 15


def test_info_invalid(shocker: zap.Shocker, responses: RequestsMock):
    message = "Not JSON lol"
    responses.post(
        APIURLs.SHOCKER_INFO,
        body=message,
        match=[
            matchers.json_params_matcher(
                {
                    "Username": FakeCredentials.USERNAME,
                    "Apikey": FakeCredentials.APIKEY,
                    "Code": FakeCredentials.SHARECODE,
                }
            )
        ],
    )
    with pytest.raises(zap.UnknownError, match=message):
        shocker.info()


def test_get_shockers(api: zap.API, responses: RequestsMock):
    responses.post(
        APIURLs.GET_SHOCKERS,
        json=[
            {"name": "test shocker", "id": 1001, "paused": False},
            {"name": "test shocker 2", "id": 1002, "paused": True},
        ],
        match=[
            matchers.json_params_matcher(
                {
                    "Username": FakeCredentials.USERNAME,
                    "Apikey": FakeCredentials.APIKEY,
                    "ClientId": 1000,
                }
            )
        ],
    )
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


def test_get_shockers_invalid(api: zap.API, responses: RequestsMock):
    message = "Not JSON lol"
    responses.post(
        APIURLs.GET_SHOCKERS,
        body=message,
        match=[
            matchers.json_params_matcher(
                {
                    "Username": FakeCredentials.USERNAME,
                    "Apikey": FakeCredentials.APIKEY,
                    "ClientId": 1000,
                }
            )
        ],
    )
    with pytest.raises(zap.UnknownError, match=message):
        api.get_shockers(client_id=1000)
