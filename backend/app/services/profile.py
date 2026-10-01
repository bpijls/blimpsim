"""Variation of the blimp's airframe parameters."""
import random

from app.contracts import BlimpProfile

# Physical parameters only: geometry and the camera stay as specified.
JITTERED = (
    "mass",
    "added_mass",
    "max_surge_thrust",
    "max_heave_thrust",
    "max_yaw_torque",
    "drag_surge",
    "drag_sway",
    "drag_heave",
    "linear_damping",
    "yaw_inertia",
    "yaw_drag",
    "yaw_damping",
    "actuator_lag",
    "command_latency",
)


def jitter_profile(profile: BlimpProfile, spread: float, seed: int) -> BlimpProfile:
    """Scale each physical parameter by a random factor in [1 - spread, 1 + spread].

    The real blimp's parameters are unknown, so a controller trained against one
    fixed set would be fitted to a guess. Training across a spread is the hedge.
    """
    if spread == 0:
        return profile
    rng = random.Random(seed)
    scaled = {
        name: getattr(profile, name) * rng.uniform(1 - spread, 1 + spread) for name in JITTERED
    }
    return profile.model_copy(update=scaled)
