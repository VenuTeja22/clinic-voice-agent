import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

DATA_FILE = os.path.join(os.path.dirname(__file__), "clinic_data.json")

INITIAL_DATA = {
    "doctors": [
        {"id": 1, "name": "Dr. Sarah Jenkins", "specialty": "Cardiology", "on_leave": False},
        {"id": 2, "name": "Dr. Rajesh Sharma", "specialty": "General Medicine", "on_leave": False},
        {"id": 3, "name": "Dr. Emily Watson", "specialty": "Dermatology", "on_leave": False},
        {"id": 4, "name": "Dr. Michael Chang", "specialty": "Pediatrics", "on_leave": False},
        {"id": 5, "name": "Dr. Ananya Iyer", "specialty": "Orthopedics", "on_leave": False},
        {"id": 6, "name": "Dr. David Miller", "specialty": "Neurology", "on_leave": True}
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
    "appointments": []
}

def ensure_active_dates(data: Dict[str, Any]) -> bool:
    """Ensures that slots for today and tomorrow always exist in the database dynamically."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    slots = data.get("slots", [])
    doctors = data.get("doctors", [])
    times = ["09:00 AM", "10:30 AM", "02:00 PM", "04:30 PM"]

    existing_keys = set((s.get("doctor_id"), s.get("date"), s.get("time")) for s in slots)
    current_max_id = max((s.get("id", 0) for s in slots), default=0)

    modified = False
    new_slots = []
    for d in [today, tomorrow]:
        for doc in doctors:
            if doc.get("on_leave"):
                continue  # Skip generating consultation slots for doctor on leave
            for t in times:
                key = (doc["id"], d, t)
                if key not in existing_keys:
                    current_max_id += 1
                    new_slots.append({
                        "id": current_max_id,
                        "doctor_id": doc["id"],
                        "doctor_name": doc["name"],
                        "date": d,
                        "time": t,
                        "is_booked": False
                    })
                    existing_keys.add(key)
                    modified = True

    if modified:
        slots.extend(new_slots)
        data["slots"] = slots
        save_data(data)
    return modified

def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        save_data(INITIAL_DATA)
        data = INITIAL_DATA
    else:
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            save_data(INITIAL_DATA)
            data = INITIAL_DATA

    ensure_active_dates(data)
    return data

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
            "on_leave": doc.get("on_leave", False),
            "slots": doc_slots
        })
    return results

def get_all_appointments() -> List[Dict[str, Any]]:
    data = load_data()
    return list(reversed(data.get("appointments", [])))
