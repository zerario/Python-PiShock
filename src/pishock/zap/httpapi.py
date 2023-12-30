from __future__ import annotations

import enum
import contextlib
import dataclasses
import http
import json
from typing import Any, Iterator

import requests

import pishock
from pishock.zap import core

NAME = "Python-PiShock"


class Operation(enum.Enum):
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

    Used as a base class for :exc:`ShockNotAllowedError`,
    :exc:`VibrateNotAllowedError` and :exc:`BeepNotAllowedError`.
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
        assert requests_error.response is not None
        self.body = requests_error.response.text
        self.status_code = requests_error.response.status_code


class UnknownError(APIError):
    """Unknown message returned from the API."""


class PiShockAPI:
    """Base entry point for the PiShock API.

    Arguments:
        username: Your `pishock.com <https://pishock.com/>`_ username.
        api_key: The API key from the `"Account" menu <https://pishock.com/#/account>`_.
    """

    def __init__(self, username: str, api_key: str) -> None:
        self.username = username
        self.api_key = api_key

    def __repr__(self) -> str:
        return f"PiShockAPI(username={self.username!r}, api_key=...)"

    def request(self, endpoint: str, params: dict[str, Any]) -> requests.Response:
        """Make a raw request to the API.

        All requests are POST requests with ``params`` passed as JSON, because the
        API seems to be like that.

        Normally, you should not need to use this method directly.

        Raises:
            HTTPError: If the API returns an invalid HTTP status.
        """
        params = {
            "Username": self.username,
            "Apikey": self.api_key,
            **params,
        }
        headers = {"User-Agent": f"{NAME}/{pishock.__version__}"}
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

    @contextlib.contextmanager
    def translate_http_errors(self) -> Iterator[None]:
        try:
            yield
        except HTTPError as e:
            if e.status_code == http.HTTPStatus.NOT_FOUND:
                raise ShareCodeNotFoundError(ShareCodeNotFoundError.TEXT)
            elif e.status_code == http.HTTPStatus.FORBIDDEN:
                raise NotAuthorizedError(NotAuthorizedError.TEXT)
            raise

    def shocker(
        self, sharecode: str, log_name: str = NAME, name: str | None = None
    ) -> HTTPShocker:
        """Get a :class:`HTTPShocker` instance for the given share code.

        This is the main entry point for almost all remaining API usages.

        Arguments:
            sharecode: The share code generated via the web interface.
            log_name: How the shocker should be named in the logs on the website.
            name: Used when converting the :class:`HTTPShocker` to a string,
                  defaults to ``sharecode``.
        """
        return HTTPShocker(api=self, sharecode=sharecode, log_name=log_name, name=name)

    def get_shockers(self, client_id: int) -> list[core.BasicShockerInfo]:
        """Get a list of all shockers for the given client (PiShock) ID.

        Raises:
            NotAuthorizedError: If username/API key is wrong.
            HTTPError: If the API returns an invalid HTTP status.
            UnknownError: If the response is not JSON.
        """
        params = {"ClientId": client_id}

        with self.translate_http_errors():
            response = self.request("GetShockers", params)

        try:
            data = response.json()
        except json.JSONDecodeError:
            raise UnknownError(response.text)
        return [
            core.BasicShockerInfo.from_get_shockers_api_dict(d, client_id=client_id)
            for d in data
        ]

    def verify_credentials(self) -> bool:
        """Check if the API credentials are valid.

        Returns:
            ``True`` on success, ``False`` on authentication failure.

        Raises:
            HTTPError: If the API returns an invalid HTTP status.
        """
        try:
            self.request("VerifyApiCredentials", {})
        except HTTPError as e:
            if e.status_code == http.HTTPStatus.FORBIDDEN:
                return False
            raise
        return True


@dataclasses.dataclass
class DetailedShockerInfo(core.BasicShockerInfo):
    """Detailed information about a shocker.

    Used by :meth:`HTTPShocker.info()`. Calling
    :meth:`PiShockAPI.get_shockers()` or
    :meth:`pishock.zap.serialapi.SerialShocker.info()` returns a
    :class:`pishock.zap.core.BasicShockerInfo` instance instead.

    This class extends :class:`pishock.zap.core.BasicShockerInfo` with the
    following attributes:

    Attributes:
        max_intensity: The maximum intensity (0-100) the shocker can be set to.
        max_duration: The maximum duration (0-15) the shocker can be set to.
    """

    max_intensity: int
    max_duration: int

    @classmethod
    def from_info_api_dict(cls, data: dict[str, Any]) -> DetailedShockerInfo:
        return cls(
            name=data["name"],
            client_id=data["clientId"],
            shocker_id=data["id"],
            is_paused=data["paused"],
            max_intensity=data["maxIntensity"],
            max_duration=data["maxDuration"],
        )


class HTTPShocker(core.Shocker):
    """Represents a single shocker / share code using the HTTP API.

    Normally, there should be no need to instanciate this manually, use
    :meth:`PiShockAPI.shocker()` instead.
    """

    IS_SERIAL = False
    _SUCCESS_MESSAGES = [
        "Operation Succeeded.",
        "Operation Attempted.",
    ]
    _SUCCESS_MESSAGE_PAUSE = "Operation Successful, Probably."  # ...shrug
    _ERROR_MESSAGES = {
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

    def __init__(
        self, api: PiShockAPI, sharecode: str, name: str | None, log_name: str
    ) -> None:
        self.api = api
        self.sharecode = sharecode
        self.name = name
        self.log_name = log_name
        self._cached_info: DetailedShockerInfo | None = None

    def __str__(self) -> str:
        if self.name is not None:
            return self.name
        return self.sharecode

    def shock(self, *, duration: int | float, intensity: int) -> None:
        """Send a shock with the given duration (0-15) and intensity (0-100).

        Durations can also be floats between 0.1 and 1.5 (inclusive), with the
        following caveats:

        - The duration is rounded down to the nearest 0.1 seconds.
        - On old Plus models, e.g. 0.3 is interpreted as 3s instead of 300ms.
        - This is an experimental and undocumented feature of the API, so it
          might break at any time.

        Raises:
            ValueError: ``duration`` or ``intensity`` are out of range.
            APIError: Any of the :exc:`APIError` subclasses in this module,
               refer to their documenation for details.
        """
        return self._call(Operation.SHOCK, duration=duration, intensity=intensity)

    def vibrate(self, *, duration: int | float, intensity: int) -> None:
        """Send a vibration with the given duration (0-15) and intensity (0-100).

        Durations can also be floats between 0.1 and 1.5 (inclusive), with the
        following caveats:

        - The duration is rounded down to the nearest 0.1 seconds.
        - On old Plus models, e.g. 0.3 is interpreted as 3s instead of 300ms.
        - This is an experimental and undocumented feature of the API, so it
          might break at any time.

        Raises:
            ValueError: ``duration`` or ``intensity`` are out of range.
            APIError: Any of the :exc:`APIError` subclasses in this
              module, refer to their documenation for details.
        """
        return self._call(Operation.VIBRATE, duration=duration, intensity=intensity)

    def beep(self, duration: int | float) -> None:
        """Send a beep with the given duration (0-15).

        Durations can also be floats between 0.1 and 1.5 (inclusive), with the
        following caveats:

        - The duration is rounded down to the nearest 0.1 seconds.
        - On old Plus models, e.g. 0.3 is interpreted as 3s instead of 300ms.
        - This is an experimental and undocumented feature of the API, so it
          might break at any time.

        Raises:
            ValueError: ``duration`` is out of range.
            APIError: Any of the :exc:`APIError` subclasses in this
              module, refer to their documenation for details.
        """
        return self._call(Operation.BEEP, duration=duration, intensity=None)

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
        self, operation: Operation, duration: int | float, intensity: int | None
    ) -> None:
        if intensity is not None and not 0 <= intensity <= 100:
            raise ValueError(
                f"intensity needs to be between 0 and 100, not {intensity}"
            )

        assert (intensity is None) == (operation == Operation.BEEP)
        assert operation in Operation

        params = {
            "Name": self.log_name,
            "Code": self.sharecode,
            "Duration": self._parse_duration(duration),
            "Op": operation.value,
        }
        if intensity is not None:
            params["Intensity"] = intensity

        response = self.api.request("apioperate", params)

        if response.text in self._ERROR_MESSAGES:
            raise self._ERROR_MESSAGES[response.text](response.text)
        elif response.text not in self._SUCCESS_MESSAGES:
            raise UnknownError(response.text)

    def pause(self, pause: bool) -> None:
        """Pause/unpause the shocker.

        Args:
            pause: Whether to pause or unpause the shocker.

        Raises:
            NotAuthorizedError: the API credentials are wrong.
            UnknownError: The response is not JSON.
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
        elif response.text != self._SUCCESS_MESSAGE_PAUSE:
            raise UnknownError(response.text)

    def info(self) -> DetailedShockerInfo:
        """Get detailed information about the shocker.

        Raises:
            NotAuthorizedError: Username/API key is wrong.
            ShareCodeNotFoundError: The given share code was not found.
            UnknownError: The response is not JSON.
        """
        params = {"Code": self.sharecode}

        with self.api.translate_http_errors():
            response = self.api.request("GetShockerInfo", params)

        try:
            data = response.json()
        except json.JSONDecodeError:
            raise UnknownError(response.text)
        return DetailedShockerInfo.from_info_api_dict(data)
