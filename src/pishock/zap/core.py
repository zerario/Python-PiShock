from __future__ import annotations

import dataclasses
from typing import Any


__version__ = "0.1.0"


class Shocker:

    """Base class for :class:`pishock.HTTPShocker` and :class:`pishock.SerialShocker`.

    Applications which only need access to :meth:`pishock.HTTPShocker.shock()`,
    :meth:`pishock.HTTPShocker.vibrate()`, :meth:`pishock.HTTPShocker.beep()` and
    :meth:`pishock.HTTPShocker.info()` (with :class:`BasicShockerInfo` only) can
    swap out a :class:`pishock.HTTPShocker` for a :class:`pishock.SerialShocker`
    (with only initialization changing) to support both APIs.
    """

    IS_SERIAL: bool

    def shock(self, *, duration: int | float, intensity: int) -> None:
        raise NotImplementedError  # pragma: no cover

    def vibrate(self, *, duration: int | float, intensity: int) -> None:
        raise NotImplementedError  # pragma: no cover

    def beep(self, duration: int | float) -> None:
        raise NotImplementedError  # pragma: no cover

    def info(self) -> BasicShockerInfo:
        raise NotImplementedError  # pragma: no cover


@dataclasses.dataclass
class BasicShockerInfo:
    """Basic information about a shocker.

    Used by :meth:`API.get_shockers()` and :meth:`SerialShocker.info()`. Calling
    :meth:`APIShocker.info()` returns a :class:`ShockerInfo` instance instead.

    Attributes:
        name: The name of this shocker in the web interface (or an autogenerated
              name for serial shockers).
        client_id: The ID of the PiShock this shocker belongs to.
        shocker_id: The ID of this shocker.
        is_paused: Whether the shocker is currently paused.
    """

    name: str
    client_id: int
    shocker_id: int
    is_paused: bool

    @classmethod
    def from_get_shockers_api_dict(
        cls, data: dict[str, Any], client_id: int
    ) -> BasicShockerInfo:
        return cls(
            name=data["name"],
            client_id=client_id,
            shocker_id=data["id"],
            is_paused=data["paused"],
        )
