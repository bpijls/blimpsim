"""Checks against the live simulator: physics sanity and repeatability.

Skipped unless the simulator is configured:
    BLIMPSIM_API_URL=... BLIMPSIM_GATEWAY_URL=... SIM_SECRET=... pytest -m sim
"""
import math
import os

import pytest

from blimpsim_client import BlimpTrackEnv

pytestmark = [
    pytest.mark.sim,
    pytest.mark.skipif(
        not os.environ.get("BLIMPSIM_GATEWAY_URL"), reason="live simulator not configured"
    ),
]

# An empty hall: nothing to bump into, nobody to compute.
EMPTY = {"pillar_spacing": 0, "obstacles": 0, "people": 0}


@pytest.fixture
def env():
    environment = BlimpTrackEnv(
        scenario_params=EMPTY, verify_tls=os.environ.get("BLIMPSIM_INSECURE") != "1"
    )
    yield environment
    environment.close()


def blimp(info: dict) -> dict:
    return info["telemetry"]["blimp"]


def test_idle_blimp_holds_position(env):
    _, info = env.reset(seed=1)
    start = blimp(info)["position"]
    for _ in range(50):
        _, _, _, _, info = env.step([0, 0, 0])
    assert blimp(info)["position"] == start


def test_full_thrust_settles_at_the_speed_drag_allows(env):
    _, info = env.reset(seed=1)
    for _ in range(200):  # 20 simulated seconds
        _, _, _, _, info = env.step([1, 0, 0])
    speed = math.hypot(*blimp(info)["velocity"])
    # Thrust 0.12 N against 0.12 u^2 + 0.02 u (the default BlimpProfile).
    expected = (-0.02 + math.sqrt(0.02**2 + 4 * 0.12 * 0.12)) / (2 * 0.12)
    assert speed == pytest.approx(expected, rel=0.02)


def test_step_advances_exactly_the_requested_time(env):
    _, info = env.reset(seed=1)
    for _ in range(10):
        _, _, _, _, info = env.step([0, 0, 0])
    assert info["telemetry"]["t"] == pytest.approx(10 * env.step_seconds)


def test_same_seed_and_commands_give_the_same_trajectory():
    def fly() -> list:
        environment = BlimpTrackEnv(
            scenario_params={"people": 30},
            verify_tls=os.environ.get("BLIMPSIM_INSECURE") != "1",
        )
        try:
            _, info = environment.reset(seed=4)
            trail = []
            for i in range(120):
                _, _, _, _, info = environment.step([0.8, 0.5 if i < 40 else -0.3, 0.1])
                trail.append((blimp(info), info["telemetry"]["people"]))
            # A reset must also reproduce the episode, not only a fresh load.
            _, info = environment.reset(seed=4)
            for i in range(120):
                _, _, _, _, info = environment.step([0.8, 0.5 if i < 40 else -0.3, 0.1])
            trail.append((blimp(info), info["telemetry"]["people"]))
            return trail
        finally:
            environment.close()

    first = fly()
    assert first[-1] == first[-2]
    assert fly() == first
