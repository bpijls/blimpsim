from app.contracts import BlimpProfile
from app.services.profile import JITTERED, jitter_profile


def test_no_spread_leaves_the_profile_alone():
    profile = BlimpProfile()
    assert jitter_profile(profile, 0, seed=1) is profile


def test_jitter_stays_within_the_spread_and_is_repeatable():
    base = BlimpProfile()
    varied = jitter_profile(base, 0.2, seed=3)
    assert varied == jitter_profile(base, 0.2, seed=3)
    assert varied != jitter_profile(base, 0.2, seed=4)
    for name in JITTERED:
        ratio = getattr(varied, name) / getattr(base, name)
        assert 0.8 <= ratio <= 1.2


def test_jitter_does_not_touch_geometry_or_camera():
    base = BlimpProfile()
    varied = jitter_profile(base, 0.5, seed=1)
    assert (varied.length, varied.diameter, varied.camera) == (
        base.length, base.diameter, base.camera,
    )


async def test_run_records_the_profile_actually_flown(client, driver):
    scenario_id = (await client.post("/api/scenarios", json={"name": "Atrium"})).json()["id"]
    res = await client.post(
        "/api/runs", json={"scenario_id": scenario_id, "profile_spread": 0.3, "profile_seed": 9}
    )
    flown = driver.loaded[0][1]
    assert flown.mass != BlimpProfile().mass
    assert res.json()["profile"]["mass"] == flown.mass
