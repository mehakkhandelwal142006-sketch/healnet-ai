from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import streamlit as st
import random

# ─── InfluxDB Cloud Configuration (from Streamlit Secrets) ───
url = st.secrets["https://us-east-1-1.aws.cloud2.influxdata.com"]
token = st.secrets["nhMnRR10-oZu29KBOzdWLvglc-XQaugoshd9_0ny9oHCrY4TfWqH1yXYX6Byw8ZfEf0WMnbMaMgeTX4WW1rsyQ=="]
org = st.secrets["healnet-org"]
bucket = st.secrets["healnet"]

client = InfluxDBClient(url=url, token=token, org=org)

write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()


# ───────────────── WRITE VITALS ─────────────────
def write_vitals(patient_id):

    systolic = random.randint(100, 150)
    diastolic = random.randint(60, 100)
    heart_rate = random.randint(60, 120)
    spo2 = random.randint(90, 100)
    blood_sugar = random.randint(80, 180)
    temperature = round(random.uniform(97, 102), 1)
    respiratory_rate = random.randint(12, 25)
    weight = random.randint(50, 90)
    height = random.randint(150, 180)

    point = (
        Point("patient_vitals")
        .tag("patient_id", patient_id)
        .field("systolic", systolic)
        .field("diastolic", diastolic)
        .field("heart_rate", heart_rate)
        .field("spo2", spo2)
        .field("blood_sugar", blood_sugar)
        .field("temperature", temperature)
        .field("respiratory_rate", respiratory_rate)
        .field("weight", weight)
        .field("height", height)
    )

    write_api.write(bucket=bucket, org=org, record=point)


# ───────────────── GET VITALS ─────────────────
def get_vitals(patient_id):

    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -10m)
      |> filter(fn: (r) => r["_measurement"] == "patient_vitals")
      |> filter(fn: (r) => r["patient_id"] == "{patient_id}")
      |> last()
    '''

    tables = query_api.query(org=org, query=query)

    vitals = {}

    for table in tables:
        for record in table.records:
            vitals[record.get_field()] = record.get_value()

    return vitals
    for table in tables:
        for record in table.records:
            vitals[record.get_field()] = record.get_value()

    return vitals
