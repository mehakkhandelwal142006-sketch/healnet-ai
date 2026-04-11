import sqlite3
import datetime
import pandas as pd

DB_PATH = "healnet.db"


# ─────────────────────────────────────────────────────────────────────────────
#  CREATE TABLE  (with safe migration for created_at column)
# ─────────────────────────────────────────────────────────────────────────────
def create_table():
    """Create the patients table and safely migrate any missing columns."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id           TEXT    UNIQUE NOT NULL,
            name                 TEXT    NOT NULL,
            age                  INTEGER,
            gender               TEXT,
            contact              TEXT,
            blood_group          TEXT,
            registered_by        TEXT,
            created_at           TEXT    DEFAULT (datetime('now','localtime')),
            email                TEXT,
            address              TEXT,
            allergies            TEXT,
            chronic_conditions   TEXT,
            current_medications  TEXT,
            past_surgeries       TEXT,
            family_history       TEXT,
            medical_notes        TEXT,
            emergency_name       TEXT,
            emergency_relation   TEXT,
            emergency_contact    TEXT,
            updated_at           TEXT
        )
    """)
    conn.commit()

    # Safe migration: add any missing columns to existing tables
    existing_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(patients)")
    }
    new_columns = {
        "created_at":          "TEXT DEFAULT (datetime('now','localtime'))",
        "email":               "TEXT",
        "address":             "TEXT",
        "allergies":           "TEXT",
        "chronic_conditions":  "TEXT",
        "current_medications": "TEXT",
        "past_surgeries":      "TEXT",
        "family_history":      "TEXT",
        "medical_notes":       "TEXT",
        "emergency_name":      "TEXT",
        "emergency_relation":  "TEXT",
        "emergency_contact":   "TEXT",
        "updated_at":          "TEXT",
        "vitals_last_updated": "TEXT",
        "data_source": "TEXT"
    }
    for col, col_type in new_columns.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE patients ADD COLUMN {col} {col_type}")
    conn.commit()

    # Backfill created_at for any rows missing it
    conn.execute("""
        UPDATE patients
        SET created_at = datetime('now','localtime')
        WHERE created_at IS NULL
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
#  ADD PATIENT
# ─────────────────────────────────────────────────────────────────────────────
def add_patient(patient_id, name, age, gender, contact,
                blood_group=None, blood=None,
                registered_by="Admin",
                email=None, address=None,
                allergies=None, chronic_conditions=None,
                current_medications=None, past_surgeries=None,
                family_history=None, medical_notes=None,
                emergency_name=None, emergency_relation=None,
                emergency_contact=None):
    """
    Insert a new patient record.
    Accepts both blood_group= and blood= (app.py uses blood=).
    Returns (True, "") on success, (False, error_message) on failure.
    """
    # Accept either keyword: blood= or blood_group=
    resolved_blood = blood_group or blood

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO patients (
                patient_id, name, age, gender, contact, blood_group, registered_by, created_at,
                email, address, allergies, chronic_conditions, current_medications,
                past_surgeries, family_history, medical_notes,
                emergency_name, emergency_relation, emergency_contact
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'),
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            patient_id, name, age, gender, contact, resolved_blood, registered_by,
            email, address, allergies, chronic_conditions, current_medications,
            past_surgeries, family_history, medical_notes,
            emergency_name, emergency_relation, emergency_contact
        ))
        conn.commit()
        conn.close()
        return True, ""
    except sqlite3.IntegrityError:
        return False, f"Patient ID '{patient_id}' already exists. Use a unique ID."
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
#  GET SINGLE PATIENT
# ─────────────────────────────────────────────────────────────────────────────
def get_patient(patient_id):
    """
    Fetch a single patient by patient_id.
    Returns a dict with patient fields, or None if not found.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM patients WHERE patient_id = ?", (patient_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  GET ALL PATIENTS
# ─────────────────────────────────────────────────────────────────────────────
def get_all_patients():
    """
    Return all patients as a pandas DataFrame.
    Columns: Patient ID, Name, Age, Gender, Contact, Blood Group, Registered By, Created At
    """
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT
            patient_id   AS "Patient ID",
            name         AS "Name",
            age          AS "Age",
            gender       AS "Gender",
            contact      AS "Contact",
            blood_group  AS "Blood Group",
            registered_by AS "Registered By",
            created_at   AS "Created At"
        FROM patients
        ORDER BY id DESC
    """, conn)
    conn.close()
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  UPDATE PATIENT
# ─────────────────────────────────────────────────────────────────────────────
def update_patient(patient_id, name=None, age=None, gender=None,
                   contact=None, blood_group=None, blood=None,
                   email=None, address=None,
                   allergies=None, chronic_conditions=None,
                   current_medications=None, past_surgeries=None,
                   family_history=None, medical_notes=None,
                   emergency_name=None, emergency_relation=None,
                   emergency_contact=None):
    """
    Update one or more fields of an existing patient.
    Only non-None values are updated. updated_at is always stamped.
    Returns (True, "") on success, (False, error_message) on failure.
    """
    fields = []
    values = []

    resolved_blood = blood_group or blood

    if name               is not None: fields.append("name = ?");               values.append(name)
    if age                is not None: fields.append("age = ?");                values.append(age)
    if gender             is not None: fields.append("gender = ?");             values.append(gender)
    if contact            is not None: fields.append("contact = ?");            values.append(contact)
    if resolved_blood     is not None: fields.append("blood_group = ?");        values.append(resolved_blood)
    if email              is not None: fields.append("email = ?");              values.append(email)
    if address            is not None: fields.append("address = ?");            values.append(address)
    if allergies          is not None: fields.append("allergies = ?");          values.append(allergies)
    if chronic_conditions is not None: fields.append("chronic_conditions = ?"); values.append(chronic_conditions)
    if current_medications is not None: fields.append("current_medications = ?"); values.append(current_medications)
    if past_surgeries     is not None: fields.append("past_surgeries = ?");     values.append(past_surgeries)
    if family_history     is not None: fields.append("family_history = ?");     values.append(family_history)
    if medical_notes      is not None: fields.append("medical_notes = ?");      values.append(medical_notes)
    if emergency_name     is not None: fields.append("emergency_name = ?");     values.append(emergency_name)
    if emergency_relation is not None: fields.append("emergency_relation = ?"); values.append(emergency_relation)
    if emergency_contact  is not None: fields.append("emergency_contact = ?");  values.append(emergency_contact)

    if not fields:
        return False, "No fields provided to update."

    # Always stamp updated_at
    fields.append("updated_at = datetime('now','localtime')")

    values.append(patient_id)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            f"UPDATE patients SET {', '.join(fields)} WHERE patient_id = ?",
            values
        )
        conn.commit()
        conn.close()
        return True, ""
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
#  DELETE PATIENT
# ─────────────────────────────────────────────────────────────────────────────
def delete_patient(patient_id):
    """
    Delete a patient by patient_id.
    Returns (True, "") on success, (False, error_message) on failure.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
        conn.commit()
        conn.close()
        return True, ""
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
#  SEARCH PATIENTS
# ─────────────────────────────────────────────────────────────────────────────
def search_patients(query="", gender_f="All", blood_f="All", cond_f=""):
    """
    Search patients by name or patient_id (case-insensitive partial match),
    with optional filters for gender, blood group, and condition.

    Parameters
    ----------
    query    : str  — partial match against name or patient_id
    gender_f : str  — "All" or one of "Male" / "Female" / "Other"
    blood_f  : str  — "All" or a blood group like "A+", "O-", etc.
    cond_f   : str  — partial match against any text field (currently unused
                      unless you add a condition column; kept for future use)

    Returns a pandas DataFrame (same columns as get_all_patients).
    """
    conn = sqlite3.connect(DB_PATH)

    sql = """
        SELECT
            patient_id    AS "Patient ID",
            name          AS "Name",
            age           AS "Age",
            gender        AS "Gender",
            contact       AS "Contact",
            blood_group   AS "Blood Group",
            registered_by AS "Registered By",
            created_at    AS "Created At"
        FROM patients
        WHERE (name LIKE ? OR patient_id LIKE ?)
    """
    like = f"%{query}%"
    params = [like, like]

    if gender_f and gender_f != "All":
        sql += " AND gender = ?"
        params.append(gender_f)

    if blood_f and blood_f != "All":
        sql += " AND blood_group = ?"
        params.append(blood_f)

    if cond_f and cond_f.strip():
        # Future-proof: searches name field for condition text until a
        # dedicated condition column is added to the schema.
        sql += " AND name LIKE ?"
        params.append(f"%{cond_f}%")

    sql += " ORDER BY created_at DESC"

    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  GET PATIENT STATS  (fixed — never crashes on legacy databases)
# ─────────────────────────────────────────────────────────────────────────────
def get_patient_stats():
    conn = sqlite3.connect(DB_PATH)

    # Check existing columns
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(patients)")
    }

    total = conn.execute(
        "SELECT COUNT(*) FROM patients"
    ).fetchone()[0]

    def safe_count(column, value):
        if column not in cols:
            return 0
        return conn.execute(
            f"SELECT COUNT(*) FROM patients WHERE {column} = ?",
            (value,)
        ).fetchone()[0]

    male = safe_count("gender", "Male")
    female = safe_count("gender", "Female")
    other = safe_count("gender", "Other")

    today = 0
    if "created_at" in cols:
        today_str = datetime.date.today().isoformat()
        today = conn.execute(
            "SELECT COUNT(*) FROM patients WHERE created_at LIKE ?",
            (f"{today_str}%",)
        ).fetchone()[0]

    conn.close()

    return {
        "total": total,
        "today": today,
        "male": male,
        "female": female,
        "other": other,
    }

# ─────────────────────────────────────────────────────────────────────────────
#  Run directly to migrate existing database
#  Usage:  python patient_db.py
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    create_table()
    stats = get_patient_stats()
    print("Migration complete. Current stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
