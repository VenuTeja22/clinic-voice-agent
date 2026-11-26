# NexovCare Hospital — Autonomous Voice AI Doctor Appointment Assistant

The system enables callers to check specialist availability, book outpatient consultations, and manage cancellations via natural voice using **spoken phone-number identity** with **mandatory confirmation read-back**. The frontend is engineered with an authentic **Clinical Hospital Theme**, auto-updating instantaneously via WebSockets as the voice assistant operates.

---

## 1. System Architecture & Pipeline

```mermaid
flowchart LR
    CallerMic["Caller Mic (Browser Web Audio)"] -->|16kHz 16-bit PCM| WSCall["WebSocket (/ws/call)"]
    WSCall --> VAD["Silero VAD (ONNX Runtime)"]
    VAD --> STT["ElevenLabs Real-Time STT"]
    STT --> Broadcaster["Transcript & State Broadcaster"]
    Broadcaster --> LLM["Google Gemini 3.5 Flash Lite"]
    LLM --> Tools["Function Calling (tools.py)"]
    Tools --> JSONStore[("clinic_data.json")]
    JSONStore --> Tools
    Tools --> LLM
    LLM --> TTS["ElevenLabs Neural TTS (Bella Voice)"]
    TTS -->|24kHz Raw PCM| WSCall
    WSCall --> CallerSpk["Caller Speaker (AudioContext)"]
    Broadcaster -->|Live Events /ws| Dashboard["Clinical Hospital Live Dashboard"]
```

### How the Pipeline Works (Step-by-Step)

Here is what happens under the hood from the moment a caller starts a conversation:

1. **Audio Capture in the Browser (`frontend/app.js`)**:
   When the user clicks the call button, the browser requests microphone access through the Web Audio API. Because standard microphones capture at 44.1kHz or 48kHz, the client downsamples the stream in real time to **16kHz 16-bit Mono PCM**. These raw audio chunks are streamed directly to the backend over a dedicated binary WebSocket (`/ws/call`). This approach keeps the system fully self-contained—there is no need for third-party WebRTC room tokens or cloud media servers.

2. **Voice Activity Detection & Interruption (`backend/bot.py`)**:
   As audio chunks hit the server, Pipecat routes them through a local **Silero VAD** model running via ONNX Runtime. Silero listens for speech boundaries in milliseconds. If the caller speaks while the assistant is talking, Silero flags it immediately, halts the outgoing speech synthesis, and clears the playback buffer. This allows callers to interrupt (barge-in) naturally at any point in the conversation.

3. **Speech-to-Text (`ElevenLabs STT`)**:
   Once Silero detects an end-of-speech pause, the speech frame is sent to **ElevenLabs Real-Time STT**. We use ElevenLabs here because it accurately transcribes doctor names and spoken digit sequences (phone numbers) without dropping numbers.

4. **Intent Handling & Tool Execution (`Google Gemini 3.5 Flash Lite` + `backend/tools.py`)**:
   The transcribed text is passed to Gemini Flash Lite along with conversation history and our function-calling schemas. Gemini was chosen because its response latency is consistently under 1.5 seconds and it adheres strictly to tool definitions:
   - When checking slots, Gemini calls `check_doctor_availability()`. The tool checks if the doctor is on leave and filters out any consultation hours that have already passed today.
   - When booking, the agent asks for the caller's phone number, reads it back for explicit confirmation, and then calls `book_appointment()` to lock in the slot and generate a reference ID.
   - When cancelling, `cancel_appointment()` pulls all appointments linked to that phone number. If multiple bookings exist, the assistant asks the caller which one to cancel before freeing the slot.

5. **Speech Synthesis & Playback (`ElevenLabs TTS` → Browser)**:
   Gemini's response text is streamed to **ElevenLabs Neural TTS** using the Bella voice. ElevenLabs generates 24kHz raw PCM audio frames, which travel back down the same `/ws/call` WebSocket to the browser. The frontend queues these frames inside the Web Audio `AudioContext` and plays them back cleanly.

6. **Live Dashboard Sync (`backend/main.py` → `frontend/app.js`)**:
   Alongside the audio WebSocket, the backend maintains a second WebSocket (`/ws`) for UI events. Whenever someone speaks or an appointment is booked or cancelled, the backend broadcasts a JSON event. The frontend catches this and updates the slot counts and appointment ledger table immediately, without a page reload.

---


## 2. Key Business Rules & Conversational Guardrails

* **Phone-Number Only Identification**: No accounts, logins, or OTP passwords required. Patients are identified strictly by their spoken phone number.
* **Mandatory Phone Read-Back Confirmation**: Before executing any booking or cancellation, the agent **always reads back the phone number** to the caller to guarantee transcription accuracy (*"To confirm, I have your phone number as 98765-43210. Is that correct?"*).
* **Multi-Appointment Disambiguation**: If a patient has multiple active bookings under the same phone number and requests cancellation, the agent reads out all matching appointments and prompts the caller to select which specific consultation to cancel.
* **Dynamic Rolling Date Auto-Seeding**: The application automatically seeds and maintains slots for **Today** and **Tomorrow** dynamically on any day the app runs, without overwriting past patient bookings.
* **Real-Time Past-Slot Protection**: Slots earlier than the current local clock time today are automatically filtered out and blocked from booking.
* **Clinical Boundary Protection**: The agent strictly declines to provide medical advice or diagnoses, steering callers to book an outpatient consultation.

---

## 3. Project Structure

```text
clinic-voice-agent/
├── backend/
│   ├── main.py            # FastAPI app, WebSockets (/ws, /ws/call), static asset server
│   ├── bot.py             # Pipecat audio pipeline (Silero VAD, STT, Gemini LLM, TTS)
│   ├── tools.py           # Function calling tools for availability, booking, cancel
│   ├── database.py        # Clean JSON database manager & rolling date seeder
│   ├── clinic_data.json   # Seeded data (6 doctors, multiple slots, appointments)
│   ├── requirements.txt   # Python dependencies (Pipecat, FastAPI, Uvicorn, etc.)
│   └── venv/              # Python virtual environment
├── frontend/
│   ├── index.html         # Clinical hospital portal & telehealth call modal
│   ├── style.css          # Professional medical design system & responsive layout
│   └── app.js             # Web Audio API 16kHz PCM streaming & 24kHz playback
├── .env.example           # Example environment template
├── .gitignore             # Git ignore file
└── README.md              # Project documentation
```

---

## 4. Setup & Running

### Prerequisites
* **Python 3.10+** (Tested on Python 3.12)
* **Google Gemini API Key** (from [Google AI Studio](https://aistudio.google.com/))
* **ElevenLabs API Key** (from [ElevenLabs](https://elevenlabs.io/))

### 1. Configure Environment Variables
Create `backend/.env` (or copy from `.env.example`):
```env
# Gemini LLM Key (from Google AI Studio)
GEMINI_API_KEY=your_gemini_api_key_here

# ElevenLabs STT & TTS (from https://elevenlabs.io/)
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL

# Server Port
PORT=8000
```

### 2. Install Dependencies & Run Server
```bash
# Navigate to the project root
cd clinic-voice-agent

# Create virtual environment (if not already created)
python3 -m venv backend/venv
source backend/venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Start the unified backend & frontend server
python backend/main.py
```

Open **`http://localhost:8000`** in your browser.

---

## 5. Demo Walkthrough Flow 

1. **Dashboard Overview**:
   - Navigate to `http://localhost:8000`. The hospital portal displays the 24/7 emergency ribbon, active clinical specialists, real-time Today & Tomorrow schedule grid, and the live Patient Appointment Ledger.
2. **Launch Call**:
   - Click **"Call Voice Desk"**. The telehealth smartphone screen opens.
   - Allow browser microphone access.
3. **Agent Greeting**:
   - Cura immediately greets: *"Hello! Welcome to NexovCare Hospital appointment desk. How may I assist you today?"*
4. **Availability Inquiry**:
   - Say: *"Can you check availability for Dr. Sarah Jenkins tomorrow?"*
   - Cura invokes `check_doctor_availability` and speaks back open slots (e.g., 09:00 AM, 10:30 AM).
5. **Booking with Confirmation**:
   - Say: *"Please book the 10:30 AM slot. My phone number is 98765-43210."*
   - Cura reads back the number: *"I have your phone number as 9 8 7, 6 5 4, 3 2 1 0. Is that correct?"*
   - Say: *"Yes, that is correct."*
   - Cura confirms the booking. The **Patient Appointment Ledger** on the dashboard immediately updates in real time with the new booking!
6. **Cancellation**:
   - Say: *"I also need to cancel an appointment under phone number 555-0199."*
   - Cura confirms: *"To confirm, you want to cancel the appointment under 5 5 5, 0 1 9 9, is that correct?"*
   - Say: *"Yes."*
   - Cura cancels the slot, and the dashboard reflects the cancellation instantly.
7. **End Call**:
   - Click the red **End Call** button.

---

## 6. Live Terminal Observability

Every conversational turn is logged directly to the server terminal with clear speaker attribution:
```text
🗣️  [CALLER]: Can you check availability for Dr. Sarah Jenkins tomorrow?
🤖 [CURA ASSISTANT]: Dr. Sarah Jenkins has available slots tomorrow at 09:00 AM and 10:30 AM. Would you like me to book one of these for you?
🗣️  [CALLER]: Let's book the 10:30 AM slot. My phone is 98765 43210.
🤖 [CURA ASSISTANT]: I have your phone number as 98765-43210. Can you confirm that this is correct before I complete the booking?
🗣️  [CALLER]: Yes that is correct.
🤖 [CURA ASSISTANT]: You're all set! I have booked your appointment with Dr. Sarah Jenkins for tomorrow at 10:30 AM.
```
---
