import pytest

from app.main import app
from app.services.datasets import DatasetError, get_dataset_store


class FakeStore:
    def __init__(self) -> None:
        self.started: list[tuple] = []

    async def list(self):
        return [{"name": "walk", "frames": 2, "recording": False}]

    async def start(self, name, every, max_frames):
        if name == "taken":
            raise DatasetError(409, "dataset 'taken' already exists")
        self.started.append((name, every, max_frames))
        return {"name": name, "frames": 0, "max_frames": max_frames}

    async def stop(self):
        raise DatasetError(409, "Nothing is being recorded")

    async def annotations(self, name):
        return {"images": [], "annotations": [], "categories": [{"id": 1, "name": "person"}]}

    async def image(self, name, file):
        return b"jpeg"


@pytest.fixture
def store():
    fake = FakeStore()
    app.dependency_overrides[get_dataset_store] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_dataset_store, None)


async def test_list_datasets(client, store):
    assert (await client.get("/api/datasets")).json()[0]["name"] == "walk"


async def test_start_recording_applies_defaults(client, store):
    res = await client.post("/api/datasets", json={"name": "walk-2"})
    assert res.status_code == 201
    assert store.started == [("walk-2", 1, 1000)]


async def test_gateway_errors_keep_their_status(client, store):
    assert (await client.post("/api/datasets", json={"name": "taken"})).status_code == 409
    assert (await client.post("/api/datasets/stop")).status_code == 409


@pytest.mark.parametrize("name", ["../etc", "Has Spaces", ""])
async def test_bad_dataset_names_are_rejected(client, store, name):
    assert (await client.post("/api/datasets", json={"name": name})).status_code == 422


async def test_image_is_served_as_jpeg(client, store):
    res = await client.get("/api/datasets/walk/images/000001.jpg")
    assert res.content == b"jpeg"
    assert res.headers["content-type"] == "image/jpeg"
    assert (await client.get("/api/datasets/walk/images/passwd")).status_code == 422
