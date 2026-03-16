import sqlite3
import pandas as pd

DB_NAME = "patients.db"

def create_table():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id TEXT PRIMARY KEY,
        name TEXT,
        age INTEGER,
        gender TEXT,
        contact TEXT
    )
    """)

    conn.commit()
    conn.close()


def add_patient(pid, name, age, gender, contact):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO patients VALUES (?, ?, ?, ?, ?)",
        (pid, name, age, gender, contact)
    )

    conn.commit()
    conn.close()


def get_all_patients():

    conn = sqlite3.connect("patients.db")

    df = pd.read_sql_query("SELECT * FROM patients", conn)

    conn.close()

    return df

def delete_patient(patient_id):

    import sqlite3

    conn = sqlite3.connect("patients.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM patients WHERE patient_id = ?",
        (patient_id,)
    )

    conn.commit()
    conn.close()
