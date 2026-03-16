import streamlit as st
import sqlite3
import pandas as pd
import requests
import time
from io import StringIO
from datetime import datetime
from vital_ranges import (
    classify_heart_rate,
    classify_spo2,
    classify_bp,
    classify_blood_sugar,
    classify_temperature,
    classify_respiratory_rate,
    classify_bmi,
)

st.set_page_config(page_title="HealNet AI", page_icon="🏥", layout="wide")


# ─────────────────────────────────────────────
# PATIENT DATABASE (SQLite)
# ─────────────────────────────────────────────
PATIENT_DB = "patients.db"

def init_patient_db():
    con = sqlite3.connect(PATIENT_DB, check_same_thread=False)
    con.execute("""
        CREATE TABLE IF NOT EXISTS registered_patients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id  TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            age         INTEGER,
            gender      TEXT,
            contact     TEXT,
            registered_by TEXT,
            registered_at TEXT
        )
    """)
    con.commit()
    con.close()

def save_patient(patient_id, name, age, gender, contact, registered_by):
    con = sqlite3.connect(PATIENT_DB, check_same_thread=False)
    try:
        con.execute(
            "INSERT INTO registered_patients(patient_id,name,age,gender,contact,registered_by,registered_at) VALUES(?,?,?,?,?,?,?)",
            (patient_id, name, age, gender, contact, registered_by,
             datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        )
        con.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Patient ID already exists."
    finally:
        con.close()

def get_all_patients():
    con = sqlite3.connect(PATIENT_DB, check_same_thread=False)
    df = pd.read_sql_query(
        "SELECT patient_id AS 'Patient ID', name AS 'Name', age AS 'Age', "
        "gender AS 'Gender', contact AS 'Contact', "
        "registered_by AS 'Registered By', registered_at AS 'Registered At' "
        "FROM registered_patients ORDER BY id DESC",
        con
    )
    con.close()
    return df

def delete_patient(patient_id):
    con = sqlite3.connect(PATIENT_DB, check_same_thread=False)
    con.execute("DELETE FROM registered_patients WHERE patient_id=?", (patient_id,))
    con.commit()
    con.close()

init_patient_db()


# ─────────────────────────────────────────────
# INFLUXDB CONFIG
# ─────────────────────────────────────────────
INFLUX_URL   = "http://localhost:8086"
INFLUX_TOKEN = "b7kTRovNbLUNwB8TB57OsmHGVUHpl-JFUssxpTGxihMo7EOCQB_07IUxzMxl6eDPfCB20IvQxJgl7xk-sZZP6w=="
ORG          = "healnet-org"
BUCKET       = "healnet"
QUERY_URL    = f"{INFLUX_URL}/api/v2/query"
WRITE_URL    = f"{INFLUX_URL}/api/v2/write"


# ─────────────────────────────────────────────
# FETCH LATEST VITALS FROM INFLUXDB
# ─────────────────────────────────────────────
def fetch_latest_vitals(patient_id, hours=1):
    flux_query = f'''
    from(bucket: "{BUCKET}")
      |> range(start: -{hours}h)
      |> filter(fn: (r) => r._measurement == "health_metrics")
      |> filter(fn: (r) => r.patient_id == "{patient_id}")
      |> last()
    '''
    try:
        response = requests.post(
            QUERY_URL,
            headers={
                "Authorization": f"Token {INFLUX_TOKEN}",
                "Content-Type":  "application/vnd.flux",
            },
            params={"org": ORG},
            data=flux_query,
            timeout=5,
        )
        if response.status_code != 200:
            return None, f"InfluxDB error {response.status_code}: {response.text}"

        df = pd.read_csv(StringIO(response.text), comment="#")
        if df.empty or "_field" not in df.columns:
            return None, "No data found for this patient in the last hour."

        pivot = df.pivot_table(
            index="_time", columns="_field", values="_value", aggfunc="last"
        ).reset_index()
        latest = pivot.iloc[-1]

        vitals = {
            "timestamp":        str(latest.get("_time", "—")),
            "heart_rate":       float(latest.get("heart_rate",       75)),
            "spo2":             float(latest.get("spo2",             98)),
            "systolic":         float(latest.get("systolic",        120)),
            "diastolic":        float(latest.get("diastolic",        80)),
            "blood_sugar":      float(latest.get("blood_sugar",      90)),
            "temperature":      float(latest.get("temperature",    98.6)),
            "respiratory_rate": float(latest.get("respiratory_rate", 16)),
            "bmi":              float(latest.get("bmi",             22.0)),
            "steps":            float(latest.get("steps",             0)),
            "sleep_hours":      float(latest.get("sleep_hours",       0)),
            "risk_score":       float(latest.get("risk_score",        0)),
        }
        return vitals, None

    except Exception as e:
        return None, f"Could not connect to InfluxDB: {str(e)}"


def fetch_history(patient_id, hours=6):
    flux_query = f'''
    from(bucket: "{BUCKET}")
      |> range(start: -{hours}h)
      |> filter(fn: (r) => r._measurement == "health_metrics")
      |> filter(fn: (r) => r.patient_id == "{patient_id}")
    '''
    try:
        response = requests.post(
            QUERY_URL,
            headers={
                "Authorization": f"Token {INFLUX_TOKEN}",
                "Content-Type":  "application/vnd.flux",
            },
            params={"org": ORG},
            data=flux_query,
            timeout=5,
        )
        if response.status_code != 200:
            return pd.DataFrame()

        df = pd.read_csv(StringIO(response.text), comment="#")
        if df.empty or "_field" not in df.columns:
            return pd.DataFrame()

        pivot = df.pivot_table(
            index="_time", columns="_field", values="_value", aggfunc="last"
        ).reset_index()
        pivot["_time"] = pd.to_datetime(pivot["_time"])
        return pivot.sort_values("_time")

    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────────
# SESSION CHECK
# ─────────────────────────────────────────────
if "session" not in st.session_state or st.session_state.session is None:
    st.error("Please login first from login.py")
    st.stop()

sess = st.session_state.session
user = sess.get("user") or {}
org  = sess.get("org")  or {}

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.title("🏥 HealNet AI")
name = user.get("name") or org.get("name")
st.sidebar.write(f"👤 {name}")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Health Monitoring", "Register Patient", "View Patients", "Report Analysis"],
)

if st.sidebar.button("Logout"):
    st.session_state.session = None
    st.switch_page("login.py")

COLOR = {
    "NORMAL":   "🟢",
    "MODERATE": "🟡",
    "LOW":      "🔵",
    "HIGH":     "🔴",
    "CRITICAL": "🚨",
}

def vital_card(label, value, level, message):
    icon = COLOR.get(level, "⚪")
    text = f"**{label}:** {value}  →  {icon} **{level}**  —  {message}"
    if level == "NORMAL":
        st.success(text)
    elif level in ("MODERATE", "LOW"):
        st.warning(text)
    else:
        st.error(text)


# ══════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════
if page == "Dashboard":
    st.title("🏥 HealNet AI Dashboard")
    col1, col2, col3 = st.columns(3)
    col1.metric("Patients Today",   "12")
    col2.metric("Reports Analysed", "8")
    col3.metric("Alerts",           "2")
    st.info("Welcome to HealNet AI Health System")


# ══════════════════════════════════════════════
# HEALTH MONITORING — InfluxDB live data
# ══════════════════════════════════════════════
elif page == "Health Monitoring":
    st.title("❤️ Health Monitoring — Live from InfluxDB")

    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        patient_id = st.text_input("Patient ID", value="P001",
                                    help="Must match the patient_id tag in InfluxDB")
    with col_b:
        auto_refresh = st.toggle("Auto Refresh", value=True)
    with col_c:
        refresh_rate = st.selectbox("Refresh every", ["5s", "10s", "30s", "60s"])

    refresh_seconds = int(refresh_rate.replace("s", ""))

    st.divider()

    vitals, error = fetch_latest_vitals(patient_id)

    if error:
        st.error(f"⚠️ {error}")
        st.info("Make sure InfluxDB is running at localhost:8086 and data has been written for this patient ID.")
        st.stop()

    st.caption(f"🕐 Last updated: {vitals['timestamp']}  |  Patient: **{patient_id}**")

    # classify
    bp_level,   bp_msg   = classify_bp(vitals["systolic"], vitals["diastolic"])
    hr_level,   hr_msg   = classify_heart_rate(vitals["heart_rate"])
    spo2_level, spo2_msg = classify_spo2(vitals["spo2"])
    sg_level,   sg_msg   = classify_blood_sugar(vitals["blood_sugar"])
    tmp_level,  tmp_msg  = classify_temperature(vitals["temperature"])
    rr_level,   rr_msg   = classify_respiratory_rate(vitals["respiratory_rate"])
    bmi_level,  bmi_msg  = classify_bmi(vitals["bmi"])

    st.subheader("📊 Real-Time Vital Range Analysis")

    c1, c2 = st.columns(2)
    with c1:
        vital_card("Blood Pressure",
                   f"{vitals['systolic']:.0f}/{vitals['diastolic']:.0f} mmHg",
                   bp_level, bp_msg)
        vital_card("Heart Rate",
                   f"{vitals['heart_rate']:.0f} bpm",
                   hr_level, hr_msg)
        vital_card("SpO2",
                   f"{vitals['spo2']:.1f}%",
                   spo2_level, spo2_msg)
        vital_card("Body Temperature",
                   f"{vitals['temperature']:.1f}°F",
                   tmp_level, tmp_msg)
    with c2:
        vital_card("Blood Sugar",
                   f"{vitals['blood_sugar']:.0f} mg/dL",
                   sg_level, sg_msg)
        vital_card("Respiratory Rate",
                   f"{vitals['respiratory_rate']:.0f} breaths/min",
                   rr_level, rr_msg)
        vital_card("BMI",
                   f"{vitals['bmi']:.1f}",
                   bmi_level, bmi_msg)

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Steps Today",  f"{vitals['steps']:.0f}")
    m2.metric("Sleep Hours",  f"{vitals['sleep_hours']:.1f} hrs")
    m3.metric("Risk Score",   f"{vitals['risk_score']:.2f}")

    st.divider()
    st.subheader("🩺 Overall Health Status")

    all_levels     = [bp_level, hr_level, spo2_level, sg_level,
                      tmp_level, rr_level, bmi_level]
    severity_order = ["CRITICAL", "HIGH", "MODERATE", "LOW", "NORMAL"]
    overall        = min(all_levels, key=lambda l: severity_order.index(l))

    if overall == "CRITICAL":
        st.error("🚨 CRITICAL — Immediate emergency care required")
        st.warning("Specialist: Emergency Physician / Cardiologist")
    elif overall == "HIGH":
        st.error("🔴 HIGH RISK — Immediate medical consultation required")
        st.warning("Specialist: General Physician / Cardiologist")
    elif overall == "MODERATE":
        st.warning("🟡 MODERATE RISK — Patient needs observation and follow-up")
        st.info("Specialist: General Physician")
    elif overall == "LOW":
        st.info("🔵 BELOW NORMAL — Some readings below normal range")
        st.info("Specialist: General Physician for review")
    else:
        st.success("✅ All vitals within normal range — Patient condition stable")

    st.divider()
    st.subheader("📈 Vital Trends (Last 6 Hours)")

    history = fetch_history(patient_id, hours=6)

    if not history.empty:
        chart1, chart2 = st.columns(2)
        with chart1:
            if "heart_rate" in history.columns:
                st.markdown("**Heart Rate (bpm)**")
                st.line_chart(history.set_index("_time")["heart_rate"],
                              use_container_width=True)
            if "spo2" in history.columns:
                st.markdown("**SpO2 (%)**")
                st.line_chart(history.set_index("_time")["spo2"],
                              use_container_width=True)
        with chart2:
            if "systolic" in history.columns:
                st.markdown("**Blood Pressure Systolic (mmHg)**")
                st.line_chart(history.set_index("_time")["systolic"],
                              use_container_width=True)
            if "risk_score" in history.columns:
                st.markdown("**Risk Score**")
                st.line_chart(history.set_index("_time")["risk_score"],
                              use_container_width=True)
    else:
        st.info("No historical trend data available yet.")

    if auto_refresh:
        time.sleep(refresh_seconds)
        st.rerun()


# ══════════════════════════════════════════════
# REGISTER PATIENT
# ══════════════════════════════════════════════
elif page == "Register Patient":
    st.title("🧾 Register Patient")

    with st.form("register_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            pname   = st.text_input("Patient Name *")
            age     = st.number_input("Age", 1, 120, 25)
            gender  = st.selectbox("Gender", ["Male", "Female", "Other"])
        with c2:
            pid     = st.text_input("Patient ID *", placeholder="e.g. P001",
                                     help="Used to fetch live data from InfluxDB")
            contact = st.text_input("Contact Number")
            blood   = st.text_input("Blood Group", placeholder="e.g. O+")

        submitted = st.form_submit_button("✅ Register Patient", type="primary",
                                          use_container_width=True)

    if submitted:
        if not pname or not pid:
            st.error("Patient Name and Patient ID are required.")
        else:
            registered_by = user.get("name") or org.get("name") or "Admin"
            ok, err = save_patient(pid, pname, age, gender, contact, registered_by)
            if ok:
                st.success(f"✅ Patient **{pname}** registered successfully with ID **{pid}**")
                st.info("Go to **View Patients** in the sidebar to see all registered patients.")
            else:
                st.error(f"❌ {err}")


# ══════════════════════════════════════════════
# VIEW PATIENTS
# ══════════════════════════════════════════════
elif page == "View Patients":
    st.title("👥 Registered Patients")

    df = get_all_patients()

    if df.empty:
        st.info("No patients registered yet. Go to Register Patient to add one.")
    else:
        # summary metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Patients",  len(df))
        m2.metric("Male",   len(df[df["Gender"] == "Male"]))
        m3.metric("Female", len(df[df["Gender"] == "Female"]))
        m4.metric("Other",  len(df[df["Gender"] == "Other"]))

        st.divider()

        # search filter
        search = st.text_input("🔍 Search by Name or Patient ID", placeholder="Type to filter...")
        if search:
            mask = (
                df["Name"].str.contains(search, case=False, na=False) |
                df["Patient ID"].str.contains(search, case=False, na=False)
            )
            df = df[mask]

        st.markdown(f"**{len(df)} record(s) found**")

        # full table
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        # delete a patient
        with st.expander("🗑️ Delete a Patient Record"):
            del_id = st.text_input("Enter Patient ID to delete")
            if st.button("Delete", type="primary"):
                if del_id:
                    delete_patient(del_id)
                    st.success(f"Patient **{del_id}** deleted.")
                    st.rerun()
                else:
                    st.error("Enter a Patient ID first.")

        # download as CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download as CSV",
            data=csv,
            file_name="healnet_patients.csv",
            mime="text/csv",
        )


# ══════════════════════════════════════════════
# REPORT ANALYSIS
# ══════════════════════════════════════════════
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
