"""Gymnasium environment over the simulator's lockstep interface.

One step advances the simulation by a fixed number of physics ticks and returns
the onboard camera frame. Nothing runs between steps, so episodes are
repeatable and run faster than real time.

    env = BlimpTrackEnv()            # reads BLIMPSIM_API_URL, BLIMPSIM_GATEWAY_URL, SIM_SECRET
    obs, info = env.reset(seed=3)
    obs, reward, terminated, truncated, info = env.step([0.5, 0.0, 0.0])
"""
import contextlib
import io
import json
import math
import os

import gymnasium as gym
import httpx
import numpy as np
from PIL import Image
from websockets.sync.client import connect

PHYSICS_HZ = 60
SCENARIO_NAME = "gym-env"


def tracking_reward(box: dict | None, width: int, height: int) -> float:
    """1 when the target is centred and fully visible; 0 at the corners or out of view."""
    if box is None:
        return 0.0
    x, y, w, h = box["bbox"]
    dx = (x + w / 2 - width / 2) / (width / 2)
    dy = (y + h / 2 - height / 2) / (height / 2)
    return (1.0 - math.hypot(dx, dy) / math.sqrt(2)) * box["visibility"]


def _required(value: str | None, env_var: str) -> str:
    value = value or os.environ.get(env_var)
    if not value:
        raise ValueError(f"{env_var} is not set")
    return value.rstrip("/")


class BlimpTrackEnv(gym.Env):
    """Keep one person in the camera's view.

    Observation: the camera frame, uint8 (height, width, 3).
    Action: [surge, yaw, heave], each in [-1, 1].
    Reward: tracking_reward() for the target person.
    info: "telemetry", "labels" (ground truth for the frame), "target_id",
    "target" (the target's label, or None when it is not in view).
    """

    metadata = {"render_modes": ["rgb_array"]}

    def __init__(
        self,
        api_url: str | None = None,
        gateway_url: str | None = None,
        secret: str | None = None,
        scenario_params: dict | None = None,
        ticks_per_step: int = 6,
        max_steps: int = 600,
        width: int = 640,
        height: int = 480,
        profile_spread: float = 0.0,
        verify_tls: bool = True,
    ) -> None:
        self.gateway_url = _required(gateway_url, "BLIMPSIM_GATEWAY_URL")
        self.secret = _required(secret, "SIM_SECRET")
        self.scenario_params = scenario_params or {}
        self.ticks_per_step = ticks_per_step
        self.max_steps = max_steps
        self.width, self.height = width, height
        # Random variation of the airframe per seed, e.g. 0.2 for ±20% (the api's jitter_profile).
        self.profile_spread = profile_spread

        self.observation_space = gym.spaces.Box(0, 255, (height, width, 3), np.uint8)
        self.action_space = gym.spaces.Box(-1.0, 1.0, (3,), np.float32)

        self._api = httpx.Client(
            base_url=_required(api_url, "BLIMPSIM_API_URL"), timeout=30.0, verify=verify_tls
        )
        self._socket = None
        self._connections = contextlib.ExitStack()
        self._scenario_id: str | None = None
        self._loaded_params: dict | None = None
        self._steps = 0
        self._frame: np.ndarray | None = None
        self.target_id: int | None = None

    @property
    def step_seconds(self) -> float:
        return self.ticks_per_step / PHYSICS_HZ

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        params = dict(self.scenario_params)
        if seed is not None:
            params["seed"] = seed

        if params == self._loaded_params and self._socket is not None:
            # Same world: the simulator rebuilds it in place.
            meta, frame = self._exchange({"type": "reset"})
        else:
            self._load(params)
            meta, frame = self._exchange({"type": "observe"})

        self._steps = 0
        self.target_id = (options or {}).get("target_id", self._nearest_person(meta["telemetry"]))
        return frame, self._info(meta)

    def step(self, action):
        surge, yaw, heave = (float(np.clip(a, -1.0, 1.0)) for a in action)
        meta, frame = self._exchange(
            {
                "type": "step",
                "command": {"surge": surge, "yaw": yaw, "heave": heave},
                "ticks": self.ticks_per_step,
            }
        )
        self._steps += 1
        info = self._info(meta)
        reward = tracking_reward(info["target"], self.width, self.height)
        return frame, reward, False, self._steps >= self.max_steps, info

    def render(self):
        return self._frame

    def close(self) -> None:
        self._connections.close()
        self._socket = None
        self._delete_scenario()
        self._api.close()

    # ── internals ────────────────────────────────────────────────────────────

    def _load(self, params: dict) -> None:
        self._delete_scenario()
        scenario = self._api.post("/api/scenarios", json={"name": SCENARIO_NAME, "params": params})
        scenario.raise_for_status()
        self._scenario_id = scenario.json()["id"]
        run = self._api.post(
            "/api/runs",
            json={
                "scenario_id": self._scenario_id,
                "mode": "lockstep",
                "profile": {"camera": {"width": self.width, "height": self.height}},
                "profile_spread": self.profile_spread,
                "profile_seed": params.get("seed", 0),
            },
        )
        run.raise_for_status()
        self._loaded_params = params
        if self._socket is None:
            url = self.gateway_url.replace("http", "ws", 1)
            self._socket = self._connections.enter_context(
                connect(f"{url}/lockstep?secret={self.secret}", max_size=None)
            )

    def _delete_scenario(self) -> None:
        # The env owns one scenario at a time, so training does not fill the database.
        if self._scenario_id is not None:
            self._api.delete(f"/api/scenarios/{self._scenario_id}")
            self._scenario_id = None
            self._loaded_params = None

    def _exchange(self, request: dict) -> tuple[dict, np.ndarray]:
        self._socket.send(json.dumps(request))
        meta = json.loads(self._socket.recv())
        if meta.get("type") == "error":
            raise RuntimeError(f"simulator: {meta['detail']}")
        jpeg = self._socket.recv()
        self._frame = np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))
        return meta, self._frame

    def _info(self, meta: dict) -> dict:
        labels = meta["labels"]
        target = next((p for p in labels["people"] if p["id"] == self.target_id), None)
        return {
            "telemetry": meta["telemetry"],
            "labels": labels,
            "target_id": self.target_id,
            "target": target,
        }

    @staticmethod
    def _nearest_person(telemetry: dict) -> int | None:
        x, _, z = telemetry["blimp"]["position"]
        people = telemetry["people"]
        if not people:
            return None
        return min(people, key=lambda p: math.hypot(p["x"] - x, p["z"] - z))["id"]
