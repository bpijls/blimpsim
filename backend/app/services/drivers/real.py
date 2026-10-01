"""Placeholder for the hardware blimp.

Its steering API is not specified yet. When it is, this class translates
BlimpCommand into whatever the hardware expects and its telemetry and video
into the shared contracts; nothing above the driver layer should need to change.
"""
from collections.abc import AsyncIterator

from app.contracts import BlimpCommand, BlimpProfile, World
from app.services.drivers.base import BlimpDriver, DriverUnavailable

NOT_YET = "the real blimp's API is not known yet"


class RealDriver(BlimpDriver):
    name = "real"

    async def status(self) -> dict:
        return {"driver": self.name, "reachable": False, "detail": NOT_YET}

    async def load(self, world: World, profile: BlimpProfile, mode: str) -> None:
        raise DriverUnavailable("a real blimp cannot be placed in a generated world")

    async def send(self, command: BlimpCommand) -> None:
        raise DriverUnavailable(NOT_YET)

    async def telemetry(self) -> AsyncIterator[dict]:
        raise DriverUnavailable(NOT_YET)
        yield {}  # pragma: no cover — makes this an async generator

    async def camera(self) -> AsyncIterator[bytes]:
        raise DriverUnavailable(NOT_YET)
        yield b""  # pragma: no cover
