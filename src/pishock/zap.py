import requests

class Shocker:

    NAME = "random"
    OP_SHOCK = 0
    OP_VIBRATE = 1
    OP_BEEP = 2

    SUCCESS_MESSAGES = [
        "Operation Succeeded.",
        "Operation Attempted.",
    ]

    def __init__(self, username: str, apikey: str, sharecode: str) -> None:
        self.username = username
        self.apikey = apikey
        self.sharecode = sharecode

    def shock(self, duration: int, intensity: int) -> bool:
        return self._call(self.OP_SHOCK, duration=duration, intensity=intensity)

    def vibrate(self, duration: int, intensity: int) -> bool:
        return self._call(self.OP_VIBRATE, duration=duration, intensity=intensity)

    def beep(self, duration: int) -> bool:
        return self._call(self.OP_BEEP, duration=duration, intensity=None)

    def _call(self, operation: int, duration: int, intensity: int | None) -> bool:
        if not 0 <= duration <= 15:
            raise ValueError(f"duration needs to be between 0 and 15, not {duration}")
        if intensity is not None and not 0 <= intensity <= 100:
            raise ValueError(
                f"intensity needs to be between 0 and 100, not {intensity}"
            )

        assert (intensity is None) == (operation == self.OP_BEEP)
        assert operation in [self.OP_BEEP, self.OP_SHOCK, self.OP_VIBRATE]

        params = {
            "Username": self.username,
            "Name": self.NAME,
            "Code": self.sharecode,
            "Apikey": self.apikey,
            "Duration": duration,
            "Op": operation,
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
