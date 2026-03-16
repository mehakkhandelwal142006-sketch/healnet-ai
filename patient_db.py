import sqlite3
import pandas as pd


# ───────── CREATE TABLE ─────────
def create_table():

    import sqlite3

    conn = sqlite3.connect("patients.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id TEXT PRIMARY KEY,
        name TEXT,
        age INTEGER,
        gender TEXT,
        contact TEXT,
        blood_group TEXT,
        registered_by TEXT
    )
    """)

    conn.commit()
    conn.close()


# ───────── ADD PATIENT ─────────
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


# ───────── GET ALL PATIENTS ─────────
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


# ───────── DELETE PATIENT ─────────
def delete_patient(patient_id):

    conn = sqlite3.connect("patients.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))

    conn.commit()
    conn.close()
