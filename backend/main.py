import os
import certifi

# Fix macOS SSL Certificate Verification for all modules
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["CURL_CA_BUNDLE"] = certifi.where()

import time
import json
import asyncio
from typing import List, Dict, Any, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

import database
import tools
from bot import run_websocket_bot

app = FastAPI(title="NexovCare Hospital Voice Agent API", version="1.0.0")

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

async def broadcast_event(data: Dict[str, Any]):
    """Broadcasts transcription and appointment updates to all connected frontend clients."""
    await manager.broadcast(data)

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "has_gemini": bool(os.getenv("GEMINI_API_KEY")),
        "has_elevenlabs": bool(os.getenv("ELEVENLABS_API_KEY")),
        "transport": "websocket"
    }

@app.get("/api/doctors")
async def get_doctors():
    """Returns list of doctors with their current slot availability from JSON."""
    return database.get_all_doctors_with_slots()

@app.get("/api/appointments")
async def get_appointments():
    """Returns all booked appointments from JSON."""
    return database.get_all_appointments()

# Dashboard Realtime Events WebSocket
@app.websocket("/ws")
async def websocket_dashboard(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# Bidirectional Voice Call Audio WebSocket
@app.websocket("/ws/call")
async def websocket_call(websocket: WebSocket):
    await websocket.accept()
    try:
        await run_websocket_bot(websocket, broadcast_event)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Call session ended: {e}")

# Mount static frontend
from fastapi.staticfiles import StaticFiles
frontend_path = os.path.join(os.path.dirname(__file__), "../frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    database.init_db()
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
