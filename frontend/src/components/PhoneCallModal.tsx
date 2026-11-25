import React, { useEffect, useState, useRef } from 'react';
import DailyIframe, { DailyCall } from '@daily-co/daily-js';
import { Mic, MicOff, PhoneOff, Volume2, Clock, CheckCircle2, AlertCircle } from 'lucide-react';
import { TranscriptMessage } from '../types';

interface PhoneCallModalProps {
  isOpen: boolean;
  onClose: () => void;
  roomUrl: string;
  token?: string;
  roomName: string;
  transcripts: TranscriptMessage[];
  lastAction?: { action: string; message: string } | null;
}

export const PhoneCallModal: React.FC<PhoneCallModalProps> = ({
  isOpen,
  onClose,
  roomUrl,
  token,
  roomName,
  transcripts,
  lastAction,
}) => {
  const [callState, setCallState] = useState<'connecting' | 'connected' | 'ended'>('connecting');
  const [isMuted, setIsMuted] = useState(false);
  const [duration, setDuration] = useState(0);
  const callObjectRef = useRef<DailyCall | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  // Timer
  useEffect(() => {
    let interval: any;
    if (callState === 'connected') {
      interval = setInterval(() => {
        setDuration((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [callState]);

  // Scroll transcripts to bottom
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts]);

  // Daily WebRTC connection
  useEffect(() => {
    if (!isOpen || !roomUrl) return;

    setCallState('connecting');
    setDuration(0);

    const callFrame = DailyIframe.createCallObject({
      audioSource: true,
      videoSource: false,
    });

    callObjectRef.current = callFrame;

    callFrame.on('joined-meeting', () => {
      setCallState('connected');
    });

    callFrame.on('left-meeting', () => {
      setCallState('ended');
    });

    callFrame.on('error', (e) => {
      console.error('Daily error:', e);
    });

    callFrame.join({
      url: roomUrl,
      token: token || undefined,
    });

    return () => {
      if (callObjectRef.current) {
        callObjectRef.current.leave();
        callObjectRef.current.destroy();
        callObjectRef.current = null;
      }
    };
  }, [isOpen, roomUrl, token]);

  const handleToggleMute = () => {
    if (callObjectRef.current) {
      const nextMute = !isMuted;
      callObjectRef.current.setLocalAudio(!nextMute);
      setIsMuted(nextMute);
    }
  };

  const handleEndCall = async () => {
    setCallState('ended');
    try {
      await fetch('/api/call/end', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ room_name: roomName }),
      });
    } catch (e) {
      console.error(e);
    }

    if (callObjectRef.current) {
      callObjectRef.current.leave();
    }
    setTimeout(() => {
      onClose();
    }, 1200);
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      {/* Phone Body Frame */}
      <div className="relative w-full max-w-sm h-[680px] bg-slate-900 rounded-[44px] p-3 shadow-2xl border-4 border-slate-700 flex flex-col overflow-hidden text-white">
        {/* Dynamic Island / Notch */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 w-32 h-4 bg-black rounded-full flex items-center justify-center gap-2 z-20">
          <div className="w-2.5 h-2.5 rounded-full bg-slate-800" />
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        </div>

        {/* Screen Header */}
        <div className="pt-7 pb-3 px-4 flex flex-col items-center border-b border-slate-800/80">
          <div className="w-14 h-14 rounded-full bg-teal-600/30 border border-teal-500/40 flex items-center justify-center mb-2 shadow-inner">
            <Volume2 className="w-7 h-7 text-teal-400" />
          </div>
          <h3 className="text-base font-semibold text-slate-100">Cura AI Receptionist</h3>
          <p className="text-xs text-teal-400 font-medium">CuraClinic Voice Desk</p>

          <div className="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
            {callState === 'connecting' && (
              <span className="flex items-center gap-1.5 text-amber-400">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
                Connecting audio...
              </span>
            )}
            {callState === 'connected' && (
              <span className="flex items-center gap-1.5 text-emerald-400">
                <Clock className="w-3.5 h-3.5" />
                {formatTime(duration)}
              </span>
            )}
            {callState === 'ended' && (
              <span className="text-slate-400">Call Ended</span>
            )}
          </div>

          {/* Voice Waveform Activity */}
          {callState === 'connected' && (
            <div className="flex items-center gap-1 mt-3 h-8">
              <span className="w-1 bg-teal-400 rounded-full animate-wave-1" />
              <span className="w-1 bg-teal-300 rounded-full animate-wave-2" />
              <span className="w-1 bg-teal-500 rounded-full animate-wave-3" />
              <span className="w-1 bg-teal-300 rounded-full animate-wave-4" />
              <span className="w-1 bg-teal-400 rounded-full animate-wave-5" />
            </div>
          )}
        </div>

        {/* Action notification toast (Booking / Cancel confirmation) */}
        {lastAction && (
          <div className="mx-3 mt-2 px-3 py-2 bg-teal-950/80 border border-teal-500/40 rounded-xl flex items-center gap-2 text-xs text-teal-200 animate-in slide-in-from-top">
            <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
            <p className="line-clamp-2">{lastAction.message}</p>
          </div>
        )}

        {/* Live Conversation Transcript */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2 text-xs">
          {transcripts.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 text-center px-4">
              <p>Say hello or ask for available appointments.</p>
              <p className="mt-1 text-[11px] text-slate-600">e.g. "Hi, what doctors are available tomorrow?"</p>
            </div>
          ) : (
            transcripts.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${
                  msg.speaker === 'user' ? 'items-end' : 'items-start'
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2 leading-relaxed ${
                    msg.speaker === 'user'
                      ? 'bg-teal-600 text-white rounded-br-none shadow'
                      : 'bg-slate-800 text-slate-200 border border-slate-700/60 rounded-bl-none shadow'
                  }`}
                >
                  <p>{msg.text}</p>
                </div>
                <span className="text-[10px] text-slate-500 mt-0.5 px-1">
                  {msg.speaker === 'user' ? 'You' : 'Cura Assistant'} • {msg.timestamp}
                </span>
              </div>
            ))
          )}
          <div ref={transcriptEndRef} />
        </div>

        {/* Call Action Controls */}
        <div className="p-4 bg-slate-900 border-t border-slate-800 flex items-center justify-around">
          {/* Mute Button */}
          <button
            onClick={handleToggleMute}
            className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
              isMuted
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                : 'bg-slate-800 text-slate-200 hover:bg-slate-700'
            }`}
            title={isMuted ? 'Unmute' : 'Mute'}
          >
            {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>

          {/* End Call Button */}
          <button
            onClick={handleEndCall}
            className="w-14 h-14 rounded-full bg-rose-600 hover:bg-rose-500 active:scale-95 text-white flex items-center justify-center shadow-lg shadow-rose-900/40 transition-all"
            title="End Call"
          >
            <PhoneOff className="w-6 h-6" />
          </button>
        </div>
      </div>
    </div>
  );
};
