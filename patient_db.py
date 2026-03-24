import sqlite3
import pandas as pd

# =========================================================
# UNIVERSAL DATABASE SETUP (AUTO-FIXES MISSING COLUMNS)
# You will NOT need to manually alter the table again
# =========================================================

def create_table():

    conn = sqlite3.connect("patients.db")
    cursor = conn.cursor()

    # Create base table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id TEXT PRIMARY KEY
    )
    """)

    # Required columns list
    required_columns = {
        "name": "TEXT",
        "age": "INTEGER",
        "gender": "TEXT",
        "contact": "TEXT",
        "blood_group": "TEXT",
        "registered_by": "TEXT"
    }

    # Get existing columns
    cursor.execute("PRAGMA table_info(patients)")
    existing_columns = [column[1] for column in cursor.fetchall()]

    # Add missing columns automatically
    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE patients ADD COLUMN {column_name} {column_type}")
            print(f"Added missing column: {column_name}")

    conn.commit()
    conn.close()


# =========================================================
# ADD PATIENT
# =========================================================

def add_patient(pid, pname, age, gender, contact, blood, registered_by):

    try:
        conn = sqlite3.connect("patients.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO patients
        (patient_id, name, age, gender, contact, blood_group, registered_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pid, pname, age, gender, contact, blood, registered_by))

        conn.commit()
        conn.close()

        return True, None

    except sqlite3.IntegrityError:
        return False, "Patient ID already exists"


# =========================================================
# GET ALL PATIENTS
# =========================================================

def get_all_patients():

    conn = sqlite3.connect("patients.db")

    df = pd.read_sql_query("""
        SELECT
        patient_id AS "Patient ID",
        name AS "Name",
        age AS "Age",
        gender AS "Gender",
        contact AS "Contact",
        blood_group AS "Blood Group",
        registered_by AS "Registered By"
        FROM patients
    """, conn)

    conn.close()

    return df


# =========================================================
# DELETE PATIENT
# =========================================================

def delete_patient(patient_id):

    conn = sqlite3.connect("patients.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))

    conn.commit()
    conn.close()


# =========================================================
# OPTIONAL: GET SINGLE PATIENT
# (Useful for future features like edit/view)
# =========================================================

def get_patient(patient_id):

    conn = sqlite3.connect("patients.db")

    df = pd.read_sql_query("""
        SELECT *
        FROM patients
        WHERE patient_id = ?
    """, conn, params=(patient_id,))

    conn.close()

    return df
