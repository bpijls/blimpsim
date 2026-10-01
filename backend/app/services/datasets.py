"""Recorded datasets live on the GPU host; this is the api's window onto them."""
from functools import lru_cache

import httpx

from app.config import settings


class DatasetError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class DatasetStore:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            base_url=settings.sim_gateway_url,
            headers={"X-Sim-Secret": settings.sim_secret},
            timeout=30.0,
        )

    async def list(self) -> list[dict]:
        return (await self._request("GET", "/datasets")).json()

    async def start(self, name: str, every: int, max_frames: int) -> dict:
        body = {"name": name, "every": every, "max_frames": max_frames}
        return (await self._request("POST", "/datasets", json=body)).json()

    async def stop(self) -> dict:
        return (await self._request("POST", "/datasets/stop")).json()

    async def annotations(self, name: str) -> dict:
        return (await self._request("GET", f"/datasets/{name}/annotations")).json()

    async def image(self, name: str, file: str) -> bytes:
        return (await self._request("GET", f"/datasets/{name}/images/{file}")).content

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            res = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise DatasetError(503, f"simulator gateway: {e}") from e
        if res.is_error:
            detail = res.json().get("detail", res.text) if res.content else res.reason_phrase
            raise DatasetError(res.status_code, str(detail))
        return res


@lru_cache
def get_dataset_store() -> DatasetStore:
    return DatasetStore()
