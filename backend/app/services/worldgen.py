"""Procedural hall generation: ScenarioParams -> World, deterministic per seed."""
import colorsys
import math
import random

from app.contracts import (
    Crowd,
    Hall,
    Light,
    Look,
    Obstacle,
    Pillar,
    Pose,
    ScenarioParams,
    World,
    Zone,
)

PILLAR_SIZE = 0.8
WALL_MARGIN = 1.5
ZONE_RADIUS = 2.5
LIGHT_SPACING = 10.0
# kind: (width, depth, height)
OBSTACLE_SIZES = {
    "kiosk": (2.0, 2.0, 2.5),
    "bench": (2.0, 0.6, 0.5),
    "planter": (1.2, 1.2, 1.0),
}
PLACEMENT_ATTEMPTS = 50

Circle = tuple[float, float, float]  # x, z, radius


def _r(value: float) -> float:
    return round(value, 3)


def _grid(extent: float, spacing: float) -> list[float]:
    """Interior grid lines across `extent`, roughly `spacing` apart, centred on 0."""
    cells = max(1, round(extent / spacing))
    return [-extent / 2 + i * extent / cells for i in range(1, cells)]


def _cell_centre_near_zero(extent: float, spacing: float) -> float:
    """A coordinate midway between grid lines, so it never lands on a pillar."""
    cells = max(1, round(extent / spacing))
    return 0.0 if cells % 2 else extent / cells / 2


def _is_clear(x: float, z: float, radius: float, taken: list[Circle]) -> bool:
    return all(math.hypot(x - tx, z - tz) >= radius + tr for tx, tz, tr in taken)


def _place(
    rng: random.Random, half_w: float, half_d: float, radius: float, taken: list[Circle]
) -> tuple[float, float] | None:
    """Random floor position clear of everything in `taken`, or None if the hall is full."""
    for _ in range(PLACEMENT_ATTEMPTS):
        x = rng.uniform(-half_w + WALL_MARGIN + radius, half_w - WALL_MARGIN - radius)
        z = rng.uniform(-half_d + WALL_MARGIN + radius, half_d - WALL_MARGIN - radius)
        if _is_clear(x, z, radius, taken):
            return x, z
    return None


def _look(rng: random.Random) -> Look:
    def colour(saturation: float, low: float, high: float) -> tuple[float, float, float]:
        rgb = colorsys.hsv_to_rgb(rng.random(), rng.uniform(0, saturation), rng.uniform(low, high))
        return tuple(_r(c) for c in rgb)

    # Lighting from warm to cool white.
    warmth = rng.uniform(-0.12, 0.12)
    return Look(
        floor=colour(0.25, 0.3, 0.7),
        walls=colour(0.2, 0.6, 0.95),
        light=(_r(1.0 + min(warmth, 0)), _r(1.0 - abs(warmth) / 2), _r(1.0 - max(warmth, 0))),
    )


def generate_world(params: ScenarioParams) -> World:
    rng = random.Random(params.seed)
    half_w, half_d = params.width / 2, params.depth / 2
    taken: list[Circle] = []

    pillars: list[Pillar] = []
    if params.pillar_spacing > 0:
        for x in _grid(params.width, params.pillar_spacing):
            for z in _grid(params.depth, params.pillar_spacing):
                pillars.append(Pillar(x=_r(x), z=_r(z), size=PILLAR_SIZE))
                taken.append((x, z, PILLAR_SIZE))

    zones: list[Zone] = []
    for i in range(params.entrances):
        # Entrances sit just inside a wall; walls are picked in turn so they spread out.
        wall = i % 4
        along_x = wall < 2
        span = (half_w if along_x else half_d) - WALL_MARGIN - ZONE_RADIUS
        offset = rng.uniform(-span, span)
        inset = (half_d if along_x else half_w) - WALL_MARGIN - ZONE_RADIUS
        sign = 1 if wall % 2 else -1
        x, z = (offset, sign * inset) if along_x else (sign * inset, offset)
        zones.append(
            Zone(id=f"entrance-{i}", kind="entrance", x=_r(x), z=_r(z), radius=ZONE_RADIUS)
        )
        taken.append((x, z, ZONE_RADIUS))

    for i in range(params.attractions):
        spot = _place(rng, half_w, half_d, ZONE_RADIUS, taken)
        if spot is None:
            break
        x, z = spot
        zones.append(
            Zone(id=f"attraction-{i}", kind="attraction", x=_r(x), z=_r(z), radius=ZONE_RADIUS)
        )
        taken.append((x, z, ZONE_RADIUS))

    obstacles: list[Obstacle] = []
    kinds = sorted(OBSTACLE_SIZES)
    for _ in range(params.obstacles):
        kind = rng.choice(kinds)
        width, depth, height = OBSTACLE_SIZES[kind]
        radius = math.hypot(width, depth) / 2
        yaw = rng.uniform(0, math.pi)
        spot = _place(rng, half_w, half_d, radius, taken)
        if spot is None:
            break
        x, z = spot
        obstacles.append(
            Obstacle(
                kind=kind, x=_r(x), z=_r(z), width=width, depth=depth, height=height, yaw=_r(yaw)
            )
        )
        taken.append((x, z, radius))

    light_y = params.height - 0.5
    lights = [
        Light(position=(_r(x), _r(light_y), _r(z)), energy=_r(rng.uniform(0.8, 1.2)))
        for x in _grid(params.width, LIGHT_SPACING) or [0.0]
        for z in _grid(params.depth, LIGHT_SPACING) or [0.0]
    ]

    spacing = params.pillar_spacing or params.width
    blimp_start = Pose(
        position=(
            _r(_cell_centre_near_zero(params.width, spacing)),
            _r(params.height * 0.6),
            _r(_cell_centre_near_zero(params.depth, spacing)),
        ),
        yaw=0.0,
    )

    return World(
        seed=params.seed,
        hall=Hall(width=params.width, depth=params.depth, height=params.height),
        pillars=pillars,
        obstacles=obstacles,
        zones=zones,
        lights=lights,
        ambient=_r(rng.uniform(0.25, 0.45)),
        look=_look(rng),
        crowd=Crowd(
            count=params.people, wander=params.wander, transit=params.transit, stand=params.stand
        ),
        blimp_start=blimp_start,
    )
