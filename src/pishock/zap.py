import enum

import requests

class Operation(enum.Enum):

    SHOCK = 0
    VIBRATE = 1
    BEEP = 2


class APIError(Exception):
    """Base class for all errors returned by the API."""


class ShareCodeAlreadyUsedError(APIError):
    """API returned: This share code has already been used by somebody else."""


class ShareCodeNotFoundError(APIError):
    """API returned: This code doesn't exist."""


class NotAuthorizedError(APIError):
    """API returned: Not Authorized."""


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


class Shocker:

    NAME = "random"
    SUCCESS_MESSAGES = [
        "Operation Succeeded.",
        "Operation Attempted.",
    ]
    ERROR_MESSAGES = {
        "Not Authorized.": NotAuthorizedError,
        "This code doesn't exist.": ShareCodeNotFoundError,
        "This share code has already been used by somebody else.":
            ShareCodeAlreadyUsedError,
    }

    def __init__(self, account: Account, sharecode: str) -> None:
        self.account = account
        self.sharecode = sharecode

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

        response = requests.post(
            "https://do.pishock.com/api/apioperate", json=params
        )
        response.raise_for_status()

        if response.text in self.SUCCESS_MESSAGES:
            pass
        elif response.text in self.ERROR_MESSAGES:
            raise self.ERROR_MESSAGES[response.text](response.text)
        else:
            raise UnknownError(response.text)
