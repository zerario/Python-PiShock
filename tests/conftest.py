from __future__ import annotations

import http
from typing import Any, Callable

import pytest
from responses import RequestsMock, matchers
from typing_extensions import TypeAlias

from pishock import zap

_MatcherType: TypeAlias = Callable[..., Any]


class FakeCredentials:
    USERNAME = "PISHOCK-USERNAME"
    API_KEY = "PISHOCK-APIKEY"
    SHARECODE = "PISHOCK-SHARECODE"


class APIURLs:
    BASE = "https://do.pishock.com/api"
    OPERATE = f"{BASE}/apioperate"
    PAUSE = f"{BASE}/PauseShocker"
    SHOCKER_INFO = f"{BASE}/GetShockerInfo"
    GET_SHOCKERS = f"{BASE}/GetShockers"
    VERIFY_CREDENTIALS = f"{BASE}/VerifyApiCredentials"


@pytest.fixture
def credentials() -> FakeCredentials:
    return FakeCredentials()


class PiShockPatcher:

    """Helper class which fakes the PiShock API using responses.

    Each API endpoint has three methods here, e.g. for ApiOperate:

    - operate_matchers: Returns the responses matchers to use for requests to
      this endpoint, matching all the data our client sent. This might be
      configurable via keyword arguments, but only to the extent used by the
      tests.
    - operate_raw: Do a raw responses call for the operate endpoint.
    - operate: Configure responses for an ApiOperate request, with some sensible
      defaults for how a request will usually look.
    """

    HEADERS = {
        "User-Agent": f"{zap.NAME}/{zap.__version__}",
        "Content-Type": "application/json",
    }
    NAME = zap.NAME

    def __init__(self, responses: RequestsMock) -> None:
        self.responses = responses

    # ApiOperate

    def operate_matchers(self, **kwargs: Any) -> list[_MatcherType]:
        template = {
            "Username": FakeCredentials.USERNAME,
            "Apikey": FakeCredentials.API_KEY,
            "Code": FakeCredentials.SHARECODE,
            "Name": self.NAME,
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
            matchers.header_matcher(self.HEADERS),
        ]

    def operate_raw(self, **kwargs: Any) -> None:
        self.responses.post(APIURLs.OPERATE, **kwargs)

    def operate(
        self, body: str = zap.Shocker.SUCCESS_MESSAGES[0], **kwargs: Any
    ) -> None:
        self.operate_raw(
            body=body,
            match=self.operate_matchers(**kwargs),
        )

    # GetShockerInfo

    def info_matchers(self) -> list[_MatcherType]:
        return [
            matchers.json_params_matcher(
                {
                    "Username": FakeCredentials.USERNAME,
                    "Apikey": FakeCredentials.API_KEY,
                    "Code": FakeCredentials.SHARECODE,
                }
            ),
            matchers.header_matcher(self.HEADERS),
        ]

    def info_raw(self, **kwargs: Any) -> None:
        self.responses.post(APIURLs.SHOCKER_INFO, **kwargs)

    def info(self, paused: bool = False, online: bool = True) -> None:
        self.info_raw(
            json={
                "name": "test shocker",
                "clientId": 1000,
                "id": 1001,
                "paused": paused,
                "online": online,
                "maxIntensity": 100,
                "maxDuration": 15,
            },
            match=self.info_matchers(),
        )

    # PauseShocker

    def pause_matchers(self, pause: bool) -> list[_MatcherType]:
        return [
            matchers.json_params_matcher(
                {
                    "Username": FakeCredentials.USERNAME,
                    "Apikey": FakeCredentials.API_KEY,
                    "ShockerId": 1001,
                    "Pause": pause,
                }
            ),
            matchers.header_matcher(self.HEADERS),
        ]

    def pause_raw(self, **kwargs: Any) -> None:
        self.responses.post(APIURLs.PAUSE, **kwargs)

    def pause(self, pause: bool, body: str = zap.Shocker.SUCCESS_MESSAGE_PAUSE) -> None:
        self.pause_raw(body=body, match=self.pause_matchers(pause))

    # GetShockers

    def get_shockers_matchers(self) -> list[_MatcherType]:
        return [
            matchers.json_params_matcher(
                {
                    "Username": FakeCredentials.USERNAME,
                    "Apikey": FakeCredentials.API_KEY,
                    "ClientId": 1000,
                }
            ),
            matchers.header_matcher(self.HEADERS),
        ]

    def get_shockers_raw(self, **kwargs: Any) -> None:
        self.responses.post(
            APIURLs.GET_SHOCKERS,
            **kwargs,
        )

    def get_shockers(self) -> None:
        self.get_shockers_raw(
            json=[
                {"name": "test shocker", "id": 1001, "paused": False},
                {"name": "test shocker 2", "id": 1002, "paused": True},
            ],
            match=self.get_shockers_matchers(),
        )

    # VerifyApiCredentials

    def verify_credentials_matchers(
        self,
        username: str = FakeCredentials.USERNAME,
    ) -> list[_MatcherType]:
        return [
            matchers.json_params_matcher(
                {
                    "Username": username,
                    "Apikey": FakeCredentials.API_KEY,
                }
            ),
            matchers.header_matcher(self.HEADERS),
        ]

    def verify_credentials_raw(self, **kwargs: Any) -> None:
        self.responses.post(
            APIURLs.VERIFY_CREDENTIALS,
            **kwargs,
        )

    def verify_credentials(
        self,
        valid: bool,
        username: str = FakeCredentials.USERNAME,
    ) -> None:
        self.verify_credentials_raw(
            status=http.HTTPStatus.OK if valid else http.HTTPStatus.FORBIDDEN,
            match=self.verify_credentials_matchers(username=username),
        )


@pytest.fixture
def patcher(responses: RequestsMock) -> PiShockPatcher:
    """Helper to patch the PiShock API using responses."""
    return PiShockPatcher(responses)
