import os
import pytest
import dataclasses

from pishock import zap


@dataclasses.dataclass
class Credentials:
    username: str
    apikey: str
    sharecode: str


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_post_data_parameters": [
            ("Code", "PISHOCK-SHARECODE"),
            ("Apikey", "PISHOCK-APIKEY"),
        ]
    }


@pytest.fixture
def credentials() -> Credentials:
    """Get credentials to run tests.

    By default, uses the same fake credentials that tests have in theis stored
    responses in tests/cassettes.

    To re-generate the cassetes, provide valid credentials in your environment:

    export PISHOCK_USERNAME=...
    export PISHOCK_APIKEY=...
    export PISHOCK_SHARECODE=...

    And then run:

    tox -e py311 -- --vcr-record=once
    """
    return Credentials(
        username=os.environ.get("PISHOCK_USERNAME", "Zerario"),
        apikey=os.environ.get("PISHOCK_APIKEY", "PISHOCK-APIKEY"),
        sharecode=os.environ.get("PISHOCK_SHARECODE", "PISHOCK-SHARECODE"),
    )


@pytest.fixture
def account(credentials: Credentials) -> zap.Account:
    return zap.Account(username=credentials.username, apikey=credentials.apikey)


@pytest.fixture
def shocker(account: zap.Account, credentials: Credentials) -> zap.Shocker:
    s = zap.Shocker(account=account, sharecode=credentials.sharecode)
    info = s.info()
    if info.is_paused:
        s.pause(False)
    yield s
    s.pause(info.is_paused)


def test_account_repr(account: zap.Account, credentials: Credentials):
    assert repr(account) == f"Account(username='{credentials.username}', apikey=...)"


@pytest.mark.vcr
def test_vibrate(shocker: zap.Shocker):
    shocker.vibrate(duration=1, intensity=2)


@pytest.mark.vcr
def test_shock(shocker: zap.Shocker):
    shocker.shock(duration=1, intensity=2)


@pytest.mark.vcr
def test_beep(shocker: zap.Shocker):
    shocker.beep(duration=1)


@pytest.mark.parametrize("duration", [-1, 16])
class TestInvalidDuration:
    def test_vibrate(self, shocker: zap.Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between 0 and 15"):
            shocker.vibrate(duration=duration, intensity=2)

    def test_shock(self, shocker: zap.Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between 0 and 15"):
            shocker.shock(duration=duration, intensity=2)

    def test_beep(self, shocker: zap.Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between 0 and 15"):
            shocker.beep(duration=duration)


@pytest.mark.parametrize("intensity", [-1, 101])
class TestInvalidIntensity:
    def test_vibrate(self, shocker: zap.Shocker, intensity: int):
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.vibrate(duration=1, intensity=intensity)

    def test_shock(self, shocker: zap.Shocker, intensity: int):
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.shock(duration=1, intensity=intensity)


def test_beep_no_intensity(shocker: zap.Shocker):
    with pytest.raises(TypeError):
        shocker.beep(duration=1, intensity=2)


@pytest.mark.vcr(filter_post_data_parameters=[])
def test_unauthorized(credentials: Credentials):
    account = zap.Account(username=credentials.username, apikey="wrong")
    shocker = zap.Shocker(account=account, sharecode="wrong")
    with pytest.raises(zap.NotAuthorizedError):
        shocker.shock(duration=1, intensity=2)


@pytest.mark.vcr(filter_post_data_parameters=[("Apikey", "PISHOCK-APIKEY")])
def test_unknown_share_code(account: zap.Account):
    shocker = zap.Shocker(account=account, sharecode="wrong")
    with pytest.raises(zap.ShareCodeNotFoundError):
        shocker.shock(duration=1, intensity=2)


@pytest.mark.vcr
@pytest.mark.parametrize("pause", [True, False])
def test_pause(shocker: zap.Shocker, pause: bool):
    shocker.pause(pause)
    assert shocker.info().is_paused == pause
