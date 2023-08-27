import enum

import requests

class Operation(enum.Enum):

    SHOCK = 0
    VIBRATE = 1
    BEEP = 2


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

    def __init__(self, account: Account, sharecode: str) -> None:
        self.account = account
        self.sharecode = sharecode

    def shock(self, duration: int, intensity: int) -> bool:
        return self._call(Operation.SHOCK, duration=duration, intensity=intensity)

    def vibrate(self, duration: int, intensity: int) -> bool:
        return self._call(Operation.VIBRATE, duration=duration, intensity=intensity)

    def beep(self, duration: int) -> bool:
        return self._call(Operation.BEEP, duration=duration, intensity=None)

    def _call(self, operation: Operation, duration: int, intensity: int | None) -> bool:
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

        if response.status_code == 200 and response.text in self.SUCCESS_MESSAGES:
            return True

        print(f"{response.status_code}: {response.text}")
        return False
