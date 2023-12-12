# Reference

## Data structures

```{eval-rst}
.. module:: pishock.zap
   :no-index:

.. autoclass:: BasicShockerInfo
.. autoclass:: ShockerInfo

.. autoclass:: Operation
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

### Errors

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

```{eval-rst}
.. autoclass:: pishock.zap.SerialShocker
   :members:

.. autoclass:: pishock.serialapi.SerialAPI
   :members:
```
