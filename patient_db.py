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

    conn = sqlite3.connect(DB_NAME)

    df = pd.read_sql("SELECT * FROM patients", conn)

    conn.close()

    return df