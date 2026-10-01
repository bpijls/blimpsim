"""Recording labelled camera frames and browsing what was recorded."""
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.datasets import DatasetError, DatasetStore, get_dataset_store

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

NAME = Path(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")


class RecordIn(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    every: int = Field(1, ge=1, description="Keep every n-th camera frame")
    max_frames: int = Field(1000, ge=1, le=100_000)


async def _call(awaitable):
    try:
        return await awaitable
    except DatasetError as e:
        raise HTTPException(e.status, e.detail) from e


@router.get("")
async def list_datasets(store: DatasetStore = Depends(get_dataset_store)) -> list[dict]:
    return await _call(store.list())


@router.post("", status_code=201)
async def start_recording(
    payload: RecordIn, store: DatasetStore = Depends(get_dataset_store)
) -> dict:
    return await _call(store.start(payload.name, payload.every, payload.max_frames))


@router.post("/stop")
async def stop_recording(store: DatasetStore = Depends(get_dataset_store)) -> dict:
    return await _call(store.stop())


@router.get("/{name}/annotations")
async def annotations(name: str = NAME, store: DatasetStore = Depends(get_dataset_store)) -> dict:
    """The dataset's COCO annotations (people only; track ids and visibility included)."""
    return await _call(store.annotations(name))


@router.get("/{name}/images/{file}")
async def image(
    name: str = NAME,
    file: str = Path(pattern=r"^\d{6}\.jpg$"),
    store: DatasetStore = Depends(get_dataset_store),
) -> Response:
    return Response(await _call(store.image(name, file)), media_type="image/jpeg")
