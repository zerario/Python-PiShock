__version__ = "1.0.0"

from .zap.core import (
    Shocker as Shocker,
    BasicShockerInfo as BasicShockerInfo,
)

from pishock.zap.httpapi import (
    HTTPShocker as HTTPShocker,
    APIError as APIError,
    ShareCodeAlreadyUsedError as ShareCodeAlreadyUsedError,
    ShareCodeNotFoundError as ShareCodeNotFoundError,
    NotAuthorizedError as NotAuthorizedError,
    ShockerPausedError as ShockerPausedError,
    DeviceNotConnectedError as DeviceNotConnectedError,
    DeviceInUseError as DeviceInUseError,
    OperationNotAllowedError as OperationNotAllowedError,
    ShockNotAllowedError as ShockNotAllowedError,
    VibrateNotAllowedError as VibrateNotAllowedError,
    BeepNotAllowedError as BeepNotAllowedError,
    HTTPError as HTTPError,
    UnknownError as UnknownError,
)

from pishock.zap.serialapi import (
    SerialShocker as SerialShocker,
    SerialOperation as SerialOperation,
    SerialAPI as SerialAPI,
)
