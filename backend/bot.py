import os
import sys
import asyncio
import aiohttp
from typing import Callable, Optional, Dict, Any

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.transports.daily.transport import DailyTransport, DailyParams
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.elevenlabs.stt import ElevenLabsSTTService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.processors.aggregators.llm_response_universal import LLMUserAggregator, LLMAssistantAggregator
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import TranscriptionFrame, TextFrame, TTSSpeakFrame

import tools

SYSTEM_INSTRUCTION = """
You are 'Cura', an intelligent and empathetic voice receptionist at CuraClinic.
Your job is to assist callers in scheduling, checking, and managing their doctor appointments over the phone.

The clinic has these doctors:
1. Dr. Sarah Jenkins - Cardiology
2. Dr. Rajesh Sharma - General Medicine
3. Dr. Emily Watson - Dermatology
4. Dr. Michael Chang - Pediatrics

Available dates are today and tomorrow (e.g., 2026-11-26 and 2026-11-27) with slots at 09:00 AM, 10:30 AM, 02:00 PM, and 04:30 PM.

YOUR THREE CAPABILITIES:
1. Check doctor availability: Call the `check_doctor_availability` tool to look up open slots by doctor name, specialty, or date.
2. Book an appointment: Call the `book_appointment` tool with the caller's phone number, doctor name, and time slot.
3. Cancel an existing appointment: Call the `cancel_appointment` tool using the caller's phone number.

STRICT CONVERSATIONAL RULES:
- Identification: Callers are identified ONLY by the phone number they speak out loud. Never ask for email, passwords, login, or OTP.
- MANDATORY PHONE CONFIRMATION: Before you book or cancel an appointment, you MUST repeat the phone number back to the caller digit-by-digit or naturally to confirm it (e.g. 'To confirm, I have your phone number as 9 8 7, 6 5 4, 3 2 1 0. Is that correct?').
- Only execute `book_appointment` or `cancel_appointment` AFTER the caller says yes/confirms.
- Conversational tone: Speak naturally, warmly, and concisely (1-2 sentences per turn), like a real receptionist. Avoid robotic or overly long lists.
- You can check slots, book, and cancel within the same phone call if the caller requests multiple actions.
"""

class TranscriptBroadcaster(FrameProcessor):
    def __init__(self, broadcast_fn: Optional[Callable[[Dict[str, Any]], Any]] = None):
        super().__init__()
        self.broadcast_fn = broadcast_fn

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if self.broadcast_fn:
            if isinstance(frame, TranscriptionFrame) and frame.text.strip():
                await self.broadcast_fn({
                    "type": "transcript",
                    "speaker": "user",
                    "text": frame.text.strip()
                })
            elif isinstance(frame, TextFrame) and frame.text.strip():
                await self.broadcast_fn({
                    "type": "transcript",
                    "speaker": "assistant",
                    "text": frame.text.strip()
                })
        await self.push_frame(frame, direction)

async def run_bot(
    room_url: str,
    token: Optional[str] = None,
    broadcast_fn: Optional[Callable[[Dict[str, Any]], Any]] = None
):
    gemini_key = os.getenv("GEMINI_API_KEY")
    eleven_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM") # Rachel

    if not gemini_key or not eleven_key:
        raise ValueError("Missing GEMINI_API_KEY or ELEVENLABS_API_KEY in environment.")

    async with aiohttp.ClientSession() as aiohttp_session:
        # 1. Transport (Daily WebRTC + Silero VAD)
        vad = SileroVADAnalyzer()
        transport = DailyTransport(
            room_url=room_url,
            token=token,
            bot_name="Cura Voice Receptionist",
            params=DailyParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_enabled=True,
                vad_analyzer=vad,
                vad_audio_passthrough=True
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
            settings=GoogleLLMService.Settings(model="gemini-2.5-flash"),
            system_instruction=SYSTEM_INSTRUCTION
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
            description="Cancel an active appointment using the caller's confirmed phone number.",
            properties={
                "patient_phone": {"type": "string", "description": "Caller's confirmed phone number"}
            },
            required=["patient_phone"]
        )

        tools_schema = ToolsSchema([tool_check_availability, tool_book_appointment, tool_cancel_appointment])
        context = LLMContext(tools=tools_schema)

        # Register Handlers
        async def handle_check_availability(params):
            args = params.arguments
            res = tools.check_doctor_availability(
                doctor_name=args.get("doctor_name"),
                date=args.get("date"),
                specialty=args.get("specialty")
            )
            await params.result_callback(res)

        async def handle_book_appointment(params):
            args = params.arguments
            res = tools.book_appointment(
                patient_phone=args.get("patient_phone", ""),
                doctor_name=args.get("doctor_name", ""),
                slot_time=args.get("slot_time", ""),
                slot_date=args.get("slot_date"),
                patient_name=args.get("patient_name")
            )
            if res.get("success") and broadcast_fn:
                await broadcast_fn({"type": "database_update", "action": "booked", "data": res})
            await params.result_callback(res)

        async def handle_cancel_appointment(params):
            args = params.arguments
            res = tools.cancel_appointment(patient_phone=args.get("patient_phone", ""))
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

        pipeline = Pipeline([
            transport.input(),
            stt,
            broadcaster,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator
        ])

        task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            greeting = "Hello! Welcome to CuraClinic appointment desk. How may I assist you today?"
            if broadcast_fn:
                await broadcast_fn({"type": "transcript", "speaker": "assistant", "text": greeting})
            await task.queue_frame(TTSSpeakFrame(greeting))

        runner = PipelineRunner()
        await runner.run(task)
