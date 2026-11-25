export interface Slot {
  id: number;
  date: string;
  time: string;
  is_booked: boolean;
}

export interface Doctor {
  id: number;
  name: string;
  specialty: string;
  slots: Slot[];
}

export interface Appointment {
  id: number;
  patient_name: string;
  patient_phone: string;
  doctor_name: string;
  specialty: string;
  date: string;
  time: string;
  status: 'CONFIRMED' | 'CANCELLED';
  created_at: string;
}

export interface TranscriptMessage {
  id: string;
  speaker: 'user' | 'assistant';
  text: string;
  timestamp: string;
}
