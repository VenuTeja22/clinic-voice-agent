import React from 'react';
import { CalendarCheck2, Phone, User, Clock, CheckCircle, XCircle } from 'lucide-react';
import { Appointment } from '../types';

interface AppointmentsListProps {
  appointments: Appointment[];
  isLoading: boolean;
}

export const AppointmentsList: React.FC<AppointmentsListProps> = ({ appointments, isLoading }) => {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-teal-50 border border-teal-100 flex items-center justify-center text-teal-600">
            <CalendarCheck2 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">Live Appointments Registry</h2>
            <p className="text-xs text-slate-500">Auto-updates in real time when booked or cancelled by voice</p>
          </div>
        </div>
        <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
          {appointments.length} Total Records
        </span>
      </div>

      {isLoading ? (
        <div className="py-10 text-center text-sm text-slate-400">Loading appointments...</div>
      ) : appointments.length === 0 ? (
        <div className="py-10 text-center text-sm text-slate-400">
          No appointments recorded yet. Call the assistant to book one!
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-100 text-slate-400 font-medium uppercase tracking-wider">
                <th className="pb-3 pl-2">Patient Phone</th>
                <th className="pb-3">Doctor</th>
                <th className="pb-3">Specialty</th>
                <th className="pb-3">Slot Date & Time</th>
                <th className="pb-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {appointments.map((apt) => (
                <tr key={apt.id} className="hover:bg-slate-50/60 transition-colors">
                  <td className="py-3 pl-2 font-mono font-medium text-slate-800 flex items-center gap-1.5">
                    <Phone className="w-3.5 h-3.5 text-teal-600" />
                    {apt.patient_phone}
                  </td>
                  <td className="py-3 font-semibold text-slate-900">{apt.doctor_name}</td>
                  <td className="py-3 text-slate-600">{apt.specialty}</td>
                  <td className="py-3 font-medium text-slate-700">
                    {apt.date} • {apt.time}
                  </td>
                  <td className="py-3">
                    {apt.status === 'CONFIRMED' ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <CheckCircle className="w-3 h-3 text-emerald-600" /> Confirmed
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
                        <XCircle className="w-3 h-3 text-rose-600" /> Cancelled
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
