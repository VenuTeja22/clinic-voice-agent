import React, { useState, useEffect, useRef } from 'react';
import { PhoneCall, Activity, Sparkles, CheckCircle2, ShieldCheck, Stethoscope } from 'lucide-react';
import { DoctorsList } from './components/DoctorsList';
import { AppointmentsList } from './components/AppointmentsList';
import { PhoneCallModal } from './components/PhoneCallModal';
import { Doctor, Appointment, TranscriptMessage } from './types';

export default function App() {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCalling, setIsCalling] = useState(false);
  const [roomData, setRoomData] = useState<{ roomUrl: string; token?: string; roomName: string } | null>(null);
  const [transcripts, setTranscripts] = useState<TranscriptMessage[]>([]);
  const [lastAction, setLastAction] = useState<{ action: string; message: string } | null>(null);
  const [apiReady, setApiReady] = useState(false);

  // Fetch initial data
  const fetchData = async () => {
    try {
      const [docsRes, aptsRes, healthRes] = await Promise.all([
        fetch('/api/doctors'),
        fetch('/api/appointments'),
        fetch('/api/health').catch(() => null),
      ]);

      if (docsRes.ok) {
        setDoctors(await docsRes.json());
      }
      if (aptsRes.ok) {
        setAppointments(await aptsRes.json());
      }
      if (healthRes && healthRes.ok) {
        setApiReady(true);
      }
    } catch (err) {
      console.error('Error fetching clinic data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000); // Polling fallback
    return () => clearInterval(interval);
  }, []);

  // WebSocket for real-time events
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    let ws: WebSocket;

    try {
      ws = new WebSocket(wsUrl);

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'transcript') {
            const newMsg: TranscriptMessage = {
              id: Math.random().toString(36).substring(7),
              speaker: payload.speaker,
              text: payload.text,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            };
            setTranscripts((prev) => [...prev, newMsg]);
          } else if (payload.type === 'database_update') {
            setLastAction({
              action: payload.action,
              message: payload.data?.message || `Appointment ${payload.action}`,
            });
            // Instantly refresh tables
            fetchData();
          }
        } catch (e) {
          console.error(e);
        }
      };
    } catch (e) {
      console.error('WebSocket connection failed:', e);
    }

    return () => {
      if (ws) ws.close();
    };
  }, []);

  const handleStartCall = async () => {
    try {
      setIsLoading(true);
      setTranscripts([]);
      setLastAction(null);

      const res = await fetch('/api/call/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        const errorData = await res.json();
        alert(`Failed to start call: ${errorData.detail || 'Check API keys in backend/.env'}`);
        return;
      }

      const data = await res.json();
      setRoomData({
        roomUrl: data.room_url,
        token: data.token,
        roomName: data.room_name,
      });
      setIsCalling(true);
    } catch (err) {
      console.error('Error starting call:', err);
      alert('Could not start call. Ensure the backend server is running.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-slate-200/80">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-teal-600 flex items-center justify-center text-white shadow-md shadow-teal-600/20">
              <Stethoscope className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold text-slate-900 tracking-tight">CuraClinic</span>
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-teal-50 text-teal-700 border border-teal-200">
                  Voice Assistant
                </span>
              </div>
              <p className="text-[11px] text-slate-500">Autonomous Doctor Appointment Management</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-[11px] font-medium text-emerald-700">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Pipeline Online (Pipecat + ElevenLabs + Gemini)
            </div>

            <button
              onClick={handleStartCall}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 active:scale-95 text-white text-xs font-semibold shadow-sm shadow-teal-600/30 transition-all duration-150"
            >
              <PhoneCall className="w-4 h-4 animate-bounce" />
              <span>Start Voice Call</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 py-8 flex-1 w-full space-y-6">
        {/* Banner Hero / Instructions */}
        <div className="rounded-2xl bg-gradient-to-r from-teal-900 via-teal-800 to-slate-900 text-white p-6 md:p-8 shadow-sm relative overflow-hidden">
          <div className="relative z-10 max-w-2xl">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/10 text-teal-200 text-xs font-medium backdrop-blur-sm mb-3">
              <Sparkles className="w-3.5 h-3.5 text-teal-300" />
              Real-time Voice AI Assistant
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
              Book and manage clinic appointments using natural voice.
            </h1>
            <p className="mt-2 text-sm text-slate-300 leading-relaxed">
              Click <strong className="text-white">Start Voice Call</strong> to speak directly with Cura. Simply state your phone number, check available doctor slots, and confirm your booking or cancellation.
            </p>

            <div className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-3 pt-4 border-t border-white/10 text-xs text-slate-300">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-teal-500/20 text-teal-300 border border-teal-400/30 flex items-center justify-center font-bold text-[10px]">1</span>
                <span>Speak phone number</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-teal-500/20 text-teal-300 border border-teal-400/30 flex items-center justify-center font-bold text-[10px]">2</span>
                <span>Agent confirms & reads back</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-teal-500/20 text-teal-300 border border-teal-400/30 flex items-center justify-center font-bold text-[10px]">3</span>
                <span>Instant live registry update</span>
              </div>
            </div>
          </div>
        </div>

        {/* Dashboard Grid */}
        <div className="space-y-6">
          <DoctorsList doctors={doctors} isLoading={isLoading} />
          <AppointmentsList appointments={appointments} isLoading={isLoading} />
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
        <p>CuraClinic Voice Agent • Built with Pipecat, ElevenLabs STT/TTS, Google Gemini, and Daily WebRTC</p>
      </footer>

      {/* Phone Screen Modal (Bonus Feature) */}
      {roomData && (
        <PhoneCallModal
          isOpen={isCalling}
          onClose={() => {
            setIsCalling(false);
            setRoomData(null);
          }}
          roomUrl={roomData.roomUrl}
          token={roomData.token}
          roomName={roomData.roomName}
          transcripts={transcripts}
          lastAction={lastAction}
        />
      )}
    </div>
  );
}
