from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import streamlit as st
import random
from datetime import datetime

# ─── InfluxDB Cloud Configuration ───
url = st.secrets.get("url", "")
token = st.secrets.get("token", "")
org = st.secrets.get("org", "")
bucket = st.secrets.get("bucket", "")

client = InfluxDBClient(url=url, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()

# ───────────────── WRITE VITALS ─────────────────
def write_vitals(patient_id, source="Simulated"):
    try:
        patient_id = str(patient_id)   # ✅ ensure matching type

        point = (
            Point("patient_vitals")
            .tag("patient_id", patient_id)
            .tag("source", source)
            .field("systolic", random.randint(100, 150))
            .field("diastolic", random.randint(60, 100))
            .field("heart_rate", random.randint(60, 120))
            .field("spo2", random.randint(90, 100))
            .field("blood_sugar", random.randint(80, 180))
            .field("temperature", round(random.uniform(97, 102), 1))
            .field("respiratory_rate", random.randint(12, 25))
            .field("weight", random.randint(50, 90))
            .field("height", random.randint(150, 180))
            .time(datetime.utcnow())
        )

        write_api.write(bucket=bucket, org=org, record=point)

    except Exception as e:
        print("❌ Error writing vitals:", e)


# ───────────────── GET VITALS ─────────────────
def get_vitals(patient_id):
    import random
    from datetime import datetime

    try:
        patient_id = str(patient_id)

        query = f'''
        from(bucket: "{bucket}")
          |> range(start: -1m)
          |> filter(fn: (r) => r["_measurement"] == "patient_vitals")
          |> filter(fn: (r) => r["patient_id"] == "{patient_id}")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: 1)
        '''

        tables = query_api.query(org=org, query=query)

        vitals = {}
        timestamp = None
        source = "InfluxDB"

        for table in tables:
            for record in table.records:
                vitals[record.get_field()] = record.get_value()
                timestamp = record.get_time()

        # 🔥 IF DB DATA IS OLD OR EMPTY → FORCE NEW VALUES
        if not vitals or timestamp is None:
            raise Exception("No fresh DB data")

        return {
            "data": vitals,
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "source": source
        }

    except Exception:
        # 🔥 FALLBACK → ALWAYS NEW LIVE DATA
        vitals = {
            "systolic": random.randint(100, 150),
            "diastolic": random.randint(60, 100),
            "heart_rate": random.randint(60, 120),
            "spo2": random.randint(90, 100),
            "blood_sugar": random.randint(80, 180),
            "temperature": round(random.uniform(97, 102), 1),
            "respiratory_rate": random.randint(12, 25),
            "weight": random.randint(50, 90),
            "height": random.randint(150, 180)
        }

        return {
            "data": vitals,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "Simulated Live"
        }

# ───────────────── FALLBACK ─────────────────
def fallback_vitals():
    return {
        "data": {
            "systolic": 120,
            "diastolic": 80,
            "heart_rate": 75,
            "spo2": 98,
            "blood_sugar": 110,
            "temperature": 98.6,
            "respiratory_rate": 18,
            "weight": 70,
            "height": 170
        },
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "Simulated (Fallback)"
    }
