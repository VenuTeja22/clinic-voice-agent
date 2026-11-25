import re
from typing import Dict, Any, Optional
from database import load_data, save_data

def normalize_phone(phone: str) -> str:
    """Strip spaces, dashes, parentheses to clean standard digits."""
    return re.sub(r"[^\d+]", "", phone)

def check_doctor_availability(doctor_name: Optional[str] = None, date: Optional[str] = None, specialty: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns available open slots for doctors matching the criteria from the JSON store.
    """
    data = load_data()
    slots = data.get("slots", [])
    doctors = {d["id"]: d for d in data.get("doctors", [])}

    matching = []
    for s in slots:
        if s.get("is_booked"):
            continue
        doc = doctors.get(s["doctor_id"], {})
        d_name = doc.get("name", "")
        d_spec = doc.get("specialty", "")

        if doctor_name and doctor_name.lower().strip() not in d_name.lower():
            continue
        if specialty and specialty.lower().strip() not in d_spec.lower():
            continue
        if date and date.strip() != s.get("date", "").strip():
            continue

        matching.append({
            "slot_id": s["id"],
            "doctor_name": d_name,
            "specialty": d_spec,
            "date": s["date"],
            "time": s["time"]
        })

    if not matching:
        return {
            "success": False,
            "message": "No open slots found matching your request. Would you like to check another doctor, specialty, or date?",
            "slots": []
        }

    return {
        "success": True,
        "count": len(matching),
        "slots": matching[:6],
        "message": f"Found {len(matching)} available slots."
    }

def book_appointment(patient_phone: str, doctor_name: str, slot_time: str, slot_date: Optional[str] = None, patient_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Books an appointment in JSON store using the confirmed phone number.
    """
    clean_phone = normalize_phone(patient_phone)
    if not clean_phone or len(clean_phone) < 7:
        return {
            "success": False,
            "error": "Invalid phone number provided. Please ask the caller for a valid phone number."
        }

    data = load_data()
    doctors = data.get("doctors", [])
    slots = data.get("slots", [])
    appointments = data.get("appointments", [])

    # Find doctor
    target_doc = None
    for d in doctors:
        if doctor_name.lower().strip() in d["name"].lower():
            target_doc = d
            break

    if not target_doc:
        return {
            "success": False,
            "error": f"Doctor '{doctor_name}' was not found in our clinic directory."
        }

    # Find unbooked slot
    target_slot = None
    for s in slots:
        if s["doctor_id"] == target_doc["id"] and not s.get("is_booked"):
            time_match = slot_time.lower().strip() in s["time"].lower() or slot_time.strip() == s["time"]
            date_match = (slot_date.strip() == s["date"]) if slot_date else True
            if time_match and date_match:
                target_slot = s
                break

    if not target_slot:
        return {
            "success": False,
            "error": f"The requested slot ({slot_time}) is not available with {target_doc['name']}."
        }

    # Mark slot booked
    target_slot["is_booked"] = True

    new_id = len(appointments) + 1
    new_apt = {
        "id": new_id,
        "patient_name": patient_name or "Caller",
        "patient_phone": clean_phone,
        "doctor_id": target_doc["id"],
        "doctor_name": target_doc["name"],
        "specialty": target_doc["specialty"],
        "date": target_slot["date"],
        "time": target_slot["time"],
        "status": "CONFIRMED"
    }
    appointments.append(new_apt)
    save_data(data)

    doc_display = target_doc["name"] if target_doc["name"].startswith("Dr.") else f"Dr. {target_doc['name']}"

    return {
        "success": True,
        "appointment_id": new_id,
        "doctor": target_doc["name"],
        "specialty": target_doc["specialty"],
        "date": target_slot["date"],
        "time": target_slot["time"],
        "phone": clean_phone,
        "message": f"Appointment successfully confirmed with {doc_display} on {target_slot['date']} at {target_slot['time']}."
    }

def cancel_appointment(patient_phone: str) -> Dict[str, Any]:
    """
    Cancels existing appointment in JSON store for phone number.
    """
    clean_phone = normalize_phone(patient_phone)
    if not clean_phone:
        return {
            "success": False,
            "error": "Valid phone number is required to look up your appointment."
        }

    data = load_data()
    appointments = data.get("appointments", [])
    slots = data.get("slots", [])

    # Find last confirmed appointment for this phone
    target_apt = None
    for apt in reversed(appointments):
        if clean_phone in apt.get("patient_phone", "") and apt.get("status") == "CONFIRMED":
            target_apt = apt
            break

    if not target_apt:
        return {
            "success": False,
            "error": f"No active confirmed appointment found for phone number {clean_phone}."
        }

    target_apt["status"] = "CANCELLED"

    # Free up slot
    for s in slots:
        if s["doctor_id"] == target_apt["doctor_id"] and s["date"] == target_apt["date"] and s["time"] == target_apt["time"]:
            s["is_booked"] = False
            break

    save_data(data)

    doc_display = target_apt["doctor_name"] if target_apt["doctor_name"].startswith("Dr.") else f"Dr. {target_apt['doctor_name']}"

    return {
        "success": True,
        "appointment_id": target_apt["id"],
        "doctor": target_apt["doctor_name"],
        "date": target_apt["date"],
        "time": target_apt["time"],
        "message": f"Your appointment with {doc_display} on {target_apt['date']} at {target_apt['time']} has been successfully cancelled."
    }
