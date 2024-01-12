# Python API

## Overview

Due to supporting both the HTTP and serial APIs, and due to the goal of exposing
everything that's deemed useful, the Python API is a bit more complex than you
might have expected. Here is a (simplified) bird's eye view:

```{mermaid}
classDiagram
    direction TD

    class Shocker {
        +shock()
        +vibrate()
        +beep()
        +info()
    }

    class HTTPShocker {
        +sharecode
        +name
        +log_name

        +pause()
    }

    class SerialShocker {
        +shocker_id

        +end()
    }

    class PiShockAPI {
        +username
        +api_key

        +get_shockers()
        +request()
        +verify_credentials()
    }

    class SerialAPI {
        +dev

        +...()
    }

    PiShockAPI -- HTTPShocker : api.shocker()
    Shocker <|-- HTTPShocker
    SerialAPI -- SerialShocker : api.shocker()
    Shocker <|-- SerialShocker
```

```{eval-rst}
.. module:: pishock.zap.core
   :no-index:
```

For sending shocks/vibrates/beeps, you will have to get a {py:class}`Shocker`
based on either the HTTP API or a PiShock attched via USB serial.

## Getting a Shocker via HTTP API

```{eval-rst}
.. module:: pishock.zap.httpapi
   :no-index:
```

To get a shocker using the PiShock.com HTTP API, you will need to:

- Create a {py:class}`PiShockAPI` (providing a username and API key)
- Call {meth}`PiShockAPI.shocker()` on it with a share code, in order to get a {class}`HTTPShocker`

thus:

```python
from pishock import PiShockAPI

username = "..."   # from pishock.com
api_key = "..."    # https://pishock.com/#/account
sharecode = "..."  # https://pishock.com/#/control (share button)

api = PiShockAPI(username, api_key)
shocker = api.shocker(sharecode)
```

## Getting a Shocker via Serial API

```{eval-rst}
.. module:: pishock.zap.serialapi
   :no-index:
```

To get a shocker for a PiShock device attached via USB, you will need to:

- Create a {class}`SerialAPI` (providing a device path or relying on autodetection)
- Call {meth}`SerialAPI.shocker()` on it with a shocker ID, in order to get a {class}`SerialShocker`

thus:

```python
from pishock import SerialAPI

shocker_id = 1234  # https://pishock.com/#/control (cogwheel button)

api = SerialAPI()
shocker = api.shocker(shocker_id)
```

```{eval-rst}
.. module:: pishock.zap
   :no-index:
```

## Using the Shocker

Once you did so, you will be able to call {meth}`Shocker.vibrate()`,
{meth}`Shocker.shock()` and {meth}`Shocker.beep()` on them for the basic
operations:

```python
shocker.vibrate(duration=1, intensity=10)
```

A {class}`HTTPShocker <httpapi.HTTPShocker>` also supports {meth}`.pause()
<httpapi.HTTPShocker.pause()>` in order to pause/unpause the shocker.

Finally, both classes support calling {meth}`Shocker.info()` to get info
about a shocker. However, note that the {class}`SerialShocker <serialapi.SerialShocker>` will only provide
{class}`BasicShockerInfo <core.BasicShockerInfo>`, while the HTTP API provides
{class}`DetailedShockerInfo <httpapi.DetailedShockerInfo>` (which adds
{attr}`max_intensity <httpapi.DetailedShockerInfo.max_intensity>` and
{attr}`max_duration <httpapi.DetailedShockerInfo.max_duration>`).

```python
>>> serial_shocker.info()
BasicShockerInfo(
    name='Serial shocker (/dev/ttyUSB0)',
    client_id=621,
    shocker_id=1234,
    is_paused=False,
)

>>> http_shocker.info()
DetailedShockerInfo(
    name='left',
    client_id=621,
    shocker_id=1234,
    is_paused=False,
    max_intensity=100,
    max_duration=15,
)
```

## Error handling

For the HTTP API, various errors can be returned from the API (sometimes in
subtly different ways). This library tries to convert all of those into
[sensible Python exceptions](#http-api-errors), which all inherit from
{class}`httpapi.APIError`. Additionally, {class}`httpapi.UnknownError` is raised
if the response couldn't be parsed, and {class}`httpapi.HTTPError` if an API
endpoint returned an unexpected HTTP status.

For the serial API, {class}`serialapi.SerialAutodetectError` is raised if device
autodetection failed (multiple potential PiShocks found, or none at all). If a
shocker gets requested for an ID that does not exist,
{class}`serialapi.ShockerNotFoundError` is raised. Additionally,
[`serial.SerialException`](https://pyserial.readthedocs.io/en/latest/pyserial_api.html#exceptions)
might be raised by the underlying PySerial package.

See the [reference documentation](#reference) for more specific documentation
about which methods are expected to raise which exceptions.

## Further operations

Further operations not connected to a single shocker are available via the
{class}`httpapi.PiShockAPI` and {class}`serialapi.SerialAPI` classes directly, see
their reference documentation for details:


```{eval-rst}
.. module:: pishock.zap.httpapi
   :no-index:
```

- HTTP API
  - [Getting all shockers for a given PiShock](#PiShockAPI.get_shockers())
  - [Verifying that credentials are valid](#PiShockAPI.verify_credentials())

```{eval-rst}
.. module:: pishock.zap.serialapi
   :no-index:
```

- Serial API
  - [Adding](#SerialAPI.add_network()) and [removing](#SerialAPI.remove_network()) networks, or [temporarily connecting](#SerialAPI.try_connect()) to one
  - [Restarting](#SerialAPI.restart()) the PiShock
  - [Getting info](#SerialAPI.info()), [waiting for info](#SerialAPI.wait_info()) without requesting it, and [decoding an info line](#SerialAPI.decode_info())
  - [Monitoring](#SerialAPI.monitor()) raw serial data
