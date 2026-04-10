from __future__ import annotations

import enum
import contextlib
import http
import json
from typing import Any, Iterator

import requests

import pishock
from pishock.zap import core

NAME = "Python-PiShock"

METHOD_GET = "GET"
METHOD_POST = "POST"

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
    CODE: int | None = None


class ShareCodeAlreadyUsedError(APIError):
    """API returned: This share code has already been used by somebody else."""

    TEXT = "This share code has already been used by somebody else."


class ShareCodeNotFoundError(APIError):
    """API returned: This code doesn't exist."""

    TEXT = "This code doesn't exist."

class SockerIdNotFoundError(APIError):
    """API returned: This code doesn't exist."""

    TEXT = "This code doesn't exist."


class NotAuthorizedError(APIError):
    """API returned: Not Authorized."""

    TEXT = "Not Authorized."
    CODE = 401


class ForbiddenError(APIError):
    """API returned: Not Authorized."""

    TEXT = "Forbidden."
    CODE = 403

class CouldNotFindShare(APIError):
    """API returned: Could not find share code."""
    TEXT = "Could not find share code."
    CODE = 404

class UnsupportedOperationError(APIError):
    """API returned: Operation not supported."""
    TEXT = "Operation not supported."
    CODE = 405

class NotV3ShockersError(APIError):
    """API returned: Not a v3 shocker."""
    TEXT = "Not a v3 shocker."
    CODE = 406

class ShareIsLockedError(APIError):
    """API returned: Share is locked."""
    TEXT = "Share is locked."
    CODE = 410

class IntensityOutOfBoundsError(APIError):
    """API returned: Intensity out of bounds."""
    TEXT = "Intensity out of bounds. (Must be between 0 and 100 and lower than max intensity)"
    CODE = 412

class DurationExceedsLimits(APIError):
    """API returned: Duration exceeds limits."""
    TEXT = "Duration exceeds limits. (Must be between 0 and 15 and lower than max duration)"
    CODE = 416

class ShockerPausedError(APIError):
    """API returned: Shocker is Paused or does not exist. Unpause to send command."""

    TEXT = "Shocker is Paused or does not exist. Unpause to send command."
    CODE = 503


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

class BadShockerRequestError(APIError):
    """While creating a shocker, not enough information was supplied"""

    TEXT = "You must specify either a shockerId or name when creating a shocker"

class NonUniqueShockerNameError(APIError):
    """While creating a shocker, zero or multiple shockers were found matching the supplied name"""

    TEXT = "While creating a shocker, zero or multiple shockers were found matching the supplied name"

class InvalidHTTPMethod(APIError):
    """HTTP Request Malfomed with invalid method"""
    TEXT = "Only GET and POST HTTP methods accepted at the moment"


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
        api_key: The API key from the `"Account" menu <https://login.pishock.com/account>`_.
    """

    def __init__(self, username: str, api_key: str) -> None:
        self.username = username
        self.api_key = api_key

        self.obtain_user_id()

    def __repr__(self) -> str:
        return f"PiShockAPI(username={self.username!r}, api_key=...)"
    
    def get(self, endpoint: str, body: dict[str, Any] = {}, params: dict[str, str] = {}) -> requests.Response:
        return self.request(method=METHOD_GET, endpoint=endpoint, body=body, params=params)

    def post(self,  endpoint: str, body: dict[str, Any] = {}, params: dict[str, str] = {}) -> requests.Response:
        return self.request(method=METHOD_POST, endpoint=endpoint, body=body, params=params)
    
    def request(self, method: str,  endpoint: str, body: dict[str, Any] = {}, params: dict[str, str] = {}) -> requests.Response:
        """Make a raw request to the API.

        All requests are POST requests with ``params`` passed as JSON, because the
        API seems to be like that.

        Normally, you should not need to use this method directly.

        Raises:
            HTTPError: If the API returns an invalid HTTP status.
        """
        headers = {
            "User-Agent": f"{NAME}/{pishock.__version__}",
            "X-PiShock-Api-Key": f"{self.api_key}",
            "X-PiShock-UserId": f"{self.username}",
        }

        if (method == METHOD_GET):
            response = requests.get(
                f"https://api.pishock.com/{endpoint}",
                params=params,
                json=body,
                headers=headers,
            )
        elif (method == METHOD_POST):
            response = requests.post(
                f"https://api.pishock.com/{endpoint}",
                params=params,
                json=body,
                headers=headers,
            )
        else:
            raise InvalidHTTPMethod()
        
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
        self, shocker_id: int | None = None, name: str | None = None, log_name: str = NAME
    ) -> HTTPShocker:
        """Get a :class:`HTTPShocker` instance for the given share code.

        This is the main entry point for almost all remaining API usages. You must specify at least one of shockerId or name

        Arguments:
            shocker_id: The shocker ID which can be found by clicking the Gear icon in the web interface
            name: The name of the shocker from the UI
            log_name: How the shocker should be named in the logs on the website.
        """
        if shocker_id is None and name is None:
            raise BadShockerRequestError()
        
        confirmed_id = shocker_id;
        
        if name is not None:
            all_shockers = self.get_shockers()
            possible_shockers = [s for s in all_shockers if s.name == name]
            if len(possible_shockers) != 1:
                raise NonUniqueShockerNameError()
            confirmed_id = possible_shockers[0].shocker_id

        return HTTPShocker(api=self, shocker_id=confirmed_id, log_name=log_name, name=name)

    def get_shockers(self) -> list[core.ApiV3ShockerInfo]:
        """Get a list of all shockers for the given client (PiShock) ID.

        Raises:
            NotAuthorizedError: If username/API key is wrong.
            HTTPError: If the API returns an invalid HTTP status.
            UnknownError: If the response is not JSON.
        """

        with self.translate_http_errors():
            response = self.get("Shockers")

        try:
            data = response.json()
        except json.JSONDecodeError:
            raise UnknownError(response.text)
        return [
            core.ApiV3ShockerInfo.from_get_shockers_api_dict(d)
            for d in data
        ]

    def obtain_user_id(self) -> bool:
        """Obtains and caches the userId associated with this account and API key

        Called by the __init__ method
        """

        try:
            response = self.get(endpoint=f"Account")
            try:
                data = response.json()
                self.user_id = data["UserId"]
            except json.JSONDecodeError:
                raise UnknownError(response.text)
        except HTTPError as e:
            if e.status_code == http.HTTPStatus.FORBIDDEN:
                return False
            raise
        return True

    def verify_credentials(self) -> bool:
        """Check if the API credentials are valid. Must be called to obtain the UserID

        Returns:
            ``True`` on success, ``False`` on authentication failure.

        Raises:
            HTTPError: If the API returns an invalid HTTP status.
        """
        try:
            self.get(endpoint=f"Account/{self.user_id}")
        except HTTPError as e:
            if e.status_code == http.HTTPStatus.FORBIDDEN:
                return False
            raise
        return True

class HTTPShocker(core.Shocker):
    """Represents a single shocker using the HTTP API.

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
            ShockerPausedError,
            DeviceNotConnectedError,
            DeviceInUseError,
            ShockNotAllowedError,
            VibrateNotAllowedError,
            BeepNotAllowedError,
        ]
    }
    _ERROR_MESSAGES_BY_CODE = {
        cls.CODE: cls
        for cls in [
            NotAuthorizedError,
            ForbiddenError,
            CouldNotFindShare,
            UnsupportedOperationError,
            NotV3ShockersError,
            ShareIsLockedError,
            IntensityOutOfBoundsError,
            DurationExceedsLimits,
            ShockerPausedError,
        ]
    }

    def __init__(
        self, api: PiShockAPI, shocker_id: str, name: str | None, log_name: str
    ) -> None:
        self.api = api
        self.shocker_id = shocker_id
        self.name = name
        self.log_name = log_name
        self._cached_info: core.ApiV3ShockerInfo | None = None

    def __str__(self) -> str:
        if self.name is not None:
            return self.name
        return str(self.shocker_id)

    def shock(self, *, duration: int | float, intensity: int, min_duration: int | float | None = None, min_intensity: int | None = None, intensity_as_pct: bool = False) -> None:
        """Send a shock with the given duration (0-15) in seconds and intensity (0-100).

        Durations can be floats between 0.016 and 15.000 or integers between 0 and 15

        If min_duration is specified, a random duration will be used between 
        min_duration and duration.

        If min_intensity is specified, a random intensity will be used between
        min_intensity and intensity.

        If intensity_as_pct is True, the intensity values will be treated as a percentage of 
        the shocker's max intensity.

        Raises:
            ValueError: ``duration`` or ``intensity`` are out of range.
            APIError: Any of the :exc:`APIError` subclasses in this module,
               refer to their documenation for details.
        """
        return self._call(Operation.SHOCK, duration=duration, intensity=intensity, min_duration=min_duration, min_intensity=min_intensity, intensity_as_pct=intensity_as_pct)

    def vibrate(self, *, duration: int | float, intensity: int, min_duration: int | float | None = None, min_intensity: int | None = None, intensity_as_pct: bool = False) -> None:
        """Send a vibration with the given duration (0-15) in seconds and intensity (0-100).

        Durations can be floats between 0.016 and 15.000 or integers between 0 and 15

        If min_duration is specified, a random duration will be used between 
        min_duration and duration.

        If min_intensity is specified, a random intensity will be used between
        min_intensity and intensity.

        If intensity_as_pct is True, the intensity values will be treated as a percentage of 
        the shocker's max intensity.

        Raises:
            ValueError: ``duration`` or ``intensity`` are out of range.
            APIError: Any of the :exc:`APIError` subclasses in this
              module, refer to their documenation for details.
        """
        return self._call(Operation.VIBRATE, duration=duration, intensity=intensity, min_duration=min_duration, min_intensity=min_intensity, intensity_as_pct=intensity_as_pct)

    def beep(self, duration: int | float, min_duration: int | float | None = None) -> None:
        """Send a beep with the given duration in seconds. 

        Durations can be floats between 0.016 and 15.000 or integers between 0 and 15

        If min_duration is specified, a random duration will be used between 
        min_duration and duration.

        Raises:
            ValueError: ``duration`` is out of range.
            APIError: Any of the :exc:`APIError` subclasses in this
              module, refer to their documenation for details.
        """
        return self._call(Operation.BEEP, duration=duration, intensity=None)

    def _parse_duration(self, duration: int | float) -> int:
        duration_ms = int(duration * 1000) # v3 API always expects ms
        if duration_ms < 16:
            return 16
        return duration_ms

    def _call(
        self, operation: Operation, duration: int | float, intensity: int | None, min_duration: int | float | None = None, min_intensity: int | None = None, intensity_as_pct: bool = False
    ) -> None:
        shocker_info = self.info()
        if intensity is not None and not 0 <= intensity <= 100:
            raise ValueError(
                f"intensity needs to be between 0 and 100, not {intensity}"
            )

        if intensity is not None and not intensity_as_pct and intensity > shocker_info.max_intensity:
            raise ValueError(
                f"shocker has max intensity of {shocker_info.max_intensity}, but was called with {intensity}"
            )

        if duration < 0:
            raise ValueError(
                f"duration cannot be negative, but was called with {duration}"
            )

        if duration > shocker_info.max_duration:
            raise ValueError(
                f"duration cannot exceed {shocker_info.max_duration}"
            )

        if min_duration is not None and not 0 <= min_duration <= duration:
            raise ValueError(
                f"Minimum duration must be between 0 and {duration}"
            )
        
        if intensity is None and min_intensity is not None:
            raise ValueError(
                "Intensity must be set to use minimum intensity random range"
            )

        if min_intensity is not None and not 0 <= min_intensity <= intensity:
            raise ValueError(
                f"Minimum intensity must be between 0 and {intensity}"
            )
        

        assert (intensity is None) == (operation == Operation.BEEP)
        assert operation in Operation

        body = {
            "AgentName": "Python-PiShock",
            "Operation": operation.value,
            "Duration": self._parse_duration(duration),
            "IntensityAsPercentage": intensity_as_pct
        }
        if intensity is not None:
            body["Intensity"] = intensity
        else:
            body["Intensity"] = 0

        if min_duration is not None:
            body["MinimumDuration"] = self._parse_duration(min_duration)
        else:
            body["MinimumDuration"] = 0

        if min_intensity is not None:
            body["MinimumIntensity"] = min_intensity
        else:
            body["MinimumIntensity"] = 0

        response = self.api.post(f"Shockers/{self.shocker_id}", body=body)

        if response.status_code != 204:
            if response.status_code in self._ERROR_MESSAGES_BY_CODE:
                raise self._ERROR_MESSAGES_BY_CODE[response.status_code](response.text)
            raise APIError(f"Unknown error {response.status_code}: {response.text}");

    def info(self) -> core.ApiV3ShockerInfo:
        """Get and cache detailed information about the shocker.

        Raises:
            NotAuthorizedError: Username/API key is wrong.
            UnknownError: The response is not JSON.
        """
        if self._cached_info is None:
            with self.api.translate_http_errors():
                response = self.api.get(f"Shockers/{self.shocker_id}")

            try:
                data = response.json()
            except json.JSONDecodeError:
                raise UnknownError(response.text)
            self._cached_info = core.ApiV3ShockerInfo.from_get_shockers_api_dict(data)

        return self._cached_info
