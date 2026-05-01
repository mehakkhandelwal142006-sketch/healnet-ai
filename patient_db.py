"""
patient_db.py — HealNet AI · Patient Database Layer
====================================================
Backend:  Supabase (PostgreSQL)
Fallback: SQLite (when SUPABASE_URL / SUPABASE_KEY are not set)

IoT-ready: the `vitals_readings` table is pre-created here so any
IoT device can INSERT rows via the same Supabase REST API without
touching app code.

Environment variables (set in .env or Streamlit secrets):
    SUPABASE_URL   – your project URL  (https://xxxx.supabase.co)
    SUPABASE_KEY   – service-role or anon key
    DB_FALLBACK    – set to "1" to force SQLite even if Supabase is configured
"""

from __future__ import annotations

import os
import sqlite3
import datetime
import logging
import uuid
from contextlib import contextmanager
from typing import Optional

import pandas as pd

logger = logging.getLogger("healnet.patient_db")

# ──────────────────────────────────────────────────────────────────────────────
# 1.  Driver selection
# ──────────────────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
FORCE_SQLITE = os.getenv("DB_FALLBACK", "0") == "1"

_USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY and not FORCE_SQLITE)

if _USE_SUPABASE:
    try:
        from supabase import create_client, Client as SupabaseClient
        _sb: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Connected to Supabase at %s", SUPABASE_URL)
    except Exception as exc:
        logger.warning("Supabase init failed (%s) — falling back to SQLite", exc)
        _USE_SUPABASE = False

# ──────────────────────────────────────────────────────────────────────────────
# 2.  SQLite helpers (fallback)
# ──────────────────────────────────────────────────────────────────────────────

_SQLITE_DB = os.path.join(os.path.dirname(__file__), "healnet.db")

@contextmanager
def _sqlite_conn():
    conn = sqlite3.connect(_SQLITE_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# 3.  Schema – patients table DDL (SQLite)
# ──────────────────────────────────────────────────────────────────────────────

_PATIENTS_DDL = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id          TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    age                 INTEGER,
    gender              TEXT,
    contact             TEXT,
    blood_group         TEXT,
    email               TEXT,
    address             TEXT,
    registered_by       TEXT,
    allergies           TEXT,
    chronic_conditions  TEXT,
    current_medications TEXT,
    past_surgeries      TEXT,
    family_history      TEXT,
    medical_notes       TEXT,
    emergency_name      TEXT,
    emergency_relation  TEXT,
    emergency_contact   TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);
"""

# IoT-ready vitals table (SQLite version)
_VITALS_DDL = """
CREATE TABLE IF NOT EXISTS vitals_readings (
    id              TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    device_id       TEXT,
    source          TEXT DEFAULT 'manual',  -- 'manual' | 'iot' | 'camera'
    heart_rate      REAL,
    spo2            REAL,
    systolic_bp     REAL,
    diastolic_bp    REAL,
    temperature     REAL,
    blood_sugar     REAL,
    respiratory_rate REAL,
    bmi             REAL,
    recorded_at     TEXT DEFAULT (datetime('now'))
);
"""

# Alert log table (SQLite version)
_ALERTS_DDL = """
CREATE TABLE IF NOT EXISTS alert_log (
    id              TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL,
    patient_name    TEXT,
    vital           TEXT,
    value           TEXT,
    level           TEXT,
    category        TEXT,
    message         TEXT,
    email_sent      INTEGER DEFAULT 0,
    email_error     TEXT,
    acknowledged    INTEGER DEFAULT 0,
    ack_by          TEXT,
    ack_time        TEXT,
    device_id       TEXT,
    recorded_at     TEXT DEFAULT (datetime('now'))
);
"""

# ──────────────────────────────────────────────────────────────────────────────
# 4.  create_table  (called once at app startup)
# ──────────────────────────────────────────────────────────────────────────────

def create_table() -> None:
    """
    Ensure all tables exist.

    • Supabase: tables should be created via the Supabase dashboard /
      migrations.  This function will log a warning if the `patients`
      table is missing.
    • SQLite:   tables are auto-created via DDL statements above.
    """
    if _USE_SUPABASE:
        _ensure_supabase_tables()
    else:
        with _sqlite_conn() as conn:
            conn.execute(_PATIENTS_DDL)
            conn.execute(_VITALS_DDL)
            conn.execute(_ALERTS_DDL)
        logger.info("SQLite tables ready at %s", _SQLITE_DB)


def _ensure_supabase_tables():
    """
    Verify the patients table exists in Supabase.
    If not, print the SQL you should run in the Supabase SQL editor.
    """
    try:
        _sb.table("patients").select("patient_id").limit(1).execute()
    except Exception:
        logger.error(
            "Supabase 'patients' table missing. Run the following SQL in "
            "your Supabase SQL editor:\n\n%s\n%s\n%s",
            _SUPABASE_PATIENTS_SQL,
            _SUPABASE_VITALS_SQL,
            _SUPABASE_ALERTS_SQL,
        )


# SQL you should run ONCE in the Supabase SQL editor
_SUPABASE_PATIENTS_SQL = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id          TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    age                 INTEGER,
    gender              TEXT,
    contact             TEXT,
    blood_group         TEXT,
    email               TEXT,
    address             TEXT,
    registered_by       TEXT,
    allergies           TEXT,
    chronic_conditions  TEXT,
    current_medications TEXT,
    past_surgeries      TEXT,
    family_history      TEXT,
    medical_notes       TEXT,
    emergency_name      TEXT,
    emergency_relation  TEXT,
    emergency_contact   TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

-- Row-level security (enable after setup)
-- ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
"""

_SUPABASE_VITALS_SQL = """
CREATE TABLE IF NOT EXISTS vitals_readings (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    device_id        TEXT,
    source           TEXT DEFAULT 'manual',
    heart_rate       NUMERIC,
    spo2             NUMERIC,
    systolic_bp      NUMERIC,
    diastolic_bp     NUMERIC,
    temperature      NUMERIC,
    blood_sugar      NUMERIC,
    respiratory_rate NUMERIC,
    bmi              NUMERIC,
    recorded_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS vitals_patient_idx ON vitals_readings(patient_id);
CREATE INDEX IF NOT EXISTS vitals_recorded_idx ON vitals_readings(recorded_at DESC);
"""

_SUPABASE_ALERTS_SQL = """
CREATE TABLE IF NOT EXISTS alert_log (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id     TEXT NOT NULL,
    patient_name   TEXT,
    vital          TEXT,
    value          TEXT,
    level          TEXT,
    category       TEXT,
    message        TEXT,
    email_sent     BOOLEAN DEFAULT false,
    email_error    TEXT,
    acknowledged   BOOLEAN DEFAULT false,
    ack_by         TEXT,
    ack_time       TIMESTAMPTZ,
    device_id      TEXT,
    recorded_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS alert_patient_idx ON alert_log(patient_id);
CREATE INDEX IF NOT EXISTS alert_recorded_idx ON alert_log(recorded_at DESC);
"""


# ──────────────────────────────────────────────────────────────────────────────
# 5.  Patient CRUD
# ──────────────────────────────────────────────────────────────────────────────

def add_patient(
    patient_id: str, name: str, age: int, gender: str,
    contact: str = "", blood: str = "", registered_by: str = "",
    email: str = "", address: str = "",
    allergies: str = "", chronic_conditions: str = "",
    current_medications: str = "", past_surgeries: str = "",
    family_history: str = "", medical_notes: str = "",
    emergency_name: str = "", emergency_relation: str = "",
    emergency_contact: str = "",
) -> tuple[bool, str]:
    """Insert a new patient.  Returns (success, error_message)."""
    now = datetime.datetime.utcnow().isoformat()
    row = {
        "patient_id": patient_id.strip(),
        "name": name.strip(),
        "age": int(age),
        "gender": gender,
        "contact": contact,
        "blood_group": blood,
        "email": email,
        "address": address,
        "registered_by": registered_by,
        "allergies": allergies,
        "chronic_conditions": chronic_conditions,
        "current_medications": current_medications,
        "past_surgeries": past_surgeries,
        "family_history": family_history,
        "medical_notes": medical_notes,
        "emergency_name": emergency_name,
        "emergency_relation": emergency_relation,
        "emergency_contact": emergency_contact,
        "created_at": now,
        "updated_at": now,
    }

    if _USE_SUPABASE:
        try:
            _sb.table("patients").insert(row).execute()
            return True, ""
        except Exception as exc:
            msg = str(exc)
            if "duplicate" in msg.lower() or "unique" in msg.lower():
                return False, f"Patient ID '{patient_id}' already exists."
            return False, msg
    else:
        try:
            with _sqlite_conn() as conn:
                cols = ", ".join(row.keys())
                placeholders = ", ".join(["?"] * len(row))
                conn.execute(
                    f"INSERT INTO patients ({cols}) VALUES ({placeholders})",
                    list(row.values()),
                )
            return True, ""
        except sqlite3.IntegrityError:
            return False, f"Patient ID '{patient_id}' already exists."
        except Exception as exc:
            return False, str(exc)


def get_patient(patient_id: str) -> Optional[dict]:
    """Fetch a single patient dict, or None if not found."""
    if _USE_SUPABASE:
        try:
            res = (
                _sb.table("patients")
                .select("*")
                .eq("patient_id", patient_id)
                .limit(1)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as exc:
            logger.error("get_patient error: %s", exc)
            return None
    else:
        with _sqlite_conn() as conn:
            row = conn.execute(
                "SELECT * FROM patients WHERE patient_id = ?", (patient_id,)
            ).fetchone()
        return dict(row) if row else None


def get_all_patients() -> list[dict]:
    """Return all patients ordered by created_at DESC."""
    if _USE_SUPABASE:
        try:
            res = (
                _sb.table("patients")
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
            return res.data or []
        except Exception as exc:
            logger.error("get_all_patients error: %s", exc)
            return []
    else:
        with _sqlite_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM patients ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def update_patient(
    patient_id: str,
    name: str = None, age: int = None, gender: str = None,
    contact: str = None, blood: str = None, email: str = None,
    address: str = None, allergies: str = None,
    chronic_conditions: str = None, current_medications: str = None,
    past_surgeries: str = None, family_history: str = None,
    medical_notes: str = None, emergency_name: str = None,
    emergency_relation: str = None, emergency_contact: str = None,
) -> tuple[bool, str]:
    """Update mutable patient fields.  Returns (success, error_message)."""
    updates: dict = {"updated_at": datetime.datetime.utcnow().isoformat()}
    mapping = {
        "name": name, "age": age, "gender": gender,
        "contact": contact, "blood_group": blood, "email": email,
        "address": address, "allergies": allergies,
        "chronic_conditions": chronic_conditions,
        "current_medications": current_medications,
        "past_surgeries": past_surgeries,
        "family_history": family_history,
        "medical_notes": medical_notes,
        "emergency_name": emergency_name,
        "emergency_relation": emergency_relation,
        "emergency_contact": emergency_contact,
    }
    for col, val in mapping.items():
        if val is not None:
            updates[col] = val

    if _USE_SUPABASE:
        try:
            _sb.table("patients").update(updates).eq("patient_id", patient_id).execute()
            return True, ""
        except Exception as exc:
            return False, str(exc)
    else:
        try:
            with _sqlite_conn() as conn:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE patients SET {set_clause} WHERE patient_id = ?",
                    [*updates.values(), patient_id],
                )
            return True, ""
        except Exception as exc:
            return False, str(exc)


def delete_patient(patient_id: str) -> bool:
    """Delete patient and cascade-delete related vitals / alerts."""
    if _USE_SUPABASE:
        try:
            _sb.table("patients").delete().eq("patient_id", patient_id).execute()
            return True
        except Exception as exc:
            logger.error("delete_patient error: %s", exc)
            return False
    else:
        with _sqlite_conn() as conn:
            conn.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
        return True


def search_patients(
    query: str = "",
    gender: str = "All",
    blood: str = "All",
    condition: str = "",
) -> pd.DataFrame:
    """
    Full-text search + filter.  Returns a DataFrame with display columns.
    Supports Supabase ilike pattern matching and SQLite LIKE.
    """
    all_cols = [
        "patient_id", "name", "age", "gender", "blood_group",
        "contact", "chronic_conditions", "created_at",
    ]

    if _USE_SUPABASE:
        q = _sb.table("patients").select(
            "patient_id,name,age,gender,blood_group,contact,chronic_conditions,created_at"
        )
        if query.strip():
            pat = f"%{query.strip()}%"
            q = q.or_(
                f"name.ilike.{pat},"
                f"patient_id.ilike.{pat},"
                f"contact.ilike.{pat},"
                f"chronic_conditions.ilike.{pat}"
            )
        if gender != "All":
            q = q.eq("gender", gender)
        if blood != "All":
            q = q.eq("blood_group", blood)
        if condition.strip():
            q = q.ilike("chronic_conditions", f"%{condition.strip()}%")
        try:
            rows = q.order("created_at", desc=True).execute().data or []
        except Exception as exc:
            logger.error("search_patients error: %s", exc)
            rows = []
    else:
        sql = "SELECT patient_id,name,age,gender,blood_group,contact,chronic_conditions,created_at FROM patients WHERE 1=1"
        params: list = []
        if query.strip():
            pat = f"%{query.strip()}%"
            sql += " AND (name LIKE ? OR patient_id LIKE ? OR contact LIKE ? OR chronic_conditions LIKE ?)"
            params.extend([pat, pat, pat, pat])
        if gender != "All":
            sql += " AND gender = ?"
            params.append(gender)
        if blood != "All":
            sql += " AND blood_group = ?"
            params.append(blood)
        if condition.strip():
            sql += " AND chronic_conditions LIKE ?"
            params.append(f"%{condition.strip()}%")
        sql += " ORDER BY created_at DESC"
        with _sqlite_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=all_cols)
    if not df.empty:
        df = df.rename(columns={
            "patient_id": "Patient ID",
            "name": "Name",
            "age": "Age",
            "gender": "Gender",
            "blood_group": "Blood Group",
            "contact": "Contact",
            "chronic_conditions": "Conditions",
            "created_at": "Registered On",
        })
    return df


def get_patient_stats() -> dict:
    """Aggregate stats shown on the dashboard."""
    today = datetime.date.today().isoformat()

    if _USE_SUPABASE:
        try:
            all_res = _sb.table("patients").select("gender,created_at").execute()
            rows = all_res.data or []
        except Exception as exc:
            logger.error("get_patient_stats error: %s", exc)
            rows = []
        total  = len(rows)
        male   = sum(1 for r in rows if str(r.get("gender", "")).lower() == "male")
        female = sum(1 for r in rows if str(r.get("gender", "")).lower() == "female")
        today_count = sum(
            1 for r in rows
            if str(r.get("created_at", "")).startswith(today)
        )
    else:
        with _sqlite_conn() as conn:
            total       = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
            male        = conn.execute("SELECT COUNT(*) FROM patients WHERE LOWER(gender)='male'").fetchone()[0]
            female      = conn.execute("SELECT COUNT(*) FROM patients WHERE LOWER(gender)='female'").fetchone()[0]
            today_count = conn.execute(
                "SELECT COUNT(*) FROM patients WHERE DATE(created_at) = DATE('now')"
            ).fetchone()[0]

    return {"total": total, "male": male, "female": female, "today": today_count}


# ──────────────────────────────────────────────────────────────────────────────
# 6.  Vitals persistence  (IoT-ready)
# ──────────────────────────────────────────────────────────────────────────────

def save_vitals_reading(
    patient_id: str,
    heart_rate: float = None,
    spo2: float = None,
    systolic_bp: float = None,
    diastolic_bp: float = None,
    temperature: float = None,
    blood_sugar: float = None,
    respiratory_rate: float = None,
    bmi: float = None,
    device_id: str = None,
    source: str = "manual",  # 'manual' | 'iot' | 'camera'
) -> tuple[bool, str]:
    """
    Persist a vitals snapshot.

    IoT devices can call the same Supabase REST endpoint:
        POST https://<project>.supabase.co/rest/v1/vitals_readings
        Headers: apikey: <anon_key>, Authorization: Bearer <anon_key>
        Body: { "patient_id": "P001", "heart_rate": 72, "source": "iot", ... }
    """
    row = {
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "device_id": device_id,
        "source": source,
        "heart_rate": heart_rate,
        "spo2": spo2,
        "systolic_bp": systolic_bp,
        "diastolic_bp": diastolic_bp,
        "temperature": temperature,
        "blood_sugar": blood_sugar,
        "respiratory_rate": respiratory_rate,
        "bmi": bmi,
        "recorded_at": datetime.datetime.utcnow().isoformat(),
    }
    # Remove None values for Supabase (it stores NULL automatically)
    row_clean = {k: v for k, v in row.items() if v is not None}
    # Keep id, patient_id, source, recorded_at always
    for must in ("id", "patient_id", "source", "recorded_at"):
        row_clean[must] = row[must]

    if _USE_SUPABASE:
        try:
            _sb.table("vitals_readings").insert(row_clean).execute()
            return True, ""
        except Exception as exc:
            return False, str(exc)
    else:
        try:
            with _sqlite_conn() as conn:
                cols = ", ".join(row.keys())
                ph   = ", ".join(["?"] * len(row))
                conn.execute(
                    f"INSERT INTO vitals_readings ({cols}) VALUES ({ph})",
                    list(row.values()),
                )
            return True, ""
        except Exception as exc:
            return False, str(exc)


def get_vitals_history(
    patient_id: str, limit: int = 100, source: str = None
) -> list[dict]:
    """
    Fetch recent vitals for a patient.
    Optionally filter by source ('manual', 'iot', 'camera').
    """
    if _USE_SUPABASE:
        try:
            q = (
                _sb.table("vitals_readings")
                .select("*")
                .eq("patient_id", patient_id)
            )
            if source:
                q = q.eq("source", source)
            res = q.order("recorded_at", desc=True).limit(limit).execute()
            return res.data or []
        except Exception as exc:
            logger.error("get_vitals_history error: %s", exc)
            return []
    else:
        with _sqlite_conn() as conn:
            if source:
                rows = conn.execute(
                    "SELECT * FROM vitals_readings WHERE patient_id=? AND source=? ORDER BY recorded_at DESC LIMIT ?",
                    (patient_id, source, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM vitals_readings WHERE patient_id=? ORDER BY recorded_at DESC LIMIT ?",
                    (patient_id, limit),
                ).fetchall()
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# 7.  Alert log persistence
# ──────────────────────────────────────────────────────────────────────────────

def save_alert(
    patient_id: str, patient_name: str,
    vital: str, value: str, level: str, category: str, message: str,
    email_sent: bool = False, email_error: str = "",
    device_id: str = None,
) -> bool:
    """Persist one alert entry to the database."""
    row = {
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "patient_name": patient_name,
        "vital": vital,
        "value": str(value),
        "level": level,
        "category": category,
        "message": message,
        "email_sent": email_sent,
        "email_error": email_error or "",
        "acknowledged": False,
        "device_id": device_id,
        "recorded_at": datetime.datetime.utcnow().isoformat(),
    }
    if _USE_SUPABASE:
        try:
            _sb.table("alert_log").insert(row).execute()
            return True
        except Exception as exc:
            logger.error("save_alert error: %s", exc)
            return False
    else:
        try:
            with _sqlite_conn() as conn:
                cols = ", ".join(row.keys())
                ph   = ", ".join(["?"] * len(row))
                conn.execute(
                    f"INSERT INTO alert_log ({cols}) VALUES ({ph})",
                    [int(v) if isinstance(v, bool) else v for v in row.values()],
                )
            return True
        except Exception as exc:
            logger.error("save_alert SQLite error: %s", exc)
            return False


def get_alert_log(patient_id: str = None, limit: int = 300) -> list[dict]:
    """Fetch alert log (all patients or one patient)."""
    if _USE_SUPABASE:
        try:
            q = _sb.table("alert_log").select("*")
            if patient_id:
                q = q.eq("patient_id", patient_id)
            res = q.order("recorded_at", desc=True).limit(limit).execute()
            return res.data or []
        except Exception as exc:
            logger.error("get_alert_log error: %s", exc)
            return []
    else:
        with _sqlite_conn() as conn:
            if patient_id:
                rows = conn.execute(
                    "SELECT * FROM alert_log WHERE patient_id=? ORDER BY recorded_at DESC LIMIT ?",
                    (patient_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM alert_log ORDER BY recorded_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]


def acknowledge_alert(alert_id: str, ack_by: str) -> bool:
    """Mark an alert as acknowledged."""
    now = datetime.datetime.utcnow().isoformat()
    if _USE_SUPABASE:
        try:
            _sb.table("alert_log").update(
                {"acknowledged": True, "ack_by": ack_by, "ack_time": now}
            ).eq("id", alert_id).execute()
            return True
        except Exception as exc:
            logger.error("acknowledge_alert error: %s", exc)
            return False
    else:
        with _sqlite_conn() as conn:
            conn.execute(
                "UPDATE alert_log SET acknowledged=1, ack_by=?, ack_time=? WHERE id=?",
                (ack_by, now, alert_id),
            )
        return True


# ──────────────────────────────────────────────────────────────────────────────
# 8.  IoT Device Registry (optional — future use)
# ──────────────────────────────────────────────────────────────────────────────

def register_device(device_id: str, patient_id: str, device_type: str = "generic") -> bool:
    """
    Register an IoT device linked to a patient.

    This table doesn't exist by default — create it with:

        CREATE TABLE IF NOT EXISTS iot_devices (
            device_id    TEXT PRIMARY KEY,
            patient_id   TEXT REFERENCES patients(patient_id),
            device_type  TEXT,
            last_seen    TIMESTAMPTZ,
            registered_at TIMESTAMPTZ DEFAULT now()
        );
    """
    if _USE_SUPABASE:
        try:
            _sb.table("iot_devices").upsert({
                "device_id": device_id,
                "patient_id": patient_id,
                "device_type": device_type,
                "last_seen": datetime.datetime.utcnow().isoformat(),
            }).execute()
            return True
        except Exception:
            return False
    return False  # SQLite IoT registry not needed for fallback mode


def get_backend_info() -> dict:
    """Return info about which backend is active — useful for Settings page."""
    return {
        "backend": "supabase" if _USE_SUPABASE else "sqlite",
        "supabase_url": SUPABASE_URL if _USE_SUPABASE else None,
        "sqlite_path": None if _USE_SUPABASE else _SQLITE_DB,
        "iot_ready": _USE_SUPABASE,
    }
