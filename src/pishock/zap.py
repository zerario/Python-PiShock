from __future__ import annotations

import json
import enum
import dataclasses
from typing import Any

import requests

# TODO:
# - vcr -> responses
# - GetShockers with dumbed down ShockerInfo
# - Actually use HTTPError
# - Better error classes for endpoints using 403/404



class Operation(enum.Enum):
    SHOCK = 0
    VIBRATE = 1
    BEEP = 2


class APIError(Exception):
    """Base class for all errors returned by the API."""


class ShareCodeAlreadyUsedError(APIError):
    """API returned: This share code has already been used by somebody else."""

    TEXT = "This share code has already been used by somebody else."


class ShareCodeNotFoundError(APIError):
    """API returned: This code doesn't exist."""

    TEXT = "This code doesn't exist."


class NotAuthorizedError(APIError):
    """API returned: Not Authorized."""

    TEXT = "Not Authorized."


class ShockerPausedError(APIError):
    """API returned: Shocker is Paused or does not exist. Unpause to send command."""

    TEXT = "Shocker is Paused or does not exist. Unpause to send command."


class HTTPError(APIError):
    """Invalid HTTP status from the API."""


class UnknownError(APIError):
    """Unknown message returned from the API."""


class API:
    def __init__(self, username: str, apikey: str) -> None:
        self.username = username
        self.apikey = apikey

    def __repr__(self) -> str:
        return f"API(username={self.username!r}, apikey=...)"

    def request(self, endpoint: str, params: dict[str, Any]) -> requests.Response:
        params = {
            "Username": self.username,
            "Apikey": self.apikey,
            **params,
        }
        response = requests.post(f"https://do.pishock.com/api/{endpoint}", json=params)
        response.raise_for_status()
        return response

    def shocker(self, sharecode: str) -> Shocker:
        return Shocker(api=self, sharecode=sharecode)


@dataclasses.dataclass
class ShockerInfo:
    name: str
    client_id: int
    shocker_id: int
    is_paused: bool
    is_online: bool
    max_intensity: int
    max_duration: int

    @classmethod
    def from_api_dict(cls, data: dict[str, Any]) -> ShockerInfo:
        print(data)
        return cls(
            name=data["name"],
            client_id=data["clientId"],
            shocker_id=data["id"],
            is_paused=data["paused"],
            is_online=data["online"],
            max_intensity=data["maxIntensity"],
            max_duration=data["maxDuration"],
        )


class Shocker:
    NAME = "random"
    SUCCESS_MESSAGES = [
        "Operation Succeeded.",
        "Operation Attempted.",
    ]
    ERROR_MESSAGES = {
        cls.TEXT: cls
        for cls in [
            NotAuthorizedError,
            ShareCodeNotFoundError,
            ShareCodeAlreadyUsedError,
            ShockerPausedError,
        ]
    }

    def __init__(self, api: API, sharecode: str) -> None:
        self.api = api
        self.sharecode = sharecode
        self._cached_info: ShockerInfo | None = None

    def shock(self, duration: int, intensity: int) -> None:
        return self._call(Operation.SHOCK, duration=duration, intensity=intensity)

    def vibrate(self, duration: int, intensity: int) -> None:
        return self._call(Operation.VIBRATE, duration=duration, intensity=intensity)

    def beep(self, duration: int) -> None:
        return self._call(Operation.BEEP, duration=duration, intensity=None)

    def _call(self, operation: Operation, duration: int, intensity: int | None) -> None:
        if not 0 <= duration <= 15:
            raise ValueError(f"duration needs to be between 0 and 15, not {duration}")
        if intensity is not None and not 0 <= intensity <= 100:
            raise ValueError(
                f"intensity needs to be between 0 and 100, not {intensity}"
            )

        assert (intensity is None) == (operation == Operation.BEEP)
        assert operation in Operation

        params = {
            "Name": self.NAME,
            "Code": self.sharecode,
            "Duration": duration,
            "Op": operation.value,
        }
        if intensity is not None:
            params["Intensity"] = intensity

        response = self.api.request("apioperate", params)

        if response.text in self.ERROR_MESSAGES:
            raise self.ERROR_MESSAGES[response.text](response.text)
        elif response.text not in self.SUCCESS_MESSAGES:
            raise UnknownError(response.text)

    def pause(self, pause: bool) -> None:
        if self._cached_info is None:
            self._cached_info = self.info()

        params = {
            "ShockerId": self._cached_info.shocker_id,
            "Pause": pause,
        }
        response = self.api.request("PauseShocker", params)

        if response.text == NotAuthorizedError.TEXT:
            raise NotAuthorizedError(response.text)
        elif response.text != "Operation Successful, Probably.":  # ...shrug
            raise UnknownError(response.text)

    def info(self) -> ShockerInfo:
        params = {"Code": self.sharecode}
        response = self.api.request("GetShockerInfo", params)

        try:
            data = response.json()
        except json.JSONDecodeError:
            raise UnknownError(response.text)
        return ShockerInfo.from_api_dict(data)
