import sqlite3
import re
from typing import Dict, Any, Optional
from database import get_connection

def normalize_phone(phone: str) -> str:
    """Strip spaces, dashes, parentheses to clean standard digits."""
    return re.sub(r"[^\d+]", "", phone)

def check_doctor_availability(doctor_name: Optional[str] = None, date: Optional[str] = None, specialty: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns available open slots for doctors matching the criteria.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT s.id as slot_id, d.name as doctor_name, d.specialty, s.date, s.time
        FROM slots s
        JOIN doctors d ON s.doctor_id = d.id
        WHERE s.is_booked = 0
    """
    params = []

    if doctor_name:
        query += " AND LOWER(d.name) LIKE ?"
        params.append(f"%{doctor_name.lower().strip()}%")
    if specialty:
        query += " AND LOWER(d.specialty) LIKE ?"
        params.append(f"%{specialty.lower().strip()}%")
    if date:
        query += " AND s.date = ?"
        params.append(date.strip())

    query += " ORDER BY s.date, s.time LIMIT 6"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    slots = [dict(r) for r in rows]
    if not slots:
        return {
            "success": False,
            "message": "No open slots found matching your request. Would you like to check another doctor, specialty, or date?",
            "slots": []
        }
    
    return {
        "success": True,
        "count": len(slots),
        "slots": slots,
        "message": f"Found {len(slots)} available slots."
    }

def book_appointment(patient_phone: str, doctor_name: str, slot_time: str, slot_date: Optional[str] = None, patient_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Books an appointment for the caller using their confirmed phone number.
    """
    clean_phone = normalize_phone(patient_phone)
    if not clean_phone or len(clean_phone) < 7:
        return {
            "success": False,
            "error": "Invalid phone number provided. Please ask the caller for a valid phone number."
        }

    conn = get_connection()
    cursor = conn.cursor()

    # Find the doctor
    cursor.execute("SELECT id, name, specialty FROM doctors WHERE LOWER(name) LIKE ?", (f"%{doctor_name.lower().strip()}%",))
    doctor = cursor.fetchone()
    if not doctor:
        conn.close()
        return {
            "success": False,
            "error": f"Doctor '{doctor_name}' was not found in our clinic directory."
        }

    # Find matching unbooked slot
    slot_query = "SELECT id, date, time FROM slots WHERE doctor_id = ? AND is_booked = 0 AND (LOWER(time) LIKE ? OR time = ?)"
    slot_params = [doctor["id"], f"%{slot_time.lower().strip()}%", slot_time.strip()]
    if slot_date:
        slot_query += " AND date = ?"
        slot_params.append(slot_date.strip())

    cursor.execute(slot_query, slot_params)
    slot = cursor.fetchone()

    if not slot:
        conn.close()
        return {
            "success": False,
            "error": f"The requested slot ({slot_time}) is not available with Dr. {doctor['name']}."
        }

    # Mark slot booked
    cursor.execute("UPDATE slots SET is_booked = 1 WHERE id = ?", (slot["id"],))

    # Insert appointment
    cursor.execute("""
        INSERT INTO appointments (patient_name, patient_phone, doctor_id, doctor_name, specialty, date, time, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'CONFIRMED')
    """, (patient_name or "Caller", clean_phone, doctor["id"], doctor["name"], doctor["specialty"], slot["date"], slot["time"]))
    
    appointment_id = cursor.lastrowid
    conn.commit()
    conn.close()

    doc_display = doctor["name"] if doctor["name"].startswith("Dr.") else f"Dr. {doctor['name']}"

    return {
        "success": True,
        "appointment_id": appointment_id,
        "doctor": doctor["name"],
        "specialty": doctor["specialty"],
        "date": slot["date"],
        "time": slot["time"],
        "phone": clean_phone,
        "message": f"Appointment successfully confirmed with {doc_display} on {slot['date']} at {slot['time']}."
    }

def cancel_appointment(patient_phone: str) -> Dict[str, Any]:
    """
    Cancels existing appointment for caller identified by their confirmed phone number.
    """
    clean_phone = normalize_phone(patient_phone)
    if not clean_phone:
        return {
            "success": False,
            "error": "Valid phone number is required to look up your appointment."
        }

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, doctor_id, doctor_name, date, time
        FROM appointments
        WHERE patient_phone LIKE ? AND status = 'CONFIRMED'
        ORDER BY id DESC LIMIT 1
    """, (f"%{clean_phone}%",))
    
    appointment = cursor.fetchone()
    if not appointment:
        conn.close()
        return {
            "success": False,
            "error": f"No active confirmed appointment found for phone number {clean_phone}."
        }

    # Update appointment status to CANCELLED
    cursor.execute("UPDATE appointments SET status = 'CANCELLED' WHERE id = ?", (appointment["id"],))
    
    # Free up the slot in slots table
    cursor.execute("""
        UPDATE slots SET is_booked = 0
        WHERE doctor_id = ? AND date = ? AND time = ?
    """, (appointment["doctor_id"], appointment["date"], appointment["time"]))

    conn.commit()
    conn.close()

    doc_display = appointment["doctor_name"] if appointment["doctor_name"].startswith("Dr.") else f"Dr. {appointment['doctor_name']}"

    return {
        "success": True,
        "appointment_id": appointment["id"],
        "doctor": appointment["doctor_name"],
        "date": appointment["date"],
        "time": appointment["time"],
        "message": f"Your appointment with {doc_display} on {appointment['date']} at {appointment['time']} has been successfully cancelled."
    }
