import math

import pytest

from app.contracts import ScenarioParams
from app.services.worldgen import PILLAR_SIZE, generate_world


def test_same_seed_same_world():
    params = ScenarioParams(seed=42)
    assert generate_world(params) == generate_world(params)


def test_different_seed_different_world():
    assert generate_world(ScenarioParams(seed=1)) != generate_world(ScenarioParams(seed=2))


@pytest.mark.parametrize("seed", range(20))
def test_everything_is_inside_the_hall(seed):
    world = generate_world(ScenarioParams(seed=seed, width=50, depth=30))
    half_w, half_d = 25, 15
    for item in [*world.pillars, *world.obstacles, *world.zones]:
        assert -half_w < item.x < half_w
        assert -half_d < item.z < half_d
    x, y, z = world.blimp_start.position
    assert -half_w < x < half_w and -half_d < z < half_d
    assert 0 < y < world.hall.height


@pytest.mark.parametrize("seed", range(20))
def test_obstacles_do_not_overlap_pillars_or_zones(seed):
    world = generate_world(ScenarioParams(seed=seed, obstacles=40))
    for obstacle in world.obstacles:
        radius = math.hypot(obstacle.width, obstacle.depth) / 2
        for pillar in world.pillars:
            assert math.hypot(obstacle.x - pillar.x, obstacle.z - pillar.z) >= radius + pillar.size
        for zone in world.zones:
            assert math.hypot(obstacle.x - zone.x, obstacle.z - zone.z) >= radius + zone.radius


@pytest.mark.parametrize("width,depth", [(60, 40), (48, 48), (36, 24), (100, 20)])
def test_blimp_does_not_start_inside_a_pillar(width, depth):
    world = generate_world(ScenarioParams(width=width, depth=depth))
    x, _, z = world.blimp_start.position
    for pillar in world.pillars:
        assert math.hypot(x - pillar.x, z - pillar.z) > PILLAR_SIZE + 1.0


def test_pillars_can_be_disabled():
    world = generate_world(ScenarioParams(pillar_spacing=0))
    assert world.pillars == []
    assert world.blimp_start.position[0] == 0.0


def test_crowded_hall_places_fewer_obstacles_instead_of_overlapping():
    world = generate_world(ScenarioParams(width=10, depth=10, obstacles=200))
    assert len(world.obstacles) < 200


def test_requested_zone_counts():
    world = generate_world(ScenarioParams(entrances=5, attractions=2))
    kinds = [z.kind for z in world.zones]
    assert kinds.count("entrance") == 5
    assert kinds.count("attraction") == 2


def test_look_varies_with_the_seed_and_stays_a_colour():
    a = generate_world(ScenarioParams(seed=1)).look
    b = generate_world(ScenarioParams(seed=2)).look
    assert a != b
    for colour in (a.floor, a.walls, a.light):
        assert all(0 <= channel <= 1 for channel in colour)
