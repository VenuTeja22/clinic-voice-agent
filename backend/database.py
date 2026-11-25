import sqlite3
import os
from typing import List, Dict, Optional, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "clinic.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Doctors Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialty TEXT NOT NULL
        )
    """)

    # Available Slots Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            is_booked INTEGER DEFAULT 0,
            FOREIGN KEY (doctor_id) REFERENCES doctors (id)
        )
    """)

    # Booked Appointments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            patient_phone TEXT NOT NULL,
            doctor_id INTEGER NOT NULL,
            doctor_name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT DEFAULT 'CONFIRMED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doctor_id) REFERENCES doctors (id)
        )
    """)

    # Populate initial mock data if empty
    cursor.execute("SELECT COUNT(*) FROM doctors")
    if cursor.fetchone()[0] == 0:
        doctors_data = [
            ("Dr. Sarah Jenkins", "Cardiology"),
            ("Dr. Rajesh Sharma", "General Medicine"),
            ("Dr. Emily Watson", "Dermatology"),
            ("Dr. Michael Chang", "Pediatrics")
        ]
        cursor.executemany("INSERT INTO doctors (name, specialty) VALUES (?, ?)", doctors_data)
        
        # Populate slots for each doctor across today and tomorrow
        cursor.execute("SELECT id, name FROM doctors")
        docs = cursor.fetchall()

        times = ["09:00 AM", "10:30 AM", "02:00 PM", "04:30 PM"]
        dates = ["2026-11-26", "2026-11-27"]

        slots_data = []
        for doc in docs:
            for d in dates:
                for t in times:
                    slots_data.append((doc["id"], d, t, 0))

        cursor.executemany("INSERT INTO slots (doctor_id, date, time, is_booked) VALUES (?, ?, ?, ?)", slots_data)

        # Seed 1 initial appointment to demonstrate cancellation/listing
        sample_doc = docs[0]
        cursor.execute("""
            INSERT INTO appointments (patient_name, patient_phone, doctor_id, doctor_name, specialty, date, time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Alex Rivera", "9876543210", sample_doc["id"], sample_doc["name"], "Cardiology", "2026-11-26", "09:00 AM", "CONFIRMED"))
        
        cursor.execute("UPDATE slots SET is_booked = 1 WHERE doctor_id = ? AND date = ? AND time = ?",
                       (sample_doc["id"], "2026-11-26", "09:00 AM"))

    conn.commit()
    conn.close()

def get_all_doctors_with_slots() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.name, d.specialty, s.id as slot_id, s.date, s.time, s.is_booked
        FROM doctors d
        LEFT JOIN slots s ON d.id = s.doctor_id
        ORDER BY d.name, s.date, s.time
    """)
    rows = cursor.fetchall()
    conn.close()

    doctors_map = {}
    for row in rows:
        d_id = row["id"]
        if d_id not in doctors_map:
            doctors_map[d_id] = {
                "id": row["id"],
                "name": row["name"],
                "specialty": row["specialty"],
                "slots": []
            }
        if row["slot_id"] is not None:
            doctors_map[d_id]["slots"].append({
                "id": row["slot_id"],
                "date": row["date"],
                "time": row["time"],
                "is_booked": bool(row["is_booked"])
            })
    return list(doctors_map.values())

def get_all_appointments() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, patient_name, patient_phone, doctor_name, specialty, date, time, status, created_at
        FROM appointments
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Initialize tables on import
init_db()
