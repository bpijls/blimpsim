# blimpsim

Digital twin of a camera blimp that tracks people in a large indoor space.

A Godot 4 simulator renders a generated hall, a walking crowd and the blimp's onboard camera on a GPU host. A FastAPI backend steers the blimp through a driver layer that can later be pointed at the real hardware, and a browser page shows the hall, the blimp, the camera's footprint and the live camera feed.

It is built for two things:

- **Developing the tracker.** A Gymnasium environment gives a controller camera frames and takes steering commands, repeatably and faster than real time.
- **Training a detector.** Camera frames can be recorded as a COCO dataset with a box, a track id and a visibility score for every person.

## Getting started

```bash
./setup.sh           # creates .env; fill in what it asks for and run it again
./sim/deploy.sh      # builds and starts the simulator on the GPU host (SIM_HOST in .env)
```

Open `https://<APP_DOMAIN>`, generate a hall, press **Run**. Steer with W/S (forward, back), A/D (turn) and R/F (up, down).

**Remote control** in the header opens `https://<APP_DOMAIN>/remote.html` in its own window: the camera feed full size, with the same keys and on-screen buttons to hold.

The HTTP and WebSocket interfaces are described in [docs/API.md](docs/API.md).

## Training against the simulator

```bash
uv venv .venv && uv pip install -p .venv/bin/python -e client
export BLIMPSIM_API_URL=https://blimpsim.paws.home BLIMPSIM_GATEWAY_URL=http://vonk:8100 SIM_SECRET=...
```

```python
from blimpsim_client import BlimpTrackEnv

env = BlimpTrackEnv(scenario_params={"people": 40}, profile_spread=0.2)
frame, info = env.reset(seed=3)                    # frame: uint8 (480, 640, 3)
frame, reward, _, truncated, info = env.step([0.5, 0.0, 0.0])   # surge, yaw, heave
info["labels"]["people"]                            # ground-truth boxes for this frame
```

`python -m blimpsim_client.baseline --seed 5` runs the reference controller, which steers from the target's ground-truth box.

## What is not here yet

- The real blimp. Its API and flight characteristics are unknown; `RealDriver` is a stub and the airframe parameters are guesses.
- Realistic people. The crowd is made of simple mannequins.
- A trained model. The twin provides the environment, the data and a baseline.

See `CLAUDE.md` for the architecture, the wire protocols and the constraints worth knowing before changing anything.
