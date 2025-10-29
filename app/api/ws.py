from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/ws", tags=["ws"])


class WebSocketHub:
    def __init__(self) -> None:
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.rooms.setdefault(room_id, set()).add(ws)

    def disconnect(self, room_id: str, ws: WebSocket) -> None:
        if room_id in self.rooms:
            self.rooms[room_id].discard(ws)
            if not self.rooms[room_id]:
                del self.rooms[room_id]

    async def broadcast(self, room_id: str, message: dict) -> None:
        for ws in list(self.rooms.get(room_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(room_id, ws)


hub = WebSocketHub()


@router.websocket("")
async def websocket_entry(ws: WebSocket):
    # Expect X-Client-Id header
    client_id = ws.headers.get("X-Client-Id")
    room = client_id or "anonymous"
    await hub.connect(room, ws)
    try:
        while True:
            # Keep alive or handle client pings
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(room, ws)


async def push_event(client_id: str, event: dict) -> None:
    await hub.broadcast(client_id, event)

from fastapi import Depends, HTTPException
from pydantic import BaseModel

class DevPush(BaseModel):
    client_id: str
    event: dict

@router.post("/dev/push")
async def dev_push(body: DevPush):
    if not body.client_id:
        raise HTTPException(status_code=400, detail="client_id required")
    await push_event(body.client_id, body.event)
    return {"ok": True}

from fastapi import Depends, HTTPException
from pydantic import BaseModel

class DevPush(BaseModel):
    client_id: str
    event: dict

@router.post("/dev/push")
async def dev_push(body: DevPush):
    if not body.client_id:
        raise HTTPException(status_code=400, detail="client_id required")
    await push_event(body.client_id, body.event)
    return {"ok": True}