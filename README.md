# PiShock for Python

![Python PiShock Logo](docs/_static/logo.png)

The *bestest* Python PiShock API wrapper and CLI!

> *If you have no idea what [PiShock](https://pishock.com/#/?campaign=zerario) is: I'm left wondering how you found this, but it's an ecosystem around using dog shock collars on humans (clearly the better way to use them!).*

- Pythonic, **easy-to-use API**.
- Beautiful **command-line interface** to send shocks/vibrates/beeps, manage share codes, keep someone on their toes with **random shocks**, interfacing with the PiShock over **USB/serial**, and more!
- **Ticks the boxes**: Support for **mini-shocks**, getting **shocker info**, and various other undocumented API features. If it's possible to do, this project probably supports it.
- **Local shocking**: Drop-in support for the **USB serial API** instead of HTTP.
- **Battle-tested**: I accidentally shocked my balls while developing so you don't have to (I *wish* this was a joke).
- **High-quality, modern** codebase: Type annotations in [Mypy strict mode](https://mypy.readthedocs.io/en/stable/), Linting/Formatting via [Ruff](https://docs.astral.sh/ruff/), Automated tests with [pytest](https://docs.pytest.org/).
- **Made with love**: Decent test coverage, CI, nice documentation, …. — I love zappies and I love going the extra mile!
- **Almost official**: While this is not an official pishock.com product, I'm the same person who developed the code running on your PiShock that's sending out the shocks.

---

Using the CLI to send a vibrate (or a shock, if you dare):

- `pip install pishock`
- Get your API key [from the website](https://pishock.com/#/account)
- `pishock init`
- Generate a share code [on the website](https://pishock.com/#/control)
- `pishock code add my-shocker ABCDEF12345`
- `pishock vibrate my-shocker --duration 1 --intensity 10`

Or via the Python API:

```python
from pishock import PiShockAPI

username = "..."   # from pishock.com
api_key = "..."    # https://pishock.com/#/account
sharecode = "..."  # https://pishock.com/#/control (share button)

api = PiShockAPI(username, api_key)
shocker = api.shocker(sharecode)
shocker.vibrate(duration=1, intensity=10)
```

For serial USB usage:

```python
from pishock import SerialAPI

shocker_id = 1234  # https://pishock.com/#/control (cogwheel button)

api = SerialAPI()
shocker = api.shocker(shocker_id)
shocker.vibrate(duration=1, intensity=10)
```

For more, see the [documentation](https://python-pishock.readthedocs.io/#full-documentation).
