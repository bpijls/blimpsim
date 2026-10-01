# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Digital twin of a camera blimp that tracks people in a large indoor space. A Godot 4 simulator renders a procedurally generated hall, a walking crowd and the blimp's onboard camera; the api steers the blimp through a driver layer that will later point at the real hardware; a Three.js page monitors it. The twin produces (1) a closed loop for developing and training a tracking controller and (2) labelled camera frames for training a person detector.

```
            this host (docker compose, Caddy)                 GPU host "vonk" (sim/docker-compose.yml)
browser ──▶ frontend (Vite+React+Three.js, :3000)
              │ /api (HTTP + WebSocket)
              ▼
            api (FastAPI, :8000) ──HTTP/WS, X-Sim-Secret──▶ gateway (FastAPI, :8100) ◀──WS── sim (Godot 4)
              │                                                │
              ▼                                                ▼
            postgres (scenarios, runs)                       datasets volume (COCO)

trainer / controller ──▶ client/ (Gymnasium env) ──▶ api (load a world) + gateway /lockstep (step it)
```

Everything that needs the GPU (rendering, and later training and inference) runs on vonk. This host only serves the api, the database and the monitor.

## Running the stack

This host:

```bash
./setup.sh                        # first time: creates .env, checks it, starts the stack
docker compose up -d --build      # after dependency changes
docker compose logs -f api
docker compose down
```

`backend/app/` and `frontend/src/` are volume-mounted with hot reload. Anything outside them (`requirements.txt`, `package.json`, `vite.config.js`, Dockerfiles) needs a rebuild.

Simulator, on vonk:

```bash
./sim/deploy.sh                   # rsync sim/ to SIM_HOST:SIM_REMOTE_DIR, then docker compose up -d --build there
ssh vonk 'cd projects/blimpsim-sim && docker compose logs -f sim'
curl http://vonk:8100/healthz     # sim_connected, loaded, recording
```

The folder on vonk (`~/projects/blimpsim-sim`) is only a deployed copy of `sim/`: it is not a git repository and has no source of its own. Edit `sim/` here and deploy; never edit on vonk, the next deploy overwrites it (everything except its `.env`).

Every change under `sim/` needs `./sim/deploy.sh`; nothing there is hot-reloaded. The image build fails on GDScript errors (the `--import` step greps for `SCRIPT ERROR`), which is the quickest way to check a script since Godot is not installed on this host. The first deploy creates the remote `.env` from `sim/.env.example` with this host's `SIM_SECRET`; later deploys never touch it.

Redeploying restarts the gateway, which forgets the loaded world: press Run/Restart in the monitor (or `POST /api/runs`) afterwards.

## Tests

One venv at the repo root serves all three Python packages:

```bash
uv venv .venv
uv pip install -p .venv/bin/python -r backend/requirements-dev.txt -r sim/gateway/requirements-dev.txt -e "client[dev]"
```

```bash
cd backend && ../.venv/bin/pytest && ../.venv/bin/ruff check app tests scripts
cd sim/gateway && ../../.venv/bin/pytest && ../../.venv/bin/ruff check app tests
cd client && ../.venv/bin/pytest && ../.venv/bin/ruff check blimpsim_client tests
cd frontend && npm test && npm run lint
```

None of these need Docker, postgres or the simulator: the backend uses SQLite in memory and a `FakeDriver` (`tests/conftest.py`), the gateway tests play the simulator's side of the WebSocket themselves.

Checks against the live simulator (physics sanity, repeatability) are marked `sim` and skipped unless configured:

```bash
cd client && BLIMPSIM_API_URL=https://blimpsim.paws.home BLIMPSIM_GATEWAY_URL=http://vonk:8100 \
  SIM_SECRET=... BLIMPSIM_INSECURE=1 ../.venv/bin/pytest -m sim
```

`BLIMPSIM_INSECURE=1` skips TLS verification, needed for Caddy's internal certificate.

## Architecture

```
contracts/                 JSON Schemas generated from backend/app/contracts.py; do not edit by hand
docs/API.md                Endpoint reference for the api, the gateway and the lockstep protocol;
                           update it when a router, a contract or the gateway changes

backend/
  app/
    main.py                FastAPI app, CORS, lifespan (create_all), router registration
    config.py              Pydantic Settings; sim_secret is required
    contracts.py           Source of truth for every wire format: World, ScenarioParams, BlimpCommand,
                           BlimpProfile, Telemetry, FrameLabels
    models.py              Scenario (params + generated world), Run (scenario, mode, profile flown)
    schemas.py             Request/response shapes that are not wire contracts
    routers/
      scenarios.py         CRUD + /preview (generate without saving)
      runs.py              POST loads a scenario into the simulator; /current returns the run with its world
      blimp.py             /status, /command, /telemetry (WebSocket relay), /camera.mjpg (stream proxy)
      datasets.py          Start/stop recording, list, annotations, images (all proxied to the gateway)
    services/
      worldgen.py          ScenarioParams + seed -> World; deterministic
      profile.py           jitter_profile(): random variation of airframe parameters
      datasets.py          DatasetStore: httpx client for the gateway's dataset endpoints
      drivers/
        base.py            BlimpDriver interface + DriverUnavailable
        sim.py             SimDriver: talks to the gateway
        real.py            RealDriver: stub until the hardware API is known
        __init__.py        get_driver() dependency, selected by BLIMP_DRIVER
  scripts/export_contracts.py   Regenerates contracts/*.schema.json
  tests/

frontend/
  index.html               The monitor (src/main.jsx)
  remote.html              Stand-alone remote control (src/remote.jsx); opened from the monitor's header.
                           Outside src/, so adding or changing a page file needs a frontend rebuild.
frontend/src/
  App.jsx                  Monitor: layout, data loading, HUD (camera preview, telemetry readout)
  Remote.jsx               Remote control: full-window camera, on-screen and keyboard steering, telemetry
  api.js                   All fetch() wrappers and URL builders
  ScenarioPanel.jsx        Scenario list and hall generation form
  DatasetPanel.jsx         Record/stop, dataset list
  DatasetViewer.jsx        Recorded frames with ground-truth boxes drawn on top
  useTelemetry.js          Telemetry WebSocket with reconnect
  useKeyboardSteering.js   W/S surge, A/D yaw, R/F heave; press()/release() for on-screen buttons
  monitor/
    scene.js               Three.js scene: hall, blimp, camera footprint, people. No React.
    Monitor.jsx            React wrapper; telemetry is pushed in through a ref, not props

sim/                       Deployed to the GPU host; not part of this host's compose project
  docker-compose.yml       gateway + sim (runtime: nvidia)
  deploy.sh                rsync + remote compose up
  godot/
    project.godot          Navigation threading disabled for repeatability (see Key constraints)
    entrypoint.sh          Starts Xvfb, then Godot with the Vulkan renderer
    scripts/
      main.gd              Simulation clock, real-time and lockstep modes, frame capture, gateway messages
      net_client.gd        Reconnecting WebSocket client
      hall_builder.gd      World -> static geometry, lights, environment
      blimp.gd             Blimp dynamics, integrated by hand from BlimpProfile
      crowd.gd             Navmesh bake, spawning, ground-truth labels
      person.gd            Procedural mannequin, walking behaviour, keypoints for labelling
  gateway/app/
    main.py                HTTP + WebSocket endpoints
    link.py                SimLink: the simulator's connection and fan-out of what it sends
    recorder.py            Recorder: frames + labels -> COCO dataset on disk
  spike/                   Milestone-0 experiment that chose the rendering route; not deployed

client/blimpsim_client/
  env.py                   BlimpTrackEnv (Gymnasium), tracking_reward()
  baseline.py              VisualServo controller + `python -m blimpsim_client.baseline`
```

## Conventions

**Coordinates** (same in Godot, the contracts and Three.js): metres, Y up, right-handed, hall centred on the origin with the floor at y=0. Yaw is radians about +Y, 0 facing -Z, positive turning left.

**Contracts.** `backend/app/contracts.py` is the only definition. After changing it, run `cd backend && ../.venv/bin/python scripts/export_contracts.py`; `tests/test_contracts.py` fails if the schemas are stale. The gateway passes payloads through without validating them, and GDScript reads fields by name, so a renamed field must also be renamed in `sim/godot/scripts/`.

**Two ways to drive the blimp.**
- Real time, through the api (`POST /api/blimp/command`, `WS /api/blimp/telemetry`). This path is identical for the simulated and the real blimp. Commands are latched: the blimp keeps the last one until told otherwise.
- Lockstep, straight to the gateway (`WS /lockstep`), for training. The world is loaded with `mode: "lockstep"`; the simulation is paused except while executing a `step` of N ticks (1 tick = 1/60 s of simulated time). It runs at up to 20x real time.

**Gateway protocol with Godot** (`/sim`). Gateway to sim: `load` {world, profile, mode}, `command`, `step` {command, ticks}, `reset`. Sim to gateway: `hello`, `loaded`, `telemetry`, and `frame` (JSON header with telemetry and labels) immediately followed by one binary message holding the JPEG.

**Blimp model.** No pitch or roll. Quadratic plus linear drag per axis, first-order actuator lag, command latency, added mass. All parameters are in `BlimpProfile` and are placeholders: fit them to step-response flights of the real blimp when it exists.

**Labels.** A person's box is the bounding box of their visible keypoints (ankles, hands, shoulders, head top, chest, pelvis), each padded by the limb radius. `visibility` is the fraction of keypoints that are in frame and not behind geometry or another person.

## Key constraints

- **`SIM_SECRET` has no default** in the api or the gateway; both refuse to start without it. It must be the same on both hosts. Never commit it.
- **Godot `--headless` renders nothing.** The sim runs under Xvfb with `--rendering-driver vulkan`, which renders on the GPU (about 285 fps at 640x480 on vonk; CPU fallbacks manage about 7). `xvfb-run` hangs as PID 1, hence `entrypoint.sh`.
- **vonk is ARM64.** The Dockerfile downloads the `linux.arm64` Godot build; another GPU host needs a different download.
- **Repeatability depends on three things**, all easy to break: the navigation settings in `project.godot` (asynchronous map updates make the crowd differ between identical episodes), `NavigationServer3D.set_active(false)` while paused (`main.gd`), and never using `Engine.physics_ticks_per_second` as "ticks per simulated second" (lockstep multiplies it by 20; use the physics delta). `client/tests/test_sim_integration.py` checks all of it.
- **`class_name` scripts need the import step.** Without `godot --headless --import` at build time, scripts cannot see each other's classes.
- **People are procedural mannequins**, not rigged human models. Detectors trained only on these frames will not transfer to real footage. `person.gd` is written so the body can be swapped: keep `keypoints()` returning the same joints.
- **Datasets live in a Docker volume on vonk** (`blimpsim-sim_datasets`); the api only proxies them. `docker compose down -v` there deletes them.
- **The frontend dev server only answers for `APP_DOMAIN`** (`allowedHosts` in `vite.config.js`); the frontend container reads it from `.env`.
- **Schema is created with `create_all` on startup.** Adding a column to an existing table needs a migration or a dropped volume.
- **`RealDriver` is a stub.** Setting `BLIMP_DRIVER=real` makes every blimp endpoint return 503 until it is implemented.
