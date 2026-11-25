import os
import json
from typing import List, Dict, Any, Optional

DATA_FILE = os.path.join(os.path.dirname(__file__), "clinic_data.json")

INITIAL_DATA = {
    "doctors": [
        {"id": 1, "name": "Dr. Sarah Jenkins", "specialty": "Cardiology"},
        {"id": 2, "name": "Dr. Rajesh Sharma", "specialty": "General Medicine"},
        {"id": 3, "name": "Dr. Emily Watson", "specialty": "Dermatology"},
        {"id": 4, "name": "Dr. Michael Chang", "specialty": "Pediatrics"}
    ],
    "slots": [
        {"id": 1, "doctor_id": 1, "doctor_name": "Dr. Sarah Jenkins", "date": "2026-11-26", "time": "09:00 AM", "is_booked": False},
        {"id": 2, "doctor_id": 1, "doctor_name": "Dr. Sarah Jenkins", "date": "2026-11-26", "time": "10:30 AM", "is_booked": False},
        {"id": 3, "doctor_id": 1, "doctor_name": "Dr. Sarah Jenkins", "date": "2026-11-26", "time": "02:00 PM", "is_booked": False},
        {"id": 4, "doctor_id": 1, "doctor_name": "Dr. Sarah Jenkins", "date": "2026-11-26", "time": "04:30 PM", "is_booked": False},
        {"id": 5, "doctor_id": 2, "doctor_name": "Dr. Rajesh Sharma", "date": "2026-11-26", "time": "09:00 AM", "is_booked": False},
        {"id": 6, "doctor_id": 2, "doctor_name": "Dr. Rajesh Sharma", "date": "2026-11-26", "time": "10:30 AM", "is_booked": False},
        {"id": 7, "doctor_id": 2, "doctor_name": "Dr. Rajesh Sharma", "date": "2026-11-26", "time": "02:00 PM", "is_booked": False},
        {"id": 8, "doctor_id": 2, "doctor_name": "Dr. Rajesh Sharma", "date": "2026-11-26", "time": "04:30 PM", "is_booked": False},
        {"id": 9, "doctor_id": 3, "doctor_name": "Dr. Emily Watson", "date": "2026-11-26", "time": "09:00 AM", "is_booked": False},
        {"id": 10, "doctor_id": 3, "doctor_name": "Dr. Emily Watson", "date": "2026-11-26", "time": "10:30 AM", "is_booked": False},
        {"id": 11, "doctor_id": 3, "doctor_name": "Dr. Emily Watson", "date": "2026-11-26", "time": "02:00 PM", "is_booked": False},
        {"id": 12, "doctor_id": 3, "doctor_name": "Dr. Emily Watson", "date": "2026-11-26", "time": "04:30 PM", "is_booked": False},
        {"id": 13, "doctor_id": 4, "doctor_name": "Dr. Michael Chang", "date": "2026-11-26", "time": "09:00 AM", "is_booked": False},
        {"id": 14, "doctor_id": 4, "doctor_name": "Dr. Michael Chang", "date": "2026-11-26", "time": "10:30 AM", "is_booked": False},
        {"id": 15, "doctor_id": 4, "doctor_name": "Dr. Michael Chang", "date": "2026-11-26", "time": "02:00 PM", "is_booked": False},
        {"id": 16, "doctor_id": 4, "doctor_name": "Dr. Michael Chang", "date": "2026-11-26", "time": "04:30 PM", "is_booked": False}
    ],
    "appointments": [
        {
            "id": 1,
            "patient_name": "Alex Rivera",
            "patient_phone": "9876543210",
            "doctor_id": 1,
            "doctor_name": "Dr. Sarah Jenkins",
            "specialty": "Cardiology",
            "date": "2026-11-26",
            "time": "09:00 AM",
            "status": "CONFIRMED"
        }
    ]
}

def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        save_data(INITIAL_DATA)
        return INITIAL_DATA
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        save_data(INITIAL_DATA)
        return INITIAL_DATA

def save_data(data: Dict[str, Any]):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def init_db():
    load_data()

def get_all_doctors_with_slots() -> List[Dict[str, Any]]:
    data = load_data()
    doctors = data.get("doctors", [])
    slots = data.get("slots", [])

    results = []
    for doc in doctors:
        doc_slots = [
            {"id": s["id"], "date": s["date"], "time": s["time"], "is_booked": s["is_booked"]}
            for s in slots if s["doctor_id"] == doc["id"]
        ]
        results.append({
            "id": doc["id"],
            "name": doc["name"],
            "specialty": doc["specialty"],
            "slots": doc_slots
        })
    return results

def get_all_appointments() -> List[Dict[str, Any]]:
    data = load_data()
    return list(reversed(data.get("appointments", [])))
