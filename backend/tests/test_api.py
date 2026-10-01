async def test_health(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


async def test_create_then_read_scenario(client):
    created = await client.post(
        "/api/scenarios", json={"name": "Atrium", "params": {"seed": 7, "people": 25}}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["world"]["seed"] == 7
    assert body["world"]["crowd"]["count"] == 25

    fetched = await client.get(f"/api/scenarios/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["world"] == body["world"]


async def test_list_omits_world(client):
    await client.post("/api/scenarios", json={"name": "Atrium"})
    listed = (await client.get("/api/scenarios")).json()
    assert [s["name"] for s in listed] == ["Atrium"]
    assert "world" not in listed[0]


async def test_preview_does_not_save(client):
    res = await client.post("/api/scenarios/preview", json={"seed": 3})
    assert res.status_code == 200
    assert res.json()["seed"] == 3
    assert (await client.get("/api/scenarios")).json() == []


async def test_invalid_params_rejected(client):
    res = await client.post("/api/scenarios", json={"name": "Tiny", "params": {"width": 1}})
    assert res.status_code == 422


async def test_delete_scenario(client):
    scenario_id = (await client.post("/api/scenarios", json={"name": "Gone"})).json()["id"]
    assert (await client.delete(f"/api/scenarios/{scenario_id}")).status_code == 204
    assert (await client.get(f"/api/scenarios/{scenario_id}")).status_code == 404


async def test_missing_scenario_is_404(client):
    assert (await client.get("/api/scenarios/nope")).status_code == 404
