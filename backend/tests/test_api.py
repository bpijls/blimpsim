async def test_health(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


async def test_create_then_read_item(client):
    created = await client.post("/api/items", json={"title": "First", "body": "hello"})
    assert created.status_code == 201
    item_id = created.json()["id"]

    fetched = await client.get(f"/api/items/{item_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "First"


async def test_missing_item_is_404(client):
    assert (await client.get("/api/items/nope")).status_code == 404


async def test_list_starts_empty(client):
    res = await client.get("/api/items")
    assert res.status_code == 200
    assert res.json() == []
