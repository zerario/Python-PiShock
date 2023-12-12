# Reference

## Basic Data structures

```{eval-rst}
.. module:: pishock.zap
   :no-index:

.. autoclass:: Shocker
.. autoclass:: BasicShockerInfo
.. autoclass:: ShockerInfo
```

## API access

```{eval-rst}
.. module:: pishock.zap
   :no-index:

.. autoclass:: API
   :members:

.. autoclass:: APIShocker
   :members:
```

### API Errors

```{eval-rst}
.. module:: pishock.zap
   :no-index:

.. autoexception:: APIError

.. autoexception:: HTTPError
.. autoexception:: UnknownError

.. autoexception:: OperationNotAllowedError
.. autoexception:: BeepNotAllowedError
.. autoexception:: VibrateNotAllowedError
.. autoexception:: ShockNotAllowedError

.. autoexception:: NotAuthorizedError
.. autoexception:: ShockerPausedError
.. autoexception:: DeviceInUseError
.. autoexception:: DeviceNotConnectedError

.. autoexception:: ShareCodeAlreadyUsedError
.. autoexception:: ShareCodeNotFoundError
```

## Serial

### High-level API

The {class}`pishock.zap.SerialShocker` shares a common
{class}`pishock.zap.Shocker` base with {class}`pishock.zap.APIShocker`. It can
thus act as a drop-in replacement for using the HTTP API, and is recommended for
most usage.

```{eval-rst}
.. autoclass:: pishock.zap.SerialShocker
   :members:
```

### Low-level API

The low-level {class}`pishock.serialapi.SerialAPI` class can be used to send raw
serial commands to the PiShock.

```{eval-rst}
.. autoclass:: pishock.serialapi.AutodetectError
.. autoclass:: pishock.serialapi.SerialOperation
.. autoclass:: pishock.serialapi.SerialAPI
   :members:
```
