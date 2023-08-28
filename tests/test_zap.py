import os
import dataclasses
import http

import pytest
from responses import RequestsMock, matchers

from pishock import zap


class APIURLs:
    BASE = "https://do.pishock.com/api"
    OPERATE = f"{BASE}/apioperate"
    PAUSE = f"{BASE}/PauseShocker"
    SHOCKER_INFO = f"{BASE}/GetShockerInfo"
    GET_SHOCKERS = f"{BASE}/GetShockers"


def get_operate_matchers(**kwargs):
    template = {
        "Username": "Zerario",
        "Apikey": "PISHOCK-APIKEY",
        "Code": "PISHOCK-SHARECODE",
        "Name": "random",
        "Op": zap.Operation.VIBRATE.value,
        "Duration": 1,
        "Intensity": 2,
    }
    for k, v in kwargs.items():
        k = k.capitalize()
        if v is None:
            del template[k]
        else:
            template[k] = v
    return [matchers.json_params_matcher(template)]


@dataclasses.dataclass
class Credentials:
    username: str
    apikey: str
    sharecode: str


@pytest.fixture
def credentials() -> Credentials:
    """Get credentials to run tests.

    By default, uses the same fake credentials that tests have in theis stored
    responses in tests/cassettes.

    To re-generate the cassetes, provide valid credentials in your environment:

    export PISHOCK_USERNAME=...
    export PISHOCK_APIKEY=...
    export PISHOCK_SHARECODE=...

    And then run:

    tox -e py311 -- --FIXME
    """
    return Credentials(
        username=os.environ.get("PISHOCK_USERNAME", "Zerario"),
        apikey=os.environ.get("PISHOCK_APIKEY", "PISHOCK-APIKEY"),
        sharecode=os.environ.get("PISHOCK_SHARECODE", "PISHOCK-SHARECODE"),
    )


@pytest.fixture
def api(credentials: Credentials) -> zap.API:
    return zap.API(username=credentials.username, apikey=credentials.apikey)


@pytest.fixture
def shocker(api: zap.API, credentials: Credentials) -> zap.Shocker:
    s = api.shocker(credentials.sharecode)
    # info = s.info()
    # if info.is_paused:
    #    s.pause(False)
    return s
    # s.pause(info.is_paused)


def test_api_repr(api: zap.API, credentials: Credentials):
    assert repr(api) == f"API(username='{credentials.username}', apikey=...)"


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
        match=get_operate_matchers(op=zap.Operation.SHOCK.value),
    )
    shocker.shock(duration=1, intensity=2)


@pytest.mark.parametrize("success_msg", zap.Shocker.SUCCESS_MESSAGES)
def test_beep(shocker: zap.Shocker, responses: RequestsMock, success_msg: str):
    responses.post(
        APIURLs.OPERATE,
        body=success_msg,
        match=get_operate_matchers(op=zap.Operation.BEEP.value, intensity=None),
    )
    shocker.beep(duration=1)


@pytest.mark.parametrize("duration", [-1, 16])
class TestInvalidDuration:
    def test_vibrate(self, shocker: zap.Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between 0 and 15"):
            shocker.vibrate(duration=duration, intensity=2)

    def test_shock(self, shocker: zap.Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between 0 and 15"):
            shocker.shock(duration=duration, intensity=2)

    def test_beep(self, shocker: zap.Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between 0 and 15"):
            shocker.beep(duration=duration)


@pytest.mark.parametrize("intensity", [-1, 101])
class TestInvalidIntensity:
    def test_vibrate(self, shocker: zap.Shocker, intensity: int):
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.vibrate(duration=1, intensity=intensity)

    def test_shock(self, shocker: zap.Shocker, intensity: int):
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.shock(duration=1, intensity=intensity)


def test_beep_no_intensity(shocker: zap.Shocker):
    with pytest.raises(TypeError):
        shocker.beep(duration=1, intensity=2)


def test_unauthorized(credentials: Credentials, responses: RequestsMock):
    responses.post(
        APIURLs.OPERATE,
        body=zap.NotAuthorizedError.TEXT,
        match=get_operate_matchers(apikey="wrong", code="wrong"),
    )
    api = zap.API(username=credentials.username, apikey="wrong")
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
                    "Username": "Zerario",
                    "Apikey": "PISHOCK-APIKEY",
                    "Code": "PISHOCK-SHARECODE",
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
                    "Username": "Zerario",
                    "Apikey": "PISHOCK-APIKEY",
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
                    "Username": "Zerario",
                    "Apikey": "PISHOCK-APIKEY",
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
                    "Username": "Zerario",
                    "Apikey": "PISHOCK-APIKEY",
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
                    "Username": "Zerario",
                    "Apikey": "PISHOCK-APIKEY",
                    "Code": "PISHOCK-SHARECODE",
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
                    "Username": "Zerario",
                    "Apikey": "PISHOCK-APIKEY",
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
                    "Username": "Zerario",
                    "Apikey": "PISHOCK-APIKEY",
                    "ClientId": 1000,
                }
            )
        ],
    )
    with pytest.raises(zap.UnknownError, match=message):
        api.get_shockers(client_id=1000)
