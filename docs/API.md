# blimpsim API

There are two HTTP services. Most users only need the first.

| Service | Where | Base URL | Authentication |
|---|---|---|---|
| **api** | this host | `https://<APP_DOMAIN>/api` or `https://<API_DOMAIN>/api` | none (internal network) |
| **gateway** | GPU host | `http://<SIM_HOST>:8100` (`SIM_GATEWAY_URL`) | `X-Sim-Secret` header, or `?secret=` on WebSockets |

The api is the one to build against: it is the same for the simulated and the real blimp. The gateway is the simulator's own interface; talk to it directly only for lockstep training.

The api also serves interactive documentation generated from the code at `https://<API_DOMAIN>/docs` (Swagger UI) and the raw schema at `/openapi.json`. Those are always current for the HTTP endpoints, but they leave out the WebSockets and the gateway; this file covers those and explains what everything is for.

- [Conventions](#conventions)
- [Scenarios](#scenarios)
- [Runs](#runs)
- [Blimp](#blimp)
- [Datasets](#datasets)
- [Data shapes](#data-shapes)
- [Gateway](#gateway)
- [Lockstep protocol](#lockstep-protocol)
- [Python client](#python-client)

## Conventions

- JSON in and out, except the camera stream and dataset images.
- Errors are `{"detail": "..."}` with a normal HTTP status. `422` means the request body failed validation, and `detail` is then a list of field errors.
- `503` from a blimp, run or dataset endpoint means the simulator or its gateway cannot be reached.
- Coordinates are metres, Y up, right-handed, with the hall centred on the origin and the floor at y = 0. Yaw is radians about +Y: 0 faces -Z, positive turns left.
- Examples use `B=https://blimpsim.paws.home/api`. Add `-k` to `curl` for Caddy's internal certificate.

### Health

`GET /api/health` → `{"status": "ok"}`. Says the api is up, nothing about the simulator; use `GET /api/blimp/status` for that.

## Scenarios

A scenario is a generated hall plus the parameters that produced it. The same parameters and seed always give the same hall.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/scenarios` | List, newest first. Without the world. |
| `POST` | `/api/scenarios` | Generate a hall and save it. `201`. |
| `POST` | `/api/scenarios/preview` | Generate a hall without saving. Returns a [World](#world). |
| `GET` | `/api/scenarios/{id}` | One scenario with its world. |
| `DELETE` | `/api/scenarios/{id}` | Delete it and its runs. `204`. |

`POST /api/scenarios` body:

```json
{ "name": "Atrium", "params": { "seed": 5, "width": 60, "depth": 40, "people": 40 } }
```

`params` and every field in it are optional:

| Field | Default | Range | Meaning |
|---|---|---|---|
| `seed` | 0 | any integer | Layout, colours and crowd all derive from it |
| `width` | 60 | 10–300 | Hall extent along X, metres |
| `depth` | 40 | 10–300 | Hall extent along Z |
| `height` | 12 | 3–40 | Floor to ceiling |
| `pillar_spacing` | 12 | ≥ 0 | Distance between pillars; 0 for none |
| `obstacles` | 12 | 0–200 | Kiosks, benches, planters. Fewer are placed if the hall is full. |
| `entrances` | 4 | 1–16 | Zones along the walls where people appear |
| `attractions` | 3 | 0–16 | Zones where people linger |
| `people` | 40 | 0–500 | Crowd size |
| `wander`, `transit`, `stand` | 0.4, 0.4, 0.2 | ≥ 0 | Behaviour mix; relative weights |

Response:

```json
{
  "id": "46f867d6-…",
  "name": "Atrium",
  "params": { "seed": 5, "width": 60.0, "…": "…" },
  "created_at": "2026-10-01T12:44:10Z",
  "world": { "…": "see World" }
}
```

## Runs

Starting a run loads a scenario into the simulator, replacing whatever was running there. There is one simulator, so there is one current run.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/runs` | Start a run. `201`; `404` unknown scenario; `503` simulator unreachable (nothing is recorded). |
| `GET` | `/api/runs` | The last 100 runs, newest first. |
| `GET` | `/api/runs/current` | The latest run with its world. `404` if nothing was ever run. |

`POST /api/runs` body:

| Field | Default | Meaning |
|---|---|---|
| `scenario_id` | required | |
| `mode` | `"realtime"` | `"realtime"` runs at wall-clock speed. `"lockstep"` stays paused until stepped; see [Lockstep protocol](#lockstep-protocol). |
| `profile` | defaults | A [BlimpProfile](#blimpprofile), whole or partial, e.g. `{"camera": {"width": 320, "height": 240}}` |
| `profile_spread` | 0 | Random variation of the physical airframe parameters; 0.2 means each is scaled by a factor in 0.8–1.2 |
| `profile_seed` | 0 | Seed for that variation |

The response's `profile` is the one actually flown, after variation.

```bash
curl -k -H 'Content-Type: application/json' -d '{"scenario_id":"46f867d6-…"}' $B/runs
```

## Blimp

These endpoints work on whichever blimp the api is configured for (`BLIMP_DRIVER`). With `BLIMP_DRIVER=real` they all return `503` for now: the hardware driver is a stub.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/blimp/status` | Is the blimp reachable. Never fails. |
| `POST` | `/api/blimp/command` | Steer. |
| `WS` | `/api/blimp/telemetry` | Stream of [Telemetry](#telemetry) messages, about 20 per second. |
| `GET` | `/api/blimp/camera.mjpg` | The onboard camera as a motion-JPEG stream. |

### Status

```json
{
  "driver": "sim",
  "reachable": true,
  "sim_connected": true,
  "sim": { "adapter": "NVIDIA GB10", "godot": "4.5-stable (official)" },
  "loaded": true,
  "recording": null
}
```

`reachable` is about the gateway, `sim_connected` about the simulator behind it, `loaded` about whether a world is running. `recording` is `null` or `{name, frames, max_frames}`.

### Command

```json
{ "surge": 0.5, "yaw": -0.2, "heave": 0, "camera_tilt": 35 }
```

| Field | Range | Meaning |
|---|---|---|
| `surge` | -1 to 1 | Forward thrust; negative reverses |
| `yaw` | -1 to 1 | Turning; positive turns left |
| `heave` | -1 to 1 | Vertical thrust; positive climbs |
| `camera_tilt` | 0 to 90, optional | Degrees below the horizon. Omit or `null` to leave it. |

All fields default to 0, so `{}` means stop thrusting.

- Out-of-range thrust is **clamped**, not rejected: `surge: 40` becomes 1. The response echoes the command as applied. Non-numbers and non-finite values are `422`.
- Commands are **latched**. The blimp keeps the last command until it gets another; there is no timeout. A controller that stops sending leaves the blimp doing whatever it was last told.
- A command takes effect after the profile's `command_latency`, and thrust then follows with `actuator_lag`.

```bash
curl -k -H 'Content-Type: application/json' -d '{"surge":1,"yaw":0.3}' $B/blimp/command
```

### Telemetry

```js
const socket = new WebSocket("wss://blimpsim.paws.home/api/blimp/telemetry");
socket.onmessage = (e) => console.log(JSON.parse(e.data).blimp.position);
```

The server closes the socket with code `1013` if the blimp cannot be reached; reconnect after a pause. Nothing is sent while no world is loaded, or while a lockstep world is waiting to be stepped.

### Camera

`multipart/x-mixed-replace; boundary=frame`, one JPEG per part, at the profile's camera `fps` (15 by default). Browsers play it in a plain `<img src=".../api/blimp/camera.mjpg">`. Query parameters are ignored, so adding one (the monitor uses `?run=<id>`) is a way to make a browser reconnect.

## Datasets

Records the camera's frames together with ground truth, as a COCO dataset stored on the GPU host. Only one recording runs at a time, and only frames from a running world are recorded.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/datasets` | `[{name, frames, recording}]` |
| `POST` | `/api/datasets` | Start recording. `201`; `409` if already recording or the name exists. |
| `POST` | `/api/datasets/stop` | Stop and write the annotations. `409` if nothing is recording. |
| `GET` | `/api/datasets/{name}/annotations` | The COCO file |
| `GET` | `/api/datasets/{name}/images/{file}` | One frame, e.g. `000012.jpg` |

`POST /api/datasets` body:

| Field | Default | Meaning |
|---|---|---|
| `name` | required | Lowercase letters, digits, `-`, `_`; up to 64 characters |
| `every` | 1 | Keep every n-th camera frame |
| `max_frames` | 1000 | Recording stops by itself at this many frames (up to 100 000) |

Annotations are standard COCO with one category (`person`) and three extras:

```json
{
  "images": [
    { "id": 0, "file_name": "000000.jpg", "width": 640, "height": 480, "t": 19.667,
      "camera": { "fov_y_deg": 60, "position": [0, 6.85, -0.3], "rotation": [0, 0, 0, 1], "…": "…" } }
  ],
  "annotations": [
    { "id": 0, "image_id": 0, "category_id": 1, "bbox": [320.1, 178.9, 16.1, 63.8], "area": 1027.2,
      "iscrowd": 0, "track_id": 15, "visibility": 1.0 }
  ],
  "categories": [{ "id": 1, "name": "person" }]
}
```

- `bbox` is `[x, y, width, height]` in pixels and covers only the visible part of the person.
- `track_id` identifies the same person across frames of one run.
- `visibility` is the fraction of the person's body keypoints that are in frame and not hidden. Filter on it to drop barely visible people.
- The annotations file exists only once recording has stopped.

## Data shapes

The definitions live in `backend/app/contracts.py`; JSON Schemas generated from them are in `contracts/`.

### World

`contracts/world.schema.json`

| Field | Meaning |
|---|---|
| `seed` | |
| `hall` | `{width, depth, height}` |
| `pillars` | `[{x, z, size}]`, square, floor to ceiling |
| `obstacles` | `[{kind, x, z, width, depth, height, yaw}]`; `kind` is `kiosk`, `bench` or `planter` |
| `zones` | `[{id, kind, x, z, radius}]`; `kind` is `entrance` or `attraction` |
| `lights` | `[{position: [x, y, z], energy}]` |
| `ambient` | 0–1 |
| `look` | `{floor, walls, light}`, each `[r, g, b]` in 0–1; varies with the seed |
| `crowd` | `{count, wander, transit, stand}` |
| `blimp_start` | `{position: [x, y, z], yaw}` |

### Telemetry

`contracts/telemetry.schema.json`

```json
{
  "t": 9.667,
  "blimp": {
    "position": [-1.999, 7.2, -3.258],
    "yaw": 1.9679,
    "velocity": [-0.698, 0.0, -0.155],
    "yaw_rate": 0.3659,
    "camera_tilt": 35.0,
    "battery": null
  },
  "people": [{ "id": 0, "x": -18.81, "z": -5.6, "heading": 0.88 }]
}
```

`t` is seconds of simulated time since the run started. `people` is ground truth and will be empty for the real blimp. `battery` is a placeholder.

### BlimpProfile

`contracts/blimp_profile.schema.json`. The physical values are placeholders until the real blimp can be measured.

| Field | Default | Meaning |
|---|---|---|
| `length`, `diameter` | 1.6, 0.7 | Hull, metres |
| `mass` | 0.35 | kg, including the lifting gas |
| `added_mass` | 0.5 | Fraction of mass added by the air it displaces |
| `buoyancy_trim` | 0 | Net lift in N; 0 is neutrally buoyant |
| `max_surge_thrust`, `max_heave_thrust` | 0.12, 0.08 | N |
| `max_yaw_torque` | 0.03 | N·m |
| `drag_surge`, `drag_sway`, `drag_heave` | 0.12, 0.6, 0.5 | Quadratic drag, N/(m/s)² |
| `linear_damping` | 0.02 | N/(m/s) |
| `yaw_inertia` | 0.08 | kg·m² |
| `yaw_drag`, `yaw_damping` | 0.05, 0.005 | Quadratic and linear |
| `actuator_lag` | 0.3 | Seconds; thrust follows the command with this lag |
| `command_latency` | 0.1 | Seconds between sending a command and it taking effect |
| `camera` | | `{width: 640, height: 480, fov_y_deg: 60, fps: 15, mount: [0, -0.35, -0.3], tilt_deg: 35}` |

### FrameLabels

`contracts/frame_labels.schema.json`. Ground truth for one camera frame; delivered with lockstep frames and written into datasets.

```json
{
  "frame": 293,
  "t": 19.667,
  "camera": { "width": 640, "height": 480, "fov_y_deg": 60,
              "position": [0, 6.85, -0.3], "rotation": [-0.3, 0, 0, 0.95] },
  "people": [{ "id": 15, "bbox": [320.1, 178.9, 16.1, 63.8], "visibility": 1.0 }]
}
```

`rotation` is a quaternion `[x, y, z, w]`. Only people with at least one visible keypoint are listed.

## Gateway

Runs next to the simulator. Everything except `/healthz` needs the shared secret: header `X-Sim-Secret: <SIM_SECRET>` on HTTP, query `?secret=<SIM_SECRET>` on WebSockets (a wrong secret closes the socket with code `4401`). The gateway does not validate bodies; the api does that before forwarding.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | `{status, sim_connected, sim, loaded, recording}`. No secret needed. |
| `POST` | `/load` | `{world, profile, mode}`. What `POST /api/runs` calls. |
| `POST` | `/command` | A blimp command. What `POST /api/blimp/command` calls. |
| `GET` | `/telemetry` | Latest telemetry. `404` before the first. |
| `WS` | `/telemetry` | Telemetry stream |
| `GET` | `/frame.jpg` | Latest camera frame |
| `GET` | `/labels` | [FrameLabels](#framelabels) for the frame `/frame.jpg` currently serves |
| `GET` | `/stream.mjpg` | Camera stream |
| `WS` | `/lockstep` | Stepping; see below |
| `GET` `POST` | `/datasets`, `/datasets/stop`, `/datasets/{name}/…` | Same as the api's dataset endpoints |
| `WS` | `/sim` | For the Godot simulator only |

`/labels` has no counterpart in the api; it is the quickest way to get ground truth for a live frame.

If the simulator restarts, the gateway reloads the last world into it. If the gateway restarts, it has forgotten the world: start a run again.

## Lockstep protocol

For training. The simulation only advances when told to, so episodes are repeatable (same seed and commands give the same blimp and crowd trajectories) and run faster than real time.

1. Start a run with `"mode": "lockstep"` through the api.
2. Connect to `ws://<SIM_HOST>:8100/lockstep?secret=<SIM_SECRET>`.
3. Send one request at a time. Each is answered with **two** messages: the frame header as JSON text, then the JPEG as binary.

| Request | Effect |
|---|---|
| `{"type": "observe"}` | Returns the frame produced by the load or the last reset, without advancing. Use it once after connecting. |
| `{"type": "step", "command": {…}, "ticks": 6}` | Applies the command (optional), advances `ticks` physics ticks, returns the resulting frame. One tick is 1/60 s of simulated time; 6 ticks gives a 10 Hz control loop. |
| `{"type": "reset"}` | Rebuilds the same world from the start and returns its first frame. |

Frame header:

```json
{ "type": "frame", "frame": 12, "tick": 72, "telemetry": { "…": "Telemetry" }, "labels": { "…": "FrameLabels" } }
```

If the simulator is not connected the answer is a single `{"type": "error", "detail": "…"}` with no binary message.

The command given with a step is latched like any other: later steps without a `command` keep using it. Command latency and actuator lag apply in simulated time.

## Python client

`client/` wraps all of the above as a Gymnasium environment.

```bash
uv pip install -p .venv/bin/python -e client
export BLIMPSIM_API_URL=https://blimpsim.paws.home BLIMPSIM_GATEWAY_URL=http://vonk:8100 SIM_SECRET=…
```

```python
from blimpsim_client import BlimpTrackEnv

env = BlimpTrackEnv(scenario_params={"people": 40}, verify_tls=False)
frame, info = env.reset(seed=3)
frame, reward, terminated, truncated, info = env.step([0.5, 0.0, 0.0])
env.close()
```

`BlimpTrackEnv(...)` arguments:

| Argument | Default | Meaning |
|---|---|---|
| `api_url`, `gateway_url`, `secret` | from the environment variables above | |
| `scenario_params` | `{}` | Passed to scenario generation; `reset(seed=…)` overrides `seed` |
| `ticks_per_step` | 6 | Physics ticks per `step()`; 6 is 0.1 s |
| `max_steps` | 600 | `truncated` becomes true after this many |
| `width`, `height` | 640, 480 | Camera resolution |
| `profile_spread` | 0 | Airframe variation per seed; see [Runs](#runs) |
| `verify_tls` | `True` | Set `False` for Caddy's internal certificate |

- **Observation**: the camera frame, `uint8` array of shape `(height, width, 3)`, RGB.
- **Action**: `[surge, yaw, heave]`, each in -1 to 1.
- **Reward**: 1 when the target person is centred and fully visible, falling to 0 towards the corners or when out of view (`tracking_reward`).
- **Target**: the person nearest the blimp at reset, or `reset(options={"target_id": n})`.
- **`info`**: `telemetry`, `labels`, `target_id`, and `target` (the target's label, or `None` when not in view).
- `reset()` with the same seed rebuilds the world in place. A different seed generates a new hall. The environment keeps one scenario named `gym-env` in the api and deletes it on `close()`.
- While an environment is in use the simulator is in lockstep mode, so the monitor and the remote control page only update when the environment steps.

`python -m blimpsim_client.baseline --seed 5 --insecure` runs a reference controller that steers from the target's ground-truth box.
