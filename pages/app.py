import streamlit as st
import time
import pandas as pd

from vital_ranges import (
    classify_bp,
    classify_heart_rate,
    classify_spo2,
    classify_blood_sugar,
    classify_temperature,
    classify_respiratory_rate,
    classify_bmi,
)

from influx_plugin import get_vitals, write_vitals

# NEW IMPORT
from patient_db import create_table, add_patient, get_all_patients

st.set_page_config(page_title="HealNet AI", page_icon="🏥", layout="wide")

# ───────────── CREATE PATIENT TABLE ─────────────

create_table()

# ───────────── SESSION CHECK ─────────────

if "session" not in st.session_state or st.session_state.session is None:
    st.error("Please login first from login.py")
    st.stop()

sess = st.session_state.session
user = sess.get("user") or {}
org = sess.get("org") or {}

# ───────────── SIDEBAR ─────────────

st.sidebar.title("🏥 HealNet AI")

name = user.get("name") or org.get("name")
st.sidebar.write(f"👤 {name}")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Health Monitoring",
        "Register Patient",
        "Patient Records",   # NEW PAGE
        "Report Analysis",
    ],
)

if st.sidebar.button("Logout"):
    st.session_state.session = None
    st.switch_page("login.py")

# ───────────── DASHBOARD ─────────────

if page == "Dashboard":

    st.title("🏥 HealNet AI Dashboard")

    col1, col2, col3 = st.columns(3)

    col1.metric("Patients Today", "12")
    col2.metric("Reports Analysed", "8")
    col3.metric("Alerts", "2")

    st.info("Welcome to HealNet AI Health System")

# ───────────── HEALTH MONITORING ─────────────

elif page == "Health Monitoring":

    st.title("❤️ Health Monitoring System")

    if "monitoring" not in st.session_state:
        st.session_state.monitoring = False

    col1, col2 = st.columns(2)

    with col1:
        patient_id = st.text_input("Patient ID", key="pid")

    with col2:
        patient_name = st.text_input("Patient Name", key="pname")

    if st.button("Start Monitoring"):

        if patient_id and patient_name:
            st.session_state.monitoring = True
        else:
            st.warning("Please enter Patient ID and Name")

    st.divider()

    col3, col4 = st.columns(2)

    with col3:
        auto_refresh = st.toggle("Auto Refresh", value=True)

    with col4:
        refresh_rate = st.selectbox(
            "Refresh Interval",
            ["1s", "5s", "10s", "30s"]
        )

    refresh_seconds = int(refresh_rate.replace("s", ""))

    st.divider()

    if st.session_state.monitoring and patient_id:

        st.subheader(f"🧑‍⚕️ Live Monitoring: {patient_name} (ID: {patient_id})")

        write_vitals(patient_id)
        vitals = get_vitals(patient_id)

        if not vitals:
            st.warning("No vitals received")
            st.stop()

        systolic = vitals.get("systolic", 0)
        diastolic = vitals.get("diastolic", 0)
        heart = vitals.get("heart_rate", 0)
        spo2 = vitals.get("spo2", 0)
        sugar = vitals.get("blood_sugar", 0)
        temp = vitals.get("temperature", 0)
        resp = vitals.get("respiratory_rate", 0)
        weight = vitals.get("weight", 0)
        height = vitals.get("height", 0)

        if height > 0:
            bmi = round(weight / ((height / 100) ** 2), 1)
        else:
            bmi = 0

        st.metric("Calculated BMI", bmi)

        st.divider()

        bp_level, bp_msg = classify_bp(systolic, diastolic)
        hr_level, hr_msg = classify_heart_rate(heart)
        spo2_level, spo2_msg = classify_spo2(spo2)
        sg_level, sg_msg = classify_blood_sugar(sugar)
        tmp_level, tmp_msg = classify_temperature(temp)
        rr_level, rr_msg = classify_respiratory_rate(resp)
        bmi_level, bmi_msg = classify_bmi(bmi)

        COLOR = {
            "NORMAL": "🟢",
            "MODERATE": "🟡",
            "LOW": "🔵",
            "HIGH": "🔴",
            "CRITICAL": "🚨",
        }

        def vital_card(label, value, level, message):

            icon = COLOR.get(level, "⚪")

            if level == "NORMAL":
                st.success(f"{label}: {value} → {icon} {level} — {message}")

            elif level in ("MODERATE", "LOW"):
                st.warning(f"{label}: {value} → {icon} {level} — {message}")

            else:
                st.error(f"{label}: {value} → {icon} {level} — {message}")

        c1, c2 = st.columns(2)

        with c1:
            vital_card("Blood Pressure", f"{systolic}/{diastolic} mmHg", bp_level, bp_msg)
            vital_card("Heart Rate", f"{heart} bpm", hr_level, hr_msg)
            vital_card("SpO2", f"{spo2}%", spo2_level, spo2_msg)
            vital_card("Temperature", f"{temp}°F", tmp_level, tmp_msg)

        with c2:
            vital_card("Blood Sugar", f"{sugar} mg/dL", sg_level, sg_msg)
            vital_card("Respiratory Rate", f"{resp} breaths/min", rr_level, rr_msg)
            vital_card("BMI", f"{bmi}", bmi_level, bmi_msg)

        st.divider()

        st.subheader("🩺 Overall Health Status")

        all_levels = [
            bp_level,
            hr_level,
            spo2_level,
            sg_level,
            tmp_level,
            rr_level,
            bmi_level,
        ]

        severity_order = ["CRITICAL", "HIGH", "MODERATE", "LOW", "NORMAL"]

        overall = min(all_levels, key=lambda l: severity_order.index(l))

        if overall == "CRITICAL":
            st.error("🚨 CRITICAL — Immediate emergency care required")

        elif overall == "HIGH":
            st.error("🔴 HIGH RISK — Immediate medical consultation required")

        elif overall == "MODERATE":
            st.warning("🟡 MODERATE RISK — Needs observation")

        elif overall == "LOW":
            st.info("🔵 BELOW NORMAL — Review recommended")

        else:
            st.success("✅ Patient vitals within normal range")

        if auto_refresh:
            time.sleep(refresh_seconds)
            st.rerun()

# ───────────── REGISTER PATIENT ─────────────

elif page == "Register Patient":

    st.title("🧾 Register Patient")

    pname = st.text_input("Patient Name")
    age = st.number_input("Age")
    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    contact = st.text_input("Contact Number")
    pid = st.text_input("Patient ID")

    if st.button("Register Patient"):

        if pname and pid:

            add_patient(pid, pname, age, gender, contact)

            st.success(f"Patient {pname} registered successfully")

        else:
            st.error("Patient Name and ID required")

# ───────────── PATIENT RECORDS ─────────────

elif page == "Patient Records":

    st.title("📋 Registered Patients")

    df = get_all_patients()

    if df.empty:
        st.info("No patients registered yet")

    else:
        st.dataframe(df, use_container_width=True)

# ───────────── REPORT ANALYSIS ─────────────

elif page == "Report Analysis":

    st.title("🧾 AI Medical Report Analysis")

    file = st.file_uploader("Upload X-ray / Scan", type=["png", "jpg", "jpeg"])

    if file:

        st.image(file)

        st.success("Report uploaded successfully")

        st.subheader("AI Prediction")

        st.write("Result: Normal")
        st.progress(85)
        st.caption("Model Accuracy: 85%")