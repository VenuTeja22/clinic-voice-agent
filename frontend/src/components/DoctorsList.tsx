import React from 'react';
import { UserCheck, Calendar, Clock, Stethoscope } from 'lucide-react';
import { Doctor } from '../types';

interface DoctorsListProps {
  doctors: Doctor[];
  isLoading: boolean;
}

export const DoctorsList: React.FC<DoctorsListProps> = ({ doctors, isLoading }) => {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-teal-50 border border-teal-100 flex items-center justify-center text-teal-600">
            <Stethoscope className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">Physicians & Available Slots</h2>
            <p className="text-xs text-slate-500">Live schedule synced with clinic directory</p>
          </div>
        </div>
        <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-teal-50 text-teal-700 border border-teal-200">
          {doctors.length} Doctors on Duty
        </span>
      </div>

      {isLoading ? (
        <div className="py-12 text-center text-sm text-slate-400">Loading clinic schedule...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {doctors.map((doc) => {
            const availableSlots = doc.slots.filter((s) => !s.is_booked);
            return (
              <div
                key={doc.id}
                className="p-4 rounded-xl border border-slate-100 bg-slate-50/50 hover:bg-white hover:border-teal-200 transition-all duration-200 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">{doc.name}</h3>
                      <p className="text-xs font-medium text-teal-600">{doc.specialty}</p>
                    </div>
                    <span
                      className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                        availableSlots.length > 0
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-slate-100 text-slate-500'
                      }`}
                    >
                      {availableSlots.length} open
                    </span>
                  </div>

                  {/* Slot pills */}
                  <div className="mt-3">
                    <p className="text-[11px] font-medium text-slate-400 mb-1.5 flex items-center gap-1">
                      <Clock className="w-3 h-3" /> Upcoming Slots
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {doc.slots.map((slot) => (
                        <span
                          key={slot.id}
                          className={`text-[11px] px-2 py-0.5 rounded-md font-mono ${
                            slot.is_booked
                              ? 'bg-slate-200/70 text-slate-400 line-through'
                              : 'bg-white text-slate-700 border border-slate-200 font-medium'
                          }`}
                        >
                          {slot.time}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="mt-3 pt-2.5 border-t border-slate-200/60 flex items-center justify-between text-[11px] text-slate-500">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-slate-400" />
                    Nov 26 - Nov 27
                  </span>
                  <span className="text-teal-600 font-medium">Spoken voice booking ready</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
