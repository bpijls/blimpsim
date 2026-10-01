from fastapi.testclient import TestClient

from app.main import app
from app.services.drivers.real import RealDriver


async def new_scenario(client) -> str:
    return (await client.post("/api/scenarios", json={"name": "Atrium"})).json()["id"]


async def test_command_is_forwarded(client, driver):
    res = await client.post("/api/blimp/command", json={"surge": 0.5, "yaw": -0.2})
    assert res.status_code == 200
    assert (driver.commands[0].surge, driver.commands[0].yaw) == (0.5, -0.2)


async def test_command_is_clamped_before_it_reaches_the_blimp(client, driver):
    res = await client.post("/api/blimp/command", json={"surge": 40, "heave": -3})
    assert res.json()["command"]["surge"] == 1.0
    assert driver.commands[0].heave == -1.0


async def test_command_without_blimp_is_503(client, driver):
    driver.unavailable = True
    assert (await client.post("/api/blimp/command", json={})).status_code == 503


async def test_run_loads_the_scenario_world(client, driver):
    scenario_id = await new_scenario(client)
    res = await client.post("/api/runs", json={"scenario_id": scenario_id, "mode": "lockstep"})
    assert res.status_code == 201
    world, profile, mode = driver.loaded[0]
    assert world.hall.width == 60
    assert profile.camera.width == 640
    assert mode == "lockstep"


async def test_run_is_not_recorded_when_the_simulator_is_down(client, driver):
    scenario_id = await new_scenario(client)
    driver.unavailable = True
    assert (await client.post("/api/runs", json={"scenario_id": scenario_id})).status_code == 503
    assert (await client.get("/api/runs")).json() == []


async def test_run_of_unknown_scenario_is_404(client):
    assert (await client.post("/api/runs", json={"scenario_id": "nope"})).status_code == 404


async def test_current_run_carries_the_world(client):
    assert (await client.get("/api/runs/current")).status_code == 404
    scenario_id = await new_scenario(client)
    await client.post("/api/runs", json={"scenario_id": scenario_id})
    current = (await client.get("/api/runs/current")).json()
    assert current["scenario_id"] == scenario_id
    assert current["world"]["hall"]["depth"] == 40


async def test_camera_stream_is_proxied(client):
    res = await client.get("/api/blimp/camera.mjpg")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("multipart/x-mixed-replace")


async def test_camera_without_blimp_is_503(client, driver):
    driver.unavailable = True
    assert (await client.get("/api/blimp/camera.mjpg")).status_code == 503


def test_telemetry_is_relayed_over_websocket(driver):
    driver.telemetry_messages = [{"t": 0.05}, {"t": 0.1}]
    with TestClient(app).websocket_connect("/api/blimp/telemetry") as socket:
        assert socket.receive_json() == {"t": 0.05}
        assert socket.receive_json() == {"t": 0.1}


async def test_real_driver_reports_itself_unavailable():
    assert (await RealDriver().status())["reachable"] is False
