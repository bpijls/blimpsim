"""The seam between the api and whichever blimp it is steering.

Controllers and the monitor only ever talk to a BlimpDriver, so the same code
runs against the simulator now and the real blimp later.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.contracts import BlimpCommand, BlimpProfile, World


class DriverUnavailable(Exception):
    """The blimp (or its simulator) cannot be reached or cannot do this."""


class BlimpDriver(ABC):
    name: str

    @abstractmethod
    async def status(self) -> dict:
        """Connection state; never raises."""

    @abstractmethod
    async def load(self, world: World, profile: BlimpProfile, mode: str) -> None:
        """Put the blimp in `world`. Only a simulated blimp can do this."""

    @abstractmethod
    async def send(self, command: BlimpCommand) -> None: ...

    @abstractmethod
    def telemetry(self) -> AsyncIterator[dict]:
        """Telemetry messages (contracts/telemetry.schema.json) until the link drops."""

    @abstractmethod
    def camera(self) -> AsyncIterator[bytes]:
        """The onboard camera as multipart/x-mixed-replace chunks, boundary `frame`."""
