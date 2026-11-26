import os
import certifi

# Fix macOS SSL Certificate Verification for all modules
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["CURL_CA_BUNDLE"] = certifi.where()

import aiohttp
from typing import Callable, Optional, Dict, Any
from fastapi import WebSocket

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.frames.frames import (
    InputAudioRawFrame,
    OutputAudioRawFrame,
    AudioRawFrame,
    TTSAudioRawFrame,
    Frame,
    TranscriptionFrame,
    TextFrame,
    TTSSpeakFrame,
    LLMRunFrame
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.elevenlabs.stt import ElevenLabsSTTService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.processors.aggregators.llm_response_universal import LLMUserAggregator, LLMAssistantAggregator
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

import tools
from datetime import datetime, timedelta

def get_system_instruction() -> str:
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    now_time = now.strftime("%I:%M %p")

    return f"""You are 'Cura', a dedicated, professional voice receptionist at NexovCare Hospital.
Your single responsibility is to assist callers in checking doctor availability, scheduling appointments, and cancelling appointments.

The hospital has these consulting specialists:
1. Dr. Sarah Jenkins - Cardiology
2. Dr. Rajesh Sharma - General Medicine
3. Dr. Emily Watson - Dermatology
4. Dr. Michael Chang - Pediatrics
5. Dr. Ananya Iyer - Orthopedics
6. Dr. David Miller - Neurology (Currently ON LEAVE)

DOCTOR ON LEAVE INSTRUCTION:
- Dr. David Miller is on leave. If a caller asks about Dr. David Miller or Neurology appointments, inform them politely that Dr. David Miller is currently on scheduled leave and not taking appointments today or tomorrow. Offer to help them with other available specialists.

Available dates are today ({today_str}) and tomorrow ({tomorrow_str}).

TIME AWARENESS & PAST SLOTS RULE:
- Today is {today_str} and the current local time is {now_time}.
- NEVER offer expired or past time slots for today. For today ({today_str}), only upcoming time slots after {now_time} returned by `check_doctor_availability` can be offered.
- For tomorrow ({tomorrow_str}), all morning and afternoon slots (09:00 AM, 10:30 AM, 02:00 PM, 04:30 PM) are open and valid.
- Always call `check_doctor_availability` with the caller's requested date ('today', 'tomorrow', or 'YYYY-MM-DD') to retrieve valid open slots.

YOUR THREE EXCLUSIVE CAPABILITIES:
1. Check doctor availability (`check_doctor_availability`)
2. Book an appointment (`book_appointment`)
3. Cancel an existing appointment (`cancel_appointment`)

STRICT DOMAIN GUARDRAILS & SCOPE BOUNDARIES:
- ABSOLUTELY NO OFF-TOPIC ANSWERS: You must NEVER answer questions outside hospital appointment management. If a caller asks about general knowledge, coding, weather, recipes, politics, trivia, or general chit-chat, politely decline and steer them back:
  "I am only able to assist with scheduling, checking doctor availability, or cancelling appointments at NexovCare Hospital. How can I help you with your appointment today?"
- NO MEDICAL ADVICE OR DIAGNOSES: If a caller describes symptoms or asks for medical advice, diagnoses, or prescriptions, never diagnose or prescribe. Respond:
  "I cannot provide medical advice. I would be happy to schedule a consultation with one of our physicians, such as Dr. Rajesh Sharma in General Medicine. Would you like to check available slots?"
- EMERGENCY PROTOCOL: If the caller mentions severe pain, difficulty breathing, chest pain, or an acute emergency:
  "If this is a medical emergency, please hang up and call 911 or your nearest emergency room immediately."

CONVERSATIONAL RULES:
- Identification: Callers are identified ONLY by the phone number they speak out loud. Never ask for email, passwords, login, or OTP.
- MANDATORY PHONE CONFIRMATION: Before you book or cancel an appointment, you MUST repeat the phone number back to the caller to confirm it (e.g., 'Just to confirm, I have your phone number as 9 8 7, 6 5 4, 3 2 1 0. Is that correct?').
- Only execute `book_appointment` or `cancel_appointment` AFTER the caller explicitly confirms.
- MULTIPLE APPOINTMENTS CANCELLATION:
  When a caller wants to cancel, call `cancel_appointment(patient_phone=...)`.
  If the tool returns `needs_clarification: True` with multiple appointments, read out all the appointments found and ask the caller which specific one they want to cancel (e.g. 'I found 2 active appointments under your number: one with Dr. Sarah Jenkins on Nov 26 at 10:30 AM, and one with Dr. Rajesh Sharma on Nov 27 at 02:00 PM. Which one would you like to cancel?').
  Once the caller specifies, call `cancel_appointment` again including `doctor_name` or `slot_time` to cancel only that particular appointment.
- Conversational tone: Speak naturally, warmly, and concisely (1-2 sentences per turn), like a real receptionist. Avoid robotic or overly long lists.
"""

class RawAudioSerializer(FrameSerializer):
    """Serializes raw audio frames to/from WebSocket binary messages."""
    async def serialize(self, frame: Frame):
        if isinstance(frame, (OutputAudioRawFrame, AudioRawFrame, TTSAudioRawFrame)):
            return frame.audio
        return None

    async def deserialize(self, data: bytes):
        if isinstance(data, (bytes, bytearray)) and len(data) > 0:
            return InputAudioRawFrame(audio=bytes(data), sample_rate=16000, num_channels=1)
        return None

class TranscriptBroadcaster(FrameProcessor):
    def __init__(self, broadcast_fn: Optional[Callable[[Dict[str, Any]], Any]] = None):
        super().__init__()
        self.broadcast_fn = broadcast_fn

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            print(f"\n🗣️  [CALLER]: {frame.text.strip()}", flush=True)
            if self.broadcast_fn:
                await self.broadcast_fn({
                    "type": "transcript",
                    "speaker": "user",
                    "text": frame.text.strip()
                })
        elif isinstance(frame, TextFrame) and frame.text.strip():
            print(f"\n🤖 [NEXOV ASSISTANT]: {frame.text.strip()}", flush=True)
            if self.broadcast_fn:
                await self.broadcast_fn({
                    "type": "transcript",
                    "speaker": "assistant",
                    "text": frame.text.strip()
                })
        await self.push_frame(frame, direction)

async def run_websocket_bot(
    websocket: WebSocket,
    broadcast_fn: Optional[Callable[[Dict[str, Any]], Any]] = None
):
    gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    eleven_key = (os.getenv("ELEVENLABS_API_KEY") or "").strip()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL").strip() # Bella (Free Tier)

    if not gemini_key or not eleven_key:
        raise ValueError("Missing GEMINI_API_KEY or ELEVENLABS_API_KEY in environment.")

    async with aiohttp.ClientSession() as aiohttp_session:
        # 1. Transport (FastAPI WebSocket + Silero VAD)
        vad = SileroVADAnalyzer()
        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                audio_in_sample_rate=16000,
                audio_out_sample_rate=24000,
                vad_enabled=True,
                vad_analyzer=vad,
                vad_audio_passthrough=True,
                serializer=RawAudioSerializer()
            )
        )

        # 2. STT (ElevenLabs)
        stt = ElevenLabsSTTService(
            api_key=eleven_key,
            aiohttp_session=aiohttp_session
        )

        # 3. TTS (ElevenLabs)
        tts = ElevenLabsTTSService(
            api_key=eleven_key,
            settings=ElevenLabsTTSService.Settings(voice=voice_id)
        )

        # 4. LLM (Google Gemini)
        llm = GoogleLLMService(
            api_key=gemini_key,
            settings=GoogleLLMService.Settings(
                model="gemini-3.5-flash-lite",
                system_instruction=get_system_instruction()
            )
        )

        # Tool Definitions
        tool_check_availability = FunctionSchema(
            name="check_doctor_availability",
            description="Check available slots for doctors by name, specialty, or date.",
            properties={
                "doctor_name": {"type": "string", "description": "Doctor's name, e.g. Dr. Sarah Jenkins"},
                "date": {"type": "string", "description": "Date formatted YYYY-MM-DD"},
                "specialty": {"type": "string", "description": "Medical specialty, e.g. Cardiology, Dermatology"}
            },
            required=[]
        )

        tool_book_appointment = FunctionSchema(
            name="book_appointment",
            description="Book an appointment slot for the patient using their confirmed phone number.",
            properties={
                "patient_phone": {"type": "string", "description": "Spoken phone number of caller"},
                "doctor_name": {"type": "string", "description": "Name of the doctor to book with"},
                "slot_time": {"type": "string", "description": "Slot time, e.g. 09:00 AM, 10:30 AM"},
                "slot_date": {"type": "string", "description": "Date of appointment, e.g. 2026-11-26"},
                "patient_name": {"type": "string", "description": "Optional caller name"}
            },
            required=["patient_phone", "doctor_name", "slot_time"]
        )

        tool_cancel_appointment = FunctionSchema(
            name="cancel_appointment",
            description="Cancel an active appointment using the caller's confirmed phone number. If caller has multiple appointments, doctor_name or slot_time/slot_date can specify which one to cancel.",
            properties={
                "patient_phone": {"type": "string", "description": "Caller's confirmed phone number"},
                "doctor_name": {"type": "string", "description": "Optional doctor name to cancel specific appointment if caller has multiple"},
                "slot_time": {"type": "string", "description": "Optional slot time to cancel specific appointment if caller has multiple"},
                "slot_date": {"type": "string", "description": "Optional slot date to cancel specific appointment if caller has multiple"}
            },
            required=["patient_phone"]
        )

        tools_schema = ToolsSchema([tool_check_availability, tool_book_appointment, tool_cancel_appointment])
        context = LLMContext(tools=tools_schema)

        # Register Handlers
        async def handle_check_availability(params):
            args = params.arguments
            print(f"\n🔧 [TOOL] Checking Availability: {args}", flush=True)
            res = tools.check_doctor_availability(
                doctor_name=args.get("doctor_name"),
                date=args.get("date"),
                specialty=args.get("specialty")
            )
            print(f"🔧 [TOOL RESULT]: {res.get('message')}", flush=True)
            await params.result_callback(res)

        async def handle_book_appointment(params):
            args = params.arguments
            print(f"\n🔧 [TOOL] Booking Appointment: {args}", flush=True)
            res = tools.book_appointment(
                patient_phone=args.get("patient_phone", ""),
                doctor_name=args.get("doctor_name", ""),
                slot_time=args.get("slot_time", ""),
                slot_date=args.get("slot_date"),
                patient_name=args.get("patient_name")
            )
            print(f"🔧 [TOOL RESULT]: {res.get('message') or res.get('error')}", flush=True)
            if res.get("success") and broadcast_fn:
                await broadcast_fn({"type": "database_update", "action": "booked", "data": res})
            await params.result_callback(res)

        async def handle_cancel_appointment(params):
            args = params.arguments
            print(f"\n🔧 [TOOL] Cancelling Appointment: {args}", flush=True)
            res = tools.cancel_appointment(
                patient_phone=args.get("patient_phone", ""),
                doctor_name=args.get("doctor_name"),
                slot_time=args.get("slot_time"),
                slot_date=args.get("slot_date")
            )
            print(f"🔧 [TOOL RESULT]: {res.get('message') or res.get('error')}", flush=True)
            if res.get("success") and broadcast_fn:
                await broadcast_fn({"type": "database_update", "action": "cancelled", "data": res})
            await params.result_callback(res)

        llm.register_function("check_doctor_availability", handle_check_availability)
        llm.register_function("book_appointment", handle_book_appointment)
        llm.register_function("cancel_appointment", handle_cancel_appointment)

        # Pipeline aggregators
        user_aggregator = LLMUserAggregator(context)
        assistant_aggregator = LLMAssistantAggregator(context)
        broadcaster = TranscriptBroadcaster(broadcast_fn=broadcast_fn)
        vad_processor = VADProcessor(vad_analyzer=vad)

        pipeline = Pipeline([
            transport.input(),
            vad_processor,
            stt,
            broadcaster,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator
        ])

        task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            print("Client connected via WebSocket, initiating conversation...")
            context.add_message({
                "role": "developer",
                "content": "Greet the caller warmly with 'Hello! Welcome to NexovCare Hospital appointment desk. How may I assist you today?'"
            })
            await task.queue_frame(LLMRunFrame())

        runner = PipelineRunner()
        await runner.run(task)
