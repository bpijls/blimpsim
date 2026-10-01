"""Steering, telemetry and camera for whichever blimp the driver points at."""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.contracts import BlimpCommand
from app.services.drivers import BlimpDriver, DriverUnavailable, get_driver

router = APIRouter(prefix="/api/blimp", tags=["blimp"])


@router.get("/status")
async def status(driver: BlimpDriver = Depends(get_driver)) -> dict:
    return await driver.status()


@router.post("/command")
async def command(payload: BlimpCommand, driver: BlimpDriver = Depends(get_driver)) -> dict:
    try:
        await driver.send(payload)
    except DriverUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return {"status": "sent", "command": payload}


@router.get("/camera.mjpg")
async def camera(driver: BlimpDriver = Depends(get_driver)) -> StreamingResponse:
    stream = driver.camera()
    try:
        first = await anext(stream)
    except (DriverUnavailable, StopAsyncIteration) as e:
        raise HTTPException(503, str(e) or "no camera stream") from e

    async def chunks():
        yield first
        try:
            async for chunk in stream:
                yield chunk
        except DriverUnavailable:
            return

    return StreamingResponse(chunks(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.websocket("/telemetry")
async def telemetry(socket: WebSocket, driver: BlimpDriver = Depends(get_driver)) -> None:
    await socket.accept()
    try:
        async for message in driver.telemetry():
            await socket.send_json(message)
    except DriverUnavailable as e:
        await socket.close(code=1013, reason=str(e)[:120])
    except WebSocketDisconnect:
        pass
