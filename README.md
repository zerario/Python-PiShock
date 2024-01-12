# PiShock for Python

![Python PiShock Logo](https://raw.githubusercontent.com/zerario/Python-PiShock/main/docs/_static/logo.png)

The *bestest* Python PiShock API wrapper and CLI!

> *If you have no idea what [PiShock](https://pishock.com/#/?campaign=zerario) is: I'm left wondering how you found this, but it's an ecosystem around using dog shock collars on humans (clearly the better way to use them!).*

- Pythonic, [**easy-to-use API**](https://python-pishock.readthedocs.io/en/latest/api.html).
- Beautiful [**command-line interface**](https://python-pishock.readthedocs.io/en/latest/cli.html) to [send shocks/vibrates/beeps](https://python-pishock.readthedocs.io/en/latest/cli.html#basic-usage), [manage share codes](https://python-pishock.readthedocs.io/en/latest/cli.html#managing-share-codes), keep someone on their toes with [**random shocks**](https://python-pishock.readthedocs.io/en/latest/cli.html#random-mode), interfacing with the PiShock [over **USB/serial**](https://python-pishock.readthedocs.io/en/latest/cli.html#serial-usage), [upgrading firmware](https://python-pishock.readthedocs.io/en/latest/cli.html#firmware-upgrade), and more!
- **Ticks the boxes**: Support for **mini-shocks**, getting **shocker info**, and various other undocumented API features. If it's possible to do, this project probably supports it.
- **Local shocking**: Drop-in support for the **USB serial API** instead of HTTP.
- **Battle-tested**: I accidentally shocked my balls while developing so you don't have to (I *wish* this was a joke).
- **High-quality, modern** codebase: Type annotations in [Mypy strict mode](https://mypy.readthedocs.io/en/stable/), Linting/Formatting via [Ruff](https://docs.astral.sh/ruff/), Automated tests with [pytest](https://docs.pytest.org/).
- **Made with love**: Decent test coverage, [CI](https://github.com/zerario/Python-PiShock/actions), [nice documentation](https://python-pishock.readthedocs.io/), …. — I love zappies and I love going the extra mile!
- **Almost official**: While this is not an official pishock.com product, I'm the same person who developed the code running on your PiShock that's sending out the shocks.
- **Runs anywhere**: Tested on CPython 3.8 to 3.12, on Windows, macOS and Linux. Possibly CircuitPython soon?

---

Using the CLI to send a vibrate (or a shock, if you dare):

```console
$ pip install pishock
[...]

$ pishock init
👤 PiShock username (your own username): Zerario
🔑 PiShock API key (https://pishock.com/#/account): 964f1513-c76a-48cc-82d4-41e757d4eb04
✅ Credentials saved.

$ pishock code add my-shocker ABCDEF12345
✅  my-shocker    ABCDEF12345

$ pishock vibrate my-shocker --duration 1 --intensity 20
📳
```

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
