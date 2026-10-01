"""Baseline tracker: proportional visual servoing on the target's bounding box.

It exists to prove the loop (camera frame in, steering command out) end to end
and to give learned controllers something to beat. The box comes from the
simulator's ground truth, so this measures control, not detection.

    python -m blimpsim_client.baseline --seconds 60 --seed 5
"""
import argparse
from dataclasses import dataclass, field

import numpy as np

from blimpsim_client.env import BlimpTrackEnv


@dataclass
class VisualServo:
    yaw_gain: float = 1.5
    yaw_damping: float = 1.0  # on how fast the target moves across the frame
    surge_gain: float = 1.5
    search_yaw: float = 0.25  # turn slowly on the spot when the target is not in view
    target_row: float = 0.5  # where in the frame to hold the target; 0 top, 1 bottom
    _last_across: float | None = field(default=None, repr=False)

    def act(self, box: dict | None, width: int, height: int, dt: float = 0.1) -> np.ndarray:
        """[surge, yaw, heave] for the target's label, or a search turn if there is none.

        `dt` is the time since the previous call, in seconds.
        """
        if box is None:
            self._last_across = None
            return np.array([0.0, self.search_yaw, 0.0], dtype=np.float32)
        x, y, w, h = box["bbox"]
        # Positive when the target is right of centre; turning right is negative yaw.
        across = (x + w / 2 - width / 2) / (width / 2)
        # Positive when the target is above the row it should sit on, i.e. too far away.
        ahead = (self.target_row * height - (y + h / 2)) / (height / 2)

        # The blimp turns slowly and keeps turning: without damping on the
        # target's motion across the frame it swings straight past it.
        rate = 0.0 if self._last_across is None else (across - self._last_across) / dt
        self._last_across = across
        yaw = np.clip(-(self.yaw_gain * across + self.yaw_damping * rate), -1, 1)
        # Do not charge forward while still turning towards the target.
        surge = np.clip(self.surge_gain * ahead, -1, 1) * max(0.0, 1.0 - abs(across))
        return np.array([surge, yaw, 0.0], dtype=np.float32)


def run(env: BlimpTrackEnv, controller: VisualServo, seconds: float, seed: int) -> dict:
    steps = round(seconds / env.step_seconds)
    env.max_steps = steps
    _, info = env.reset(seed=seed)
    in_view = 0
    acquired_at: int | None = None  # step at which the target was first seen
    total_reward = 0.0
    for step in range(steps):
        action = controller.act(info["target"], env.width, env.height, env.step_seconds)
        _, reward, _, _, info = env.step(action)
        if info["target"] is not None:
            in_view += 1
            if acquired_at is None:
                acquired_at = step
        total_reward += reward
    return {
        "target_id": info["target_id"],
        "steps": steps,
        "in_view": in_view / steps,
        # Searching for the target and keeping it are different problems.
        "search_seconds": None if acquired_at is None else acquired_at * env.step_seconds,
        "held": None if acquired_at is None else in_view / (steps - acquired_at),
        "mean_reward": total_reward / steps,
        "sim_seconds": info["telemetry"]["t"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--people", type=int, default=40)
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification of the api")
    args = parser.parse_args()

    env = BlimpTrackEnv(scenario_params={"people": args.people}, verify_tls=not args.insecure)
    try:
        result = run(env, VisualServo(), args.seconds, args.seed)
    finally:
        env.close()
    print(
        f"target #{result['target_id']}: in view {result['in_view']:.0%} of "
        f"{result['sim_seconds']:.0f} s, mean reward {result['mean_reward']:.2f}"
    )
    if result["held"] is None:
        print("  never found the target")
    else:
        print(
            f"  found after {result['search_seconds']:.1f} s, "
            f"then in view {result['held']:.0%} of the time"
        )


if __name__ == "__main__":
    main()
