"""Drives the simulated blimp through the gateway on the GPU host."""
import json
from collections.abc import AsyncIterator

import httpx
import websockets

from app.config import settings
from app.contracts import BlimpCommand, BlimpProfile, World
from app.services.drivers.base import BlimpDriver, DriverUnavailable


class SimDriver(BlimpDriver):
    name = "sim"

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            base_url=settings.sim_gateway_url,
            headers={"X-Sim-Secret": settings.sim_secret},
            timeout=5.0,
        )

    async def status(self) -> dict:
        try:
            res = await self._http.get("/healthz")
            res.raise_for_status()
        except httpx.HTTPError as e:
            return {"driver": self.name, "reachable": False, "detail": str(e)}
        return {"driver": self.name, "reachable": True, **res.json()}

    async def load(self, world: World, profile: BlimpProfile, mode: str) -> None:
        await self._post(
            "/load",
            {
                "world": world.model_dump(mode="json"),
                "profile": profile.model_dump(mode="json"),
                "mode": mode,
            },
        )

    async def send(self, command: BlimpCommand) -> None:
        await self._post("/command", command.model_dump(exclude_none=True))

    async def telemetry(self) -> AsyncIterator[dict]:
        base = settings.sim_gateway_url.replace("http", "ws", 1)
        try:
            async with websockets.connect(
                f"{base}/telemetry?secret={settings.sim_secret}"
            ) as socket:
                async for message in socket:
                    yield json.loads(message)
        except (OSError, websockets.WebSocketException) as e:
            raise DriverUnavailable(f"simulator gateway: {e}") from e

    async def camera(self) -> AsyncIterator[bytes]:
        try:
            async with self._http.stream("GET", "/stream.mjpg", timeout=None) as res:
                res.raise_for_status()
                async for chunk in res.aiter_bytes():
                    yield chunk
        except httpx.HTTPError as e:
            raise DriverUnavailable(f"simulator gateway: {e}") from e

    async def _post(self, path: str, body: dict) -> None:
        try:
            res = await self._http.post(path, json=body)
            res.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise DriverUnavailable(e.response.json().get("detail", str(e))) from e
        except httpx.HTTPError as e:
            raise DriverUnavailable(f"simulator gateway: {e}") from e
