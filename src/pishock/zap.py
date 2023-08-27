from __future__ import annotations

import json
import enum
import dataclasses
from typing import Any

import requests


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


class HTTPError(APIError):
    """Invalid HTTP status from the API."""


class UnknownError(APIError):
    """Unknown message returned from the API."""


class Account:
    def __init__(self, username: str, apikey: str) -> None:
        self.username = username
        self.apikey = apikey

    def __repr__(self) -> str:
        return f"Account(username={self.username!r}, apikey=...)"


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
        ]
    }

    def __init__(self, account: Account, sharecode: str) -> None:
        self.account = account
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
            "Username": self.account.username,
            "Name": self.NAME,
            "Code": self.sharecode,
            "Apikey": self.account.apikey,
            "Duration": duration,
            "Op": operation.value,
        }
        if intensity is not None:
            params["Intensity"] = intensity

        response = requests.post("https://do.pishock.com/api/apioperate", json=params)
        response.raise_for_status()  # FIXME test for 404/403

        if response.text in self.ERROR_MESSAGES:
            raise self.ERROR_MESSAGES[response.text](response.text)
        elif response.text not in self.SUCCESS_MESSAGES:
            raise UnknownError(response.text)

    def pause(self, pause: bool) -> None:
        if self._cached_info is None:
            self._cached_info = self.info()

        params = {
            "Username": self.account.username,
            "ShockerId": self._cached_info.shocker_id,
            "Apikey": self.account.apikey,
            "Pause": pause,
        }
        response = requests.post("https://do.pishock.com/api/PauseShocker", json=params)
        response.raise_for_status()

        if response.text == NotAuthorizedError.TEXT:
            raise NotAuthorizedError(response.text)
        elif response.text != "Operation Successful, Probably.":  # ...shrug
            raise UnknownError(response.text)

    def info(self) -> ShockerInfo:
        params = {
            "Username": self.account.username,
            "Code": self.sharecode,
            "Apikey": self.account.apikey,
        }
        response = requests.post(
            "https://do.pishock.com/api/GetShockerInfo",
            json=params,
        )
        response.raise_for_status()  # FIXME better error classes for 403/404?
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise UnknownError(response.text)
        return ShockerInfo.from_api_dict(data)
