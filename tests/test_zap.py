import os
import dataclasses

import pytest
from responses import RequestsMock, matchers

from pishock import zap


class APIURLs:
    OPERATE = "https://do.pishock.com/api/apioperate"
    PAUSE = "https://do.pishock.com/api/PauseShocker"
    SHOCKER_INFO = "https://do.pishock.com/api/GetShockerInfo"


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


@pytest.mark.parametrize("pause", [True, False])
def test_pause(shocker: zap.Shocker, pause: bool, responses: RequestsMock):
    responses.post(
        APIURLs.SHOCKER_INFO,
        json={
            "name": "test shocker",
            "clientId": "0001",
            "id": "0002",
            "paused": pause,
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
    responses.post(
        APIURLs.PAUSE,
        body=zap.Shocker.SUCCESS_MESSAGE_PAUSE,
        match=[
            matchers.json_params_matcher(
                {
                    "Username": "Zerario",
                    "Apikey": "PISHOCK-APIKEY",
                    "ShockerId": "0002",
                    "Pause": pause,
                }
            )
        ],
    )
    shocker.pause(pause)
    assert shocker.info().is_paused == pause
