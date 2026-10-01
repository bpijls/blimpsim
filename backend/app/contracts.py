"""Wire contracts shared by the api, the gateway, the Godot sim and the browser monitor.

Coordinates are Godot's: metres, Y up, right-handed, hall centred on the origin
with the floor at y=0. Yaw is radians about +Y; yaw 0 faces -Z.

These models are the source of truth. The JSON Schemas in /contracts are
generated from them by scripts/export_contracts.py; a test fails when they drift.
"""
import math
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

CONTRACT_VERSION = 1


def _clamp_unit(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("must be a finite number")
    return max(-1.0, min(1.0, value))


# Out-of-range commands are clamped, not rejected: a controller that overshoots
# should saturate the actuator, as it would on the real blimp.
Unit = Annotated[float, BeforeValidator(_clamp_unit), Field(ge=-1.0, le=1.0)]
Vec3 = tuple[float, float, float]


# ── World ────────────────────────────────────────────────────────────────────


class Hall(BaseModel):
    width: float = Field(gt=0, description="Extent along X")
    depth: float = Field(gt=0, description="Extent along Z")
    height: float = Field(gt=0, description="Floor to ceiling")


class Pillar(BaseModel):
    x: float
    z: float
    size: float = Field(gt=0, description="Side of the square cross-section")


class Obstacle(BaseModel):
    kind: Literal["kiosk", "bench", "planter"]
    x: float
    z: float
    width: float = Field(gt=0)
    depth: float = Field(gt=0)
    height: float = Field(gt=0)
    yaw: float = 0.0


class Zone(BaseModel):
    """Where people appear (entrance) or linger (attraction)."""

    id: str
    kind: Literal["entrance", "attraction"]
    x: float
    z: float
    radius: float = Field(gt=0)


class Light(BaseModel):
    position: Vec3
    energy: float = Field(gt=0)


class Crowd(BaseModel):
    count: int = Field(ge=0)
    # Behaviour mix; fractions of `count`, normalised by the sim.
    wander: float = Field(ge=0)
    transit: float = Field(ge=0)
    stand: float = Field(ge=0)


Rgb = tuple[float, float, float]


class Look(BaseModel):
    """Surface and light colours, varied per seed so a detector does not learn one hall."""

    floor: Rgb = (0.55, 0.55, 0.58)
    walls: Rgb = (0.82, 0.8, 0.76)
    light: Rgb = (1.0, 1.0, 1.0)


class Pose(BaseModel):
    position: Vec3
    yaw: float = 0.0


class World(BaseModel):
    version: int = CONTRACT_VERSION
    seed: int
    hall: Hall
    pillars: list[Pillar]
    obstacles: list[Obstacle]
    zones: list[Zone]
    lights: list[Light]
    ambient: float = Field(ge=0, le=1)
    look: Look = Look()
    crowd: Crowd
    blimp_start: Pose


class ScenarioParams(BaseModel):
    """Inputs to world generation. Same params + seed always give the same world."""

    seed: int = 0
    width: float = Field(60.0, ge=10, le=300)
    depth: float = Field(40.0, ge=10, le=300)
    height: float = Field(12.0, ge=3, le=40)
    pillar_spacing: float = Field(12.0, ge=0, description="0 disables pillars")
    obstacles: int = Field(12, ge=0, le=200)
    entrances: int = Field(4, ge=1, le=16)
    attractions: int = Field(3, ge=0, le=16)
    people: int = Field(40, ge=0, le=500)
    wander: float = Field(0.4, ge=0)
    transit: float = Field(0.4, ge=0)
    stand: float = Field(0.2, ge=0)


# ── Blimp ────────────────────────────────────────────────────────────────────


class BlimpCommand(BaseModel):
    """Hardware-agnostic steering command. The real blimp's API adapts to this."""

    surge: Unit = Field(0.0, description="Forward thrust, -1 (reverse) to 1")
    yaw: Unit = Field(0.0, description="Turn rate demand, positive turns left")
    heave: Unit = Field(0.0, description="Vertical thrust, positive up")
    camera_tilt: float | None = Field(
        None, ge=0, le=90, description="Degrees below the horizon; null leaves it unchanged"
    )


class CameraProfile(BaseModel):
    width: int = Field(640, gt=0)
    height: int = Field(480, gt=0)
    fov_y_deg: float = Field(60.0, gt=0, lt=180)
    fps: float = Field(15.0, gt=0)
    mount: Vec3 = Field((0.0, -0.35, -0.3), description="Offset from the blimp's centre")
    tilt_deg: float = Field(35.0, ge=0, le=90, description="Default tilt below the horizon")


class BlimpProfile(BaseModel):
    """Airframe parameters. Placeholders until fitted to the real blimp's step responses."""

    length: float = Field(1.6, gt=0)
    diameter: float = Field(0.7, gt=0)
    mass: float = Field(0.35, gt=0, description="kg, including the lifting gas")
    added_mass: float = Field(0.5, ge=0, description="Fraction of mass added by displaced air")
    buoyancy_trim: float = Field(0.0, description="Net lift in N; 0 is neutrally buoyant")
    max_surge_thrust: float = Field(0.12, gt=0, description="N")
    max_heave_thrust: float = Field(0.08, gt=0, description="N")
    max_yaw_torque: float = Field(0.03, gt=0, description="N·m")
    drag_surge: float = Field(0.12, gt=0, description="Quadratic drag, N/(m/s)^2")
    drag_sway: float = Field(0.6, gt=0)
    drag_heave: float = Field(0.5, gt=0)
    linear_damping: float = Field(0.02, ge=0, description="N/(m/s); brings it to rest")
    yaw_inertia: float = Field(0.08, gt=0, description="kg·m^2")
    yaw_drag: float = Field(0.05, gt=0, description="N·m/(rad/s)^2")
    yaw_damping: float = Field(0.005, ge=0, description="N·m/(rad/s)")
    actuator_lag: float = Field(0.3, ge=0, description="First-order thrust lag, s")
    command_latency: float = Field(0.1, ge=0, description="Radio delay, s")
    camera: CameraProfile = CameraProfile()


# ── Telemetry and labels ─────────────────────────────────────────────────────


class BlimpState(BaseModel):
    position: Vec3
    yaw: float
    velocity: Vec3
    yaw_rate: float
    camera_tilt: float = Field(description="Degrees below the horizon")
    battery: float | None = Field(None, ge=0, le=1)


class PersonState(BaseModel):
    """Ground truth; only the simulator can provide it."""

    id: int
    x: float
    z: float
    heading: float


class Telemetry(BaseModel):
    t: float = Field(description="Seconds since the run started")
    blimp: BlimpState
    people: list[PersonState] = []


class CameraPose(BaseModel):
    width: int
    height: int
    fov_y_deg: float
    position: Vec3
    rotation: tuple[float, float, float, float] = Field(description="Quaternion x, y, z, w")


class PersonLabel(BaseModel):
    id: int = Field(description="Stable across frames: the track id")
    bbox: tuple[float, float, float, float] = Field(description="x, y, width, height in pixels")
    visibility: float = Field(ge=0, le=1, description="Fraction of the body not occluded")


class FrameLabels(BaseModel):
    frame: int
    t: float
    camera: CameraPose
    people: list[PersonLabel]


SCHEMAS: dict[str, type[BaseModel]] = {
    "world": World,
    "scenario_params": ScenarioParams,
    "blimp_command": BlimpCommand,
    "blimp_profile": BlimpProfile,
    "telemetry": Telemetry,
    "frame_labels": FrameLabels,
}
