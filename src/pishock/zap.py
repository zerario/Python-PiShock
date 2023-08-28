from __future__ import annotations

import json
import enum
import dataclasses
from typing import Any

import requests

class _Operation(enum.Enum):
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


class DeviceNotConnectedError(APIError):
    """API returned: Device currently not connected."""

    TEXT = "Device currently not connected."


class HTTPError(APIError):
    """Invalid HTTP status from the API."""

    def __init__(self, requests_error: requests.HTTPError) -> None:
        self.body = requests_error.response.text
        self.status_code = requests_error.response.status_code


class UnknownError(APIError):
    """Unknown message returned from the API."""


class API:

    """Base entry point for the PiShock API."""

    def __init__(self, username: str, apikey: str) -> None:
        self.username = username
        self.apikey = apikey

    def __repr__(self) -> str:
        return f"API(username={self.username!r}, apikey=...)"

    def request(self, endpoint: str, params: dict[str, Any]) -> requests.Response:
        """Make a request to the API.

        All requests are POST requests with `params` passed as JSON, because the
        API seems to be like that.

        Normally, you should not need to use this method directly.
        """
        params = {
            "Username": self.username,
            "Apikey": self.apikey,
            **params,
        }
        response = requests.post(f"https://do.pishock.com/api/{endpoint}", json=params)

        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise HTTPError(e) from e

        return response

    def shocker(self, sharecode: str) -> Shocker:
        """Get a Shocker instance for the given share code.

        This is the main entry point for almost all remaining API usages.
        """
        return Shocker(api=self, sharecode=sharecode)

    def get_shockers(self, client_id: int) -> list[BasicShockerInfo]:
        """Get a list of all shockers for the given client (PiShock) ID.

        Raises:
            - `HTTPError` with a 403 status code if username/API key is wrong.
            - `UnknownError` if the response is not JSON.
        """
        params = {"ClientId": client_id}
        response = self.request("GetShockers", params)

        try:
            data = response.json()
        except json.JSONDecodeError:
            raise UnknownError(response.text)
        return [
            BasicShockerInfo.from_get_shockers_api_dict(d, client_id=client_id)
            for d in data
        ]


@dataclasses.dataclass
class BasicShockerInfo:
    """Basic information about a shocker.

    Used by `API.get_shockers`. Calling `Shocker.info()` returns a `ShockerInfo`
    instance instead.
    """

    name: str
    client_id: int
    shocker_id: int
    is_paused: bool

    @classmethod
    def from_get_shockers_api_dict(
        cls, data: dict[str, Any], client_id: int
    ) -> BasicShockerInfo:
        return cls(
            name=data["name"],
            client_id=client_id,
            shocker_id=data["id"],
            is_paused=data["paused"],
        )


@dataclasses.dataclass
class ShockerInfo(BasicShockerInfo):
    """Detailed information about a shocker."""

    is_online: bool
    max_intensity: int
    max_duration: int

    @classmethod
    def from_info_api_dict(cls, data: dict[str, Any]) -> ShockerInfo:
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
    """Represents a single shocker / share code."""

    NAME = "random"
    SUCCESS_MESSAGES = [
        "Operation Succeeded.",
        "Operation Attempted.",
    ]
    SUCCESS_MESSAGE_PAUSE = "Operation Successful, Probably."  # ...shrug
    ERROR_MESSAGES = {
        cls.TEXT: cls
        for cls in [
            NotAuthorizedError,
            ShareCodeNotFoundError,
            ShareCodeAlreadyUsedError,
            ShockerPausedError,
            DeviceNotConnectedError,
        ]
    }

    def __init__(self, api: API, sharecode: str) -> None:
        self.api = api
        self.sharecode = sharecode
        self._cached_info: ShockerInfo | None = None

    def shock(self, *, duration: int, intensity: int) -> None:
        """Send a shock with the given duration (0-15) and intensity (0-100).

        Raises:
            - `ValueError` if `duration` or `intensity` are out of range.
            - Any of the `APIError` subclasses in this module, refer to their
              documenation for details.
        """
        return self._call(_Operation.SHOCK, duration=duration, intensity=intensity)

    def vibrate(self, *, duration: int, intensity: int) -> None:
        """Send a vibration with the given duration (0-15) and intensity (0-100).

        Raises:
            - `ValueError` if `duration` or `intensity` are out of range.
            - Any of the `APIError` subclasses in this module, refer to their
              documenation for details.
        """
        return self._call(_Operation.VIBRATE, duration=duration, intensity=intensity)

    def beep(self, duration: int) -> None:
        """Send a beep with the given duration (0-15).

        Raises:
            - `ValueError` if `duration` is out of range.
            - Any of the `APIError` subclasses in this module, refer to their
              documenation for details.
        """
        return self._call(_Operation.BEEP, duration=duration, intensity=None)

    def _call(self, operation: _Operation, duration: int, intensity: int | None) -> None:
        if not 0 <= duration <= 15:
            raise ValueError(f"duration needs to be between 0 and 15, not {duration}")
        if intensity is not None and not 0 <= intensity <= 100:
            raise ValueError(
                f"intensity needs to be between 0 and 100, not {intensity}"
            )

        assert (intensity is None) == (operation == _Operation.BEEP)
        assert operation in _Operation

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
        """Pause/unpause the shocker.

        Args:
            - `pause`: Whether to pause or unpause the shocker.

        Raises:
            - `NotAuthorizedError` if the API credentials are wrong.
            - `UnknownError` if the response is not JSON.
        """
        if self._cached_info is None:
            self._cached_info = self.info()

        params = {
            "ShockerId": self._cached_info.shocker_id,
            "Pause": pause,
        }
        response = self.api.request("PauseShocker", params)

        if response.text == NotAuthorizedError.TEXT:
            raise NotAuthorizedError(response.text)
        elif response.text != self.SUCCESS_MESSAGE_PAUSE:
            raise UnknownError(response.text)

    def info(self) -> ShockerInfo:
        """Get detailed information about the shocker.

        Raises:
            - `HTTPError` with a 403 status code if username/API key is wrong.
            - `UnknownError` if the response is not JSON.
        """
        params = {"Code": self.sharecode}
        response = self.api.request("GetShockerInfo", params)

        try:
            data = response.json()
        except json.JSONDecodeError:
            raise UnknownError(response.text)
        return ShockerInfo.from_info_api_dict(data)
