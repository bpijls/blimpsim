import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import AUTH

TELEMETRY = {"t": 1.0, "blimp": {"position": [0, 5, 0]}, "people": []}


def send_frame(sim, number: int, jpeg: bytes) -> None:
    sim.send_json({"type": "frame", "frame": number, "tick": number, "telemetry": TELEMETRY})
    sim.send_bytes(jpeg)


def test_health_reports_simulator_connection(client):
    assert client.get("/healthz").json()["sim_connected"] is False
    with client.websocket_connect("/sim?secret=test-secret") as sim:
        sim.send_json({"type": "hello", "godot": "4.5"})
        client.get("/healthz")  # lets the hello be processed
        health = client.get("/healthz").json()
        assert health["sim_connected"] is True
        assert health["sim"]["godot"] == "4.5"


@pytest.mark.parametrize("path", ["/telemetry", "/frame.jpg"])
def test_reads_need_the_secret(client, path):
    assert client.get(path).status_code == 401


def test_sim_socket_needs_the_secret(client):
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/sim?secret=wrong"):
            pass
    assert e.value.code == 4401


def test_command_without_simulator_is_503(client):
    assert client.post("/command", json={"surge": 1}, headers=AUTH).status_code == 503


def test_command_reaches_simulator(client, sim):
    assert client.post("/command", json={"surge": 0.5}, headers=AUTH).status_code == 200
    assert sim.receive_json() == {"surge": 0.5, "type": "command"}


def test_load_reaches_simulator(client, sim):
    body = {"world": {"seed": 1}, "profile": {}, "mode": "realtime"}
    assert client.post("/load", json=body, headers=AUTH).status_code == 200
    assert sim.receive_json() == {"type": "load", **body}


def test_load_is_replayed_to_a_restarted_simulator(client):
    body = {"world": {"seed": 1}, "profile": {}, "mode": "realtime"}
    with client.websocket_connect("/sim?secret=test-secret") as first:
        client.post("/load", json=body, headers=AUTH)
        first.receive_json()
    with client.websocket_connect("/sim?secret=test-secret") as second:
        second.send_json({"type": "hello"})
        assert second.receive_json() == {"type": "load", **body}


def test_frame_is_paired_with_its_header(client, sim):
    assert client.get("/frame.jpg", headers=AUTH).status_code == 404
    send_frame(sim, 0, b"jpeg-zero")
    send_frame(sim, 1, b"jpeg-one")
    client.get("/healthz")
    res = client.get("/frame.jpg", headers=AUTH)
    assert res.content == b"jpeg-one"
    assert res.headers["content-type"] == "image/jpeg"
    assert client.get("/telemetry", headers=AUTH).json() == TELEMETRY


def test_telemetry_is_fanned_out_to_subscribers(client, sim):
    with client.websocket_connect("/telemetry?secret=test-secret") as a:
        with client.websocket_connect("/telemetry?secret=test-secret") as b:
            sim.send_json({"type": "telemetry", "telemetry": TELEMETRY})
            assert a.receive_json() == TELEMETRY
            assert b.receive_json() == TELEMETRY


def test_frames_from_the_previous_world_are_dropped_while_loading(client, sim):
    body = {"world": {"seed": 2}, "profile": {}, "mode": "lockstep"}
    client.post("/load", json=body, headers=AUTH)
    send_frame(sim, 99, b"stale")  # was already on its way when the load was sent
    client.get("/healthz")
    assert client.get("/frame.jpg", headers=AUTH).status_code == 404

    sim.send_json({"type": "loaded", "mode": "lockstep"})
    send_frame(sim, 0, b"fresh")
    client.get("/healthz")
    assert client.get("/frame.jpg", headers=AUTH).content == b"fresh"


# ── Lockstep ─────────────────────────────────────────────────────────────────


def test_lockstep_step_is_answered_with_the_next_frame(client, sim):
    send_frame(sim, 0, b"first")
    with client.websocket_connect("/lockstep?secret=test-secret") as env:
        env.send_json({"type": "observe"})
        assert env.receive_json()["frame"] == 0
        assert env.receive_bytes() == b"first"

        env.send_json({"type": "step", "command": {"surge": 1}, "ticks": 6})
        assert sim.receive_json() == {"type": "step", "command": {"surge": 1}, "ticks": 6}
        send_frame(sim, 1, b"second")
        assert env.receive_json()["frame"] == 1
        assert env.receive_bytes() == b"second"


def test_lockstep_reset_waits_for_a_new_frame_even_if_its_number_repeats(client, sim):
    send_frame(sim, 0, b"old")
    with client.websocket_connect("/lockstep?secret=test-secret") as env:
        env.send_json({"type": "reset"})
        assert sim.receive_json() == {"type": "reset"}
        send_frame(sim, 0, b"fresh")  # the simulator restarts its numbering
        assert env.receive_json()["frame"] == 0
        assert env.receive_bytes() == b"fresh"


def test_lockstep_without_simulator_reports_an_error(client):
    with client.websocket_connect("/lockstep?secret=test-secret") as env:
        env.send_json({"type": "step", "ticks": 1})
        assert env.receive_json()["type"] == "error"


# ── Datasets ─────────────────────────────────────────────────────────────────

CAMERA = {"width": 640, "height": 480, "fov_y_deg": 60, "position": [0, 5, 0],
          "rotation": [0, 0, 0, 1]}


def send_labelled(sim, number: int, people: list[dict]) -> None:
    labels = {"frame": number, "t": number / 15, "camera": CAMERA, "people": people}
    sim.send_json({"type": "frame", "frame": number, "telemetry": TELEMETRY, "labels": labels})
    sim.send_bytes(b"jpeg-%d" % number)


def test_recording_writes_a_coco_dataset(client, sim):
    started = client.post("/datasets", json={"name": "walk", "every": 2}, headers=AUTH)
    assert started.status_code == 201
    person = {"id": 7, "bbox": [10, 20, 30, 40], "visibility": 0.5}
    for n in range(4):
        send_labelled(sim, n, [person])
    client.get("/healthz")
    summary = client.post("/datasets/stop", headers=AUTH).json()
    assert summary == {"name": "walk", "frames": 2, "annotations": 2}

    coco = client.get("/datasets/walk/annotations", headers=AUTH).json()
    assert [i["file_name"] for i in coco["images"]] == ["000000.jpg", "000001.jpg"]
    assert coco["annotations"][1] == {
        "id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 20, 30, 40], "area": 1200,
        "iscrowd": 0, "track_id": 7, "visibility": 0.5,
    }
    assert coco["categories"] == [{"id": 1, "name": "person"}]
    # every=2 keeps frames 0 and 2
    assert client.get("/datasets/walk/images/000001.jpg", headers=AUTH).content == b"jpeg-2"
    assert client.get("/datasets", headers=AUTH).json() == [
        {"name": "walk", "frames": 2, "recording": False}
    ]


def test_recording_stops_itself_at_max_frames(client, sim):
    client.post("/datasets", json={"name": "short", "max_frames": 2}, headers=AUTH)
    for n in range(5):
        send_labelled(sim, n, [])
    assert client.get("/healthz").json()["recording"] is None
    assert len(client.get("/datasets/short/annotations", headers=AUTH).json()["images"]) == 2


def test_dataset_names_cannot_escape_the_datasets_directory(client):
    assert client.post("/datasets", json={"name": "../etc"}, headers=AUTH).status_code == 422
    assert client.get("/datasets/walk/images/..%2F..%2Fsecret", headers=AUTH).status_code == 404


def test_cannot_record_two_datasets_or_reuse_a_name(client):
    client.post("/datasets", json={"name": "one"}, headers=AUTH)
    assert client.post("/datasets", json={"name": "two"}, headers=AUTH).status_code == 409
    client.post("/datasets/stop", headers=AUTH)
    assert client.post("/datasets", json={"name": "one"}, headers=AUTH).status_code == 409
