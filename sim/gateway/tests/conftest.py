import os

os.environ["SIM_SECRET"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.link import SimLink  # noqa: E402
from app.recorder import Recorder  # noqa: E402

AUTH = {"X-Sim-Secret": "test-secret"}


@pytest.fixture
def client(tmp_path):
    main.link = SimLink()
    main.recorder = Recorder(str(tmp_path))
    main.link.on_frame = lambda meta, jpeg: main.recorder.add(meta, jpeg)
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def sim(client):
    """A fake Godot simulator connected to the gateway."""
    with client.websocket_connect("/sim?secret=test-secret") as socket:
        socket.send_json({"type": "hello", "godot": "test"})
        yield socket
