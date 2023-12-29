# Reference

For convenience, all classes documented here are re-exported in the
flat ``pishock`` namespace.

## Basic Data structures

```{eval-rst}
.. autoclass:: pishock.zap.core.Shocker
.. autoclass:: pishock.zap.core.BasicShockerInfo
```

## API access

```{eval-rst}
.. module:: pishock.zap.httpapi
   :no-index:

.. autoclass:: DetailedShockerInfo

.. autoclass:: PiShockAPI
   :members:

.. autoclass:: HTTPShocker
   :members:
```

(http-api-errors)=
### API Errors

```{eval-rst}
.. module:: pishock.zap.httpapi
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

The {class}`pishock.zap.serialapi.SerialShocker` shares a common
{class}`pishock.zap.core.Shocker` base with {class}`pishock.zap.httpapi.HTTPShocker`. It can
thus act as a drop-in replacement for using the HTTP API, and is recommended for
most usage.

```{eval-rst}
.. autoclass:: pishock.zap.serialapi.SerialShocker
   :members:
```

### Low-level API

The low-level {class}`pishock.zap.serialapi.SerialAPI` class can be used to send raw
serial commands to the PiShock.

```{eval-rst}
.. module:: pishock.zap.serialapi
   :no-index:

.. autoclass:: SerialAutodetectError
.. autoclass:: ShockerNotFoundError
.. autoclass:: SerialOperation
.. autoclass:: SerialAPI
   :members:
```
