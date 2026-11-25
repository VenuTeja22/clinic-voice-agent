import os
import time
import json
import asyncio
from typing import List, Dict, Any, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import aiohttp
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

import database
import tools
from bot import run_bot

app = FastAPI(title="CuraClinic Voice Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections for dashboard live events
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# Background Pipecat bot task tracking
active_bot_tasks: Dict[str, asyncio.Task] = {}

async def broadcast_event(data: Dict[str, Any]):
    """Broadcasts transcription and appointment updates to all connected frontend clients."""
    await manager.broadcast(data)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "has_gemini": bool(os.getenv("GEMINI_API_KEY")),
        "has_elevenlabs": bool(os.getenv("ELEVENLABS_API_KEY")),
        "has_daily": bool(os.getenv("DAILY_API_KEY")),
    }

@app.get("/api/doctors")
async def get_doctors():
    """Returns list of doctors with their current slot availability."""
    return database.get_all_doctors_with_slots()

@app.get("/api/appointments")
async def get_appointments():
    """Returns all booked appointments."""
    return database.get_all_appointments()

async def create_daily_room_and_tokens() -> Dict[str, str]:
    """Creates a temporary room on Daily.co and returns bot token + user token."""
    daily_key = os.getenv("DAILY_API_KEY")
    if not daily_key:
        raise HTTPException(status_code=500, detail="DAILY_API_KEY not configured in .env")

    headers = {
        "Authorization": f"Bearer {daily_key}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        # Create Room (expires in 2 hours)
        room_payload = {
            "properties": {
                "exp": int(time.time()) + 7200,
                "enable_chat": True,
                "enable_screenshare": False
            }
        }
        async with session.post("https://api.daily.co/v1/rooms", headers=headers, json=room_payload) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                raise HTTPException(status_code=resp.status, detail=f"Failed to create Daily room: {text}")
            room_data = await resp.json()
            room_url = room_data["url"]
            room_name = room_data["name"]

        # Create Bot Token (Owner)
        bot_token_payload = {
            "properties": {
                "room_name": room_name,
                "is_owner": True,
                "user_name": "Cura Clinic AI"
            }
        }
        async with session.post("https://api.daily.co/v1/meeting-tokens", headers=headers, json=bot_token_payload) as resp:
            bot_token_data = await resp.json()
            bot_token = bot_token_data.get("token")

        # Create Client/Caller Token
        client_token_payload = {
            "properties": {
                "room_name": room_name,
                "is_owner": False,
                "user_name": "Patient"
            }
        }
        async with session.post("https://api.daily.co/v1/meeting-tokens", headers=headers, json=client_token_payload) as resp:
            client_token_data = await resp.json()
            client_token = client_token_data.get("token")

    return {
        "room_url": room_url,
        "room_name": room_name,
        "bot_token": bot_token,
        "client_token": client_token
    }

@app.post("/api/call/start")
async def start_call():
    """Initializes Daily WebRTC room and spawns the Pipecat agent."""
    try:
        daily_info = await create_daily_room_and_tokens()
        room_url = daily_info["room_url"]
        room_name = daily_info["room_name"]
        bot_token = daily_info["bot_token"]
        client_token = daily_info["client_token"]

        # Launch Pipecat runner as background task
        task = asyncio.create_task(
            run_bot(
                room_url=room_url,
                token=bot_token,
                broadcast_fn=broadcast_event
            )
        )
        active_bot_tasks[room_name] = task

        return {
            "success": True,
            "room_url": room_url,
            "room_name": room_name,
            "token": client_token
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/call/end")
async def end_call(payload: Dict[str, str]):
    room_name = payload.get("room_name")
    if room_name and room_name in active_bot_tasks:
        task = active_bot_tasks.pop(room_name)
        task.cancel()
        return {"success": True, "message": "Call session ended"}
    return {"success": True, "message": "No active session found"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive & listen for client ping/messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    database.init_db()
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
