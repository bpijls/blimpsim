"""The one connection to the Godot simulator, and fan-out of what it sends."""
import asyncio
import json
from collections.abc import Callable

from fastapi import WebSocket

SUBSCRIBER_QUEUE = 8


class SimUnavailable(Exception):
    pass


class SimLink:
    def __init__(self) -> None:
        self.socket: WebSocket | None = None
        self.hello: dict | None = None
        self.load_message: dict | None = None
        self.telemetry: dict | None = None
        self.frame: bytes | None = None
        self.frame_meta: dict | None = None
        # Counts frames received, unlike the simulator's own frame number, which
        # restarts at 0 with every load.
        self.frame_seq = 0
        # True between sending a load and the simulator confirming it. Frames
        # still in flight from the previous world are dropped meanwhile.
        self._loading = False
        self.on_frame: Callable[[dict, bytes], None] | None = None
        self._new_frame = asyncio.Condition()
        self._subscribers: set[asyncio.Queue] = set()

    @property
    def connected(self) -> bool:
        return self.socket is not None

    async def send(self, message: dict) -> None:
        if self.socket is None:
            raise SimUnavailable("simulator is not connected")
        await self.socket.send_text(json.dumps(message))

    async def load(self, message: dict) -> None:
        await self.send(message)
        # Kept so a restarted simulator comes back with the same world.
        self.load_message = message
        self.frame = self.frame_meta = self.telemetry = None
        self._loading = True

    async def serve(self, socket: WebSocket) -> None:
        """Run the receive loop for the simulator's connection until it drops."""
        await socket.accept()
        self.socket = socket
        pending_meta: dict | None = None
        try:
            while True:
                event = await socket.receive()
                if event["type"] == "websocket.disconnect":
                    return
                if event.get("bytes") is not None:
                    if pending_meta is not None and not self._loading:
                        await self._on_frame(pending_meta, event["bytes"])
                    pending_meta = None
                    continue
                message = json.loads(event["text"])
                kind = message.get("type")
                if kind == "loaded":
                    self._loading = False
                elif kind == "frame":
                    pending_meta = message
                elif kind == "telemetry":
                    if not self._loading:
                        self._publish(message["telemetry"])
                elif kind == "hello":
                    self.hello = message
                    if self.load_message is not None:
                        await self.send(self.load_message)
        finally:
            if self.socket is socket:
                self.socket = None
                self.hello = None

    async def next_frame(self, after: int = 0) -> tuple[int, dict, bytes]:
        """The latest frame as (seq, meta, jpeg), waiting until one newer than `after`."""
        async with self._new_frame:
            await self._new_frame.wait_for(
                lambda: self.frame is not None and self.frame_seq > after
            )
            return self.frame_seq, self.frame_meta, self.frame

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    async def _on_frame(self, meta: dict, jpeg: bytes) -> None:
        async with self._new_frame:
            self.frame_meta, self.frame = meta, jpeg
            self.frame_seq += 1
            self._new_frame.notify_all()
        if self.on_frame is not None:
            self.on_frame(meta, jpeg)
        self._publish(meta["telemetry"])

    def _publish(self, telemetry: dict) -> None:
        self.telemetry = telemetry
        for queue in self._subscribers:
            if queue.full():
                queue.get_nowait()  # a slow reader gets the newest state, not a backlog
            queue.put_nowait(telemetry)
