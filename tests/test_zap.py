import os
import pytest
import dataclasses

from pishock.zap import Shocker


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
def shocker(credentials: Credentials) -> Shocker:
    return Shocker(
        username=credentials.username,
        apikey=credentials.apikey,
        sharecode=credentials.sharecode,
    )


@pytest.mark.vcr
def test_vibrate(shocker: Shocker):
    ok = shocker.vibrate(duration=1, intensity=2)
    assert ok


@pytest.mark.vcr
def test_shock(shocker: Shocker):
    ok = shocker.shock(duration=1, intensity=2)
    assert ok


@pytest.mark.vcr
def test_beep(shocker: Shocker):
    ok = shocker.beep(duration=1)
    assert ok


@pytest.mark.parametrize("duration", [-1, 16])
class TestInvalidDuration:
    def test_vibrate(self, shocker: Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between 0 and 15"):
            shocker.vibrate(duration=duration, intensity=2)

    def test_shock(self, shocker: Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between 0 and 15"):
            shocker.shock(duration=duration, intensity=2)

    def test_beep(self, shocker: Shocker, duration: int):
        with pytest.raises(ValueError, match="duration needs to be between 0 and 15"):
            shocker.beep(duration=duration)


@pytest.mark.parametrize("intensity", [-1, 101])
class TestInvalidIntensity:
    def test_vibrate(self, shocker: Shocker, intensity: int):
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.vibrate(duration=1, intensity=intensity)

    def test_shock(self, shocker: Shocker, intensity: int):
        with pytest.raises(ValueError, match="intensity needs to be between 0 and 100"):
            shocker.shock(duration=1, intensity=intensity)


def test_beep_no_intensity(shocker: Shocker):
    with pytest.raises(TypeError):
        shocker.beep(duration=1, intensity=2)


@pytest.mark.vcr(filter_post_data_parameters=[])
def test_unauthorized(credentials: Credentials):
    shocker = Shocker(username=credentials.username, apikey="wrong", sharecode="wrong")
    assert not shocker.shock(duration=1, intensity=2)


@pytest.mark.vcr(filter_post_data_parameters=[("Apikey", "PISHOCK-APIKEY")])
def test_unknown_share_code(credentials: Credentials):
    shocker = Shocker(
        username=credentials.username,
        apikey=credentials.apikey,
        sharecode="wrong",
    )
    assert not shocker.shock(duration=1, intensity=2)
