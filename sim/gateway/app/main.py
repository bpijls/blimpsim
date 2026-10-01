"""Gateway between the Godot simulator and everything that uses it.

Godot connects to /sim as a WebSocket client. The api (on another host) loads
worlds, sends commands, and reads telemetry and camera frames through the rest.
Payloads are passed through as-is: the api validates them against the contracts.
"""
import hmac

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.link import SimLink, SimUnavailable
from app.recorder import NAME_PATTERN, Recorder, RecorderError

app = FastAPI(title="blimpsim gateway")
link = SimLink()
recorder = Recorder(settings.datasets_dir)
link.on_frame = recorder.add


def _secret_ok(candidate: str | None) -> bool:
    return candidate is not None and hmac.compare_digest(candidate, settings.sim_secret)


def require_secret(request: Request) -> None:
    if not _secret_ok(request.headers.get("x-sim-secret")):
        raise HTTPException(401, "Missing or wrong X-Sim-Secret")


async def _accept_with_secret(socket: WebSocket) -> bool:
    if _secret_ok(socket.query_params.get("secret")):
        return True
    await socket.close(code=4401)
    return False


async def _send(message: dict) -> None:
    try:
        await link.send(message)
    except SimUnavailable as e:
        raise HTTPException(503, str(e)) from e


@app.get("/healthz")
async def healthz() -> dict:
    return {
        "status": "ok",
        "sim_connected": link.connected,
        "sim": link.hello,
        "loaded": link.load_message is not None,
        "recording": recorder.status(),
    }


@app.post("/load", dependencies=[Depends(require_secret)])
async def load(body: dict) -> dict:
    """Body: {world, profile, mode}. Replaces whatever the simulator was running."""
    try:
        await link.load({"type": "load", **body})
    except SimUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return {"status": "loading"}


@app.post("/command", dependencies=[Depends(require_secret)])
async def command(body: dict) -> dict:
    await _send({**body, "type": "command"})
    return {"status": "sent"}


@app.get("/telemetry", dependencies=[Depends(require_secret)])
async def latest_telemetry() -> dict:
    if link.telemetry is None:
        raise HTTPException(404, "No telemetry yet")
    return link.telemetry


@app.get("/labels", dependencies=[Depends(require_secret)])
async def latest_labels() -> dict:
    """Ground truth for the frame currently served by /frame.jpg."""
    if link.frame_meta is None:
        raise HTTPException(404, "No frame yet")
    return link.frame_meta.get("labels", {})


@app.get("/frame.jpg", dependencies=[Depends(require_secret)])
async def frame() -> Response:
    if link.frame is None:
        raise HTTPException(404, "No frame yet")
    return Response(link.frame, media_type="image/jpeg")


@app.get("/stream.mjpg", dependencies=[Depends(require_secret)])
async def stream() -> StreamingResponse:
    async def frames():
        last = 0
        while True:
            last, _, jpeg = await link.next_frame(after=last)
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/telemetry")
async def telemetry_stream(socket: WebSocket) -> None:
    if not await _accept_with_secret(socket):
        return
    await socket.accept()
    queue = link.subscribe()
    try:
        while True:
            await socket.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        link.unsubscribe(queue)


@app.websocket("/sim")
async def sim(socket: WebSocket) -> None:
    if not await _accept_with_secret(socket):
        return
    await link.serve(socket)


# ── Lockstep (training) ──────────────────────────────────────────────────────


@app.websocket("/lockstep")
async def lockstep(socket: WebSocket) -> None:
    """Request/response stepping for a world loaded with mode "lockstep".

    The client sends {"type": "observe"} (the frame after a load or reset),
    {"type": "reset"} or {"type": "step", "command": {...}, "ticks": n}.
    Each is answered with the frame header as JSON, then the JPEG as binary.
    """
    if not await _accept_with_secret(socket):
        return
    await socket.accept()
    seen = 0
    try:
        while True:
            request = await socket.receive_json()
            if request.get("type") != "observe":
                seen = link.frame_seq
                try:
                    await link.send(request)
                except SimUnavailable as e:
                    await socket.send_json({"type": "error", "detail": str(e)})
                    continue
            seen, meta, jpeg = await link.next_frame(after=seen)
            await socket.send_json(meta)
            await socket.send_bytes(jpeg)
    except WebSocketDisconnect:
        pass


# ── Datasets ─────────────────────────────────────────────────────────────────


class RecordIn(BaseModel):
    name: str = Field(pattern=NAME_PATTERN)
    every: int = Field(1, ge=1, description="Keep every n-th camera frame")
    max_frames: int = Field(1000, ge=1, le=100_000)


@app.get("/datasets", dependencies=[Depends(require_secret)])
async def list_datasets() -> list[dict]:
    return recorder.list()


@app.post("/datasets", dependencies=[Depends(require_secret)], status_code=201)
async def start_recording(body: RecordIn) -> dict:
    try:
        recorder.start(body.name, body.every, body.max_frames)
    except RecorderError as e:
        raise HTTPException(409, str(e)) from e
    return recorder.status()


@app.post("/datasets/stop", dependencies=[Depends(require_secret)])
async def stop_recording() -> dict:
    summary = recorder.stop()
    if summary is None:
        raise HTTPException(409, "Nothing is being recorded")
    return summary


@app.get("/datasets/{name}/annotations", dependencies=[Depends(require_secret)])
async def annotations(name: str) -> FileResponse:
    return _dataset_file(name, "annotations.json")


@app.get("/datasets/{name}/images/{file}", dependencies=[Depends(require_secret)])
async def image(name: str, file: str) -> FileResponse:
    return _dataset_file(name, "images", file)


def _dataset_file(name: str, *parts: str) -> FileResponse:
    path = recorder.path(name, *parts)
    if path is None:
        raise HTTPException(404, "No such dataset file")
    return FileResponse(path)
