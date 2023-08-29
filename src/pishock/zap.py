from __future__ import annotations

import dataclasses
import enum
import http
import json
from typing import Any

import requests

from . import __version__ as __version__

# TODO:
# - Address book
# - Random mode
# - PiVault
# - Readme / API docs
# - Rename to PyShock?


NAME = "Python-PiShock"


class _Operation(enum.Enum):
    SHOCK = 0
    VIBRATE = 1
    BEEP = 2


class APIError(Exception):
    """Base class for all errors returned by the API."""

    # Messages which are currently not handled because it's unclear how to
    # reproduce them:
    #
    # "Client has been locked because the owner has been naughty.."
    # "Version too old, contact for upgrade."
    # "Unauthorized Attempt."
    # "Invalid/Forbidden Method"
    #
    # Messages which are not handled because we should be doing the right thing:
    #
    # "Unknown Op, use 0 for shock, 1 for vibrate and 2 for beep"
    # "Duration must be between 1 and {maxdur}"
    # "Intensity must be between 0 and {maxint}"

    TEXT: str  # set by subclasses


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


class DeviceInUseError(APIError):
    """API returned: Device in Use."""

    TEXT = "Device in Use."


class OperationNotAllowedError(APIError):
    """API returned: <Operation> not allowed.

    Used as a base class for ShockNotAllowedError, VibrateNotAllowedError and
    BeepNotAllowedError.
    """


class ShockNotAllowedError(OperationNotAllowedError):
    """API returned: Shock not allowed."""

    TEXT = "Shock not allowed."


class VibrateNotAllowedError(OperationNotAllowedError):
    """API returned: Vibrate not allowed."""

    TEXT = "Vibrate not allowed."


class BeepNotAllowedError(OperationNotAllowedError):
    """API returned: Beep not allowed."""

    TEXT = "Beep not allowed."


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
        headers = {"User-Agent": f"{NAME}/{__version__}"}
        response = requests.post(
            f"https://do.pishock.com/api/{endpoint}",
            json=params,
            headers=headers,
        )

        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise HTTPError(e) from e

        return response

    def shocker(self, sharecode: str, name: str = NAME) -> Shocker:
        """Get a Shocker instance for the given share code.

        This is the main entry point for almost all remaining API usages.

        Via the optional `name` argument, how the shocker is named in the
        logs can be specified.
        """
        return Shocker(api=self, sharecode=sharecode, name=name)

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

    def verify_credentials(self) -> bool:
        """Check if the API credentials are valid.

        Returns True on success, False on authentication failure.
        """
        try:
            self.request("VerifyApiCredentials", {})
        except HTTPError as e:
            if e.status_code == http.HTTPStatus.FORBIDDEN:
                return False
            raise
        return True


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
            DeviceInUseError,
            ShockNotAllowedError,
            VibrateNotAllowedError,
            BeepNotAllowedError,
        ]
    }

    def __init__(self, api: API, sharecode: str, name: str) -> None:
        self.api = api
        self.sharecode = sharecode
        self.name = name
        self._cached_info: ShockerInfo | None = None

    def shock(self, *, duration: int | float, intensity: int) -> None:
        """Send a shock with the given duration (0-15) and intensity (0-100).

        Durations can also be floats between 0.1 and 1.5 (inclusive), with the
        following caveats:

        - The duration is rounded down to the nearest 0.1 seconds.
        - On old Plus models and the V3 firmware, e.g. 0.3 is interpreted as 3s
          instead of 300ms.
        - This is an experimental and undocumented feature of the API, so it
          might break at any time.

        Raises:
            - `ValueError` if `duration` or `intensity` are out of range.
            - Any of the `APIError` subclasses in this module, refer to their
              documenation for details.
        """
        return self._call(_Operation.SHOCK, duration=duration, intensity=intensity)

    def vibrate(self, *, duration: int | float, intensity: int) -> None:
        """Send a vibration with the given duration (0-15) and intensity (0-100).

        Durations can also be floats between 0.1 and 1.5 (inclusive), with the
        following caveats:

        - The duration is rounded down to the nearest 0.1 seconds.
        - On old Plus models and the V3 firmware, e.g. 0.3 is interpreted as 3s
          instead of 300ms.
        - This is an experimental and undocumented feature of the API, so it
          might break at any time.

        Raises:
            - `ValueError` if `duration` or `intensity` are out of range.
            - Any of the `APIError` subclasses in this module, refer to their
              documenation for details.
        """
        return self._call(_Operation.VIBRATE, duration=duration, intensity=intensity)

    def beep(self, duration: int | float) -> None:
        """Send a beep with the given duration (0-15).

        Durations can also be floats between 0.1 and 1.5 (inclusive), with the
        following caveats:

        - The duration is rounded down to the nearest 0.1 seconds.
        - On old Plus models and the V3 firmware, e.g. 0.3 is interpreted as 3s
          instead of 300ms.
        - This is an experimental and undocumented feature of the API, so it
          might break at any time.

        Raises:
            - `ValueError` if `duration` is out of range.
            - Any of the `APIError` subclasses in this module, refer to their
              documenation for details.
        """
        return self._call(_Operation.BEEP, duration=duration, intensity=None)

    def _parse_duration(self, duration: int | float) -> int:
        if isinstance(duration, float) and not duration.is_integer():
            if not 0.1 <= duration < 1.6:
                raise ValueError(
                    f"float duration needs to be between 0.1 and 1.5, not {duration}"
                )
            return int(duration * 1000)  # e.g. 0.1 -> 100 sent to API -> 100ms

        if not 0 <= duration <= 15:
            raise ValueError(f"duration needs to be between 0 and 15, not {duration}")

        return int(duration)

    def _call(
        self, operation: _Operation, duration: int | float, intensity: int | None
    ) -> None:
        if intensity is not None and not 0 <= intensity <= 100:
            raise ValueError(
                f"intensity needs to be between 0 and 100, not {intensity}"
            )

        assert (intensity is None) == (operation == _Operation.BEEP)
        assert operation in _Operation

        params = {
            "Name": self.name,
            "Code": self.sharecode,
            "Duration": self._parse_duration(duration),
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
