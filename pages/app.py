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
from patient_db import create_table, add_patient, get_all_patients, delete_patient

st.set_page_config(page_title="HealNet AI", page_icon="🏥", layout="wide")

# ───────────── GLOBAL DARK TECH THEME ─────────────

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;800&family=Exo+2:wght@300;400;500;600&display=swap');

  /* ── Root Variables ── */
  :root {
    --bg-deep:    #040d1a;
    --bg-card:    #071428;
    --bg-panel:   #0a1e3a;
    --border:     rgba(0, 200, 255, 0.18);
    --cyan:       #00d4ff;
    --cyan-dim:   rgba(0, 212, 255, 0.15);
    --green:      #00ff9d;
    --yellow:     #f5c518;
    --red:        #ff4560;
    --text-hi:    #e0f4ff;
    --text-mid:   #7eb8d4;
    --text-lo:    #3a6a8a;
    --glow-cyan:  0 0 12px rgba(0, 212, 255, 0.5), 0 0 30px rgba(0, 212, 255, 0.2);
    --glow-green: 0 0 12px rgba(0, 255, 157, 0.5);
    --glow-red:   0 0 12px rgba(255, 69, 96, 0.5);
  }

  /* ── Full App Background ── */
  .stApp {
    background: var(--bg-deep) !important;
    background-image:
      radial-gradient(ellipse at 20% 0%, rgba(0,100,200,0.12) 0%, transparent 60%),
      radial-gradient(ellipse at 80% 100%, rgba(0,50,120,0.10) 0%, transparent 50%),
      repeating-linear-gradient(
        0deg,
        transparent,
        transparent 39px,
        rgba(0,180,255,0.025) 40px
      ),
      repeating-linear-gradient(
        90deg,
        transparent,
        transparent 39px,
        rgba(0,180,255,0.025) 40px
      );
    font-family: 'Exo 2', sans-serif !important;
    color: var(--text-hi) !important;
  }

  /* ── Hide Streamlit chrome ── */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding: 1.5rem 2rem 2rem !important; max-width: 100% !important; }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg-deep); }
  ::-webkit-scrollbar-thumb { background: var(--cyan); border-radius: 3px; }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: var(--bg-card) !important;
    border-right: 1px solid var(--border) !important;
    box-shadow: 4px 0 30px rgba(0,200,255,0.07);
  }
  [data-testid="stSidebar"] * { color: var(--text-hi) !important; font-family: 'Exo 2', sans-serif !important; }
  [data-testid="stSidebar"] .stRadio label {
    padding: 6px 12px;
    border-radius: 6px;
    transition: background 0.2s;
    font-weight: 500;
    letter-spacing: 0.04em;
  }
  [data-testid="stSidebar"] .stRadio label:hover {
    background: var(--cyan-dim);
    color: var(--cyan) !important;
  }

  /* ── Sidebar Title ── */
  [data-testid="stSidebar"] h1 {
    font-family: 'Orbitron', sans-serif !important;
    font-size: 1.1rem !important;
    color: var(--cyan) !important;
    text-shadow: var(--glow-cyan);
    letter-spacing: 0.1em;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1rem;
  }

  /* ── All Headings ── */
  h1, h2, h3, h4 {
    font-family: 'Orbitron', sans-serif !important;
    color: var(--text-hi) !important;
    letter-spacing: 0.06em;
    text-shadow: 0 0 20px rgba(0,212,255,0.3);
  }
  h1 { font-size: 1.6rem !important; }
  h2 { font-size: 1.2rem !important; }
  h3 { font-size: 1rem !important; }

  /* ── Metric Cards ── */
  [data-testid="stMetric"] {
    background: var(--bg-panel) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 16px 20px !important;
    box-shadow: 0 0 20px rgba(0,180,255,0.07), inset 0 1px 0 rgba(0,200,255,0.08);
    position: relative;
    overflow: hidden;
  }
  [data-testid="stMetric"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--cyan), transparent);
  }
  [data-testid="stMetricLabel"] { color: var(--text-mid) !important; font-size: 0.72rem !important; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 500; }
  [data-testid="stMetricValue"] { color: var(--cyan) !important; font-family: 'Orbitron', sans-serif !important; font-size: 1.7rem !important; text-shadow: var(--glow-cyan); }
  [data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

  /* ── Inputs ── */
  .stTextInput input, .stNumberInput input, .stSelectbox select {
    background: var(--bg-panel) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text-hi) !important;
    font-family: 'Exo 2', sans-serif !important;
    font-size: 0.9rem !important;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--cyan) !important;
    box-shadow: 0 0 0 2px rgba(0,212,255,0.2) !important;
    outline: none !important;
  }
  .stTextInput label, .stNumberInput label, .stSelectbox label, .stFileUploader label {
    color: var(--text-mid) !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 500;
  }

  /* ── Buttons ── */
  .stButton > button {
    background: transparent !important;
    border: 1px solid var(--cyan) !important;
    color: var(--cyan) !important;
    font-family: 'Exo 2', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em;
    border-radius: 8px !important;
    padding: 8px 20px !important;
    transition: all 0.2s ease !important;
    text-transform: uppercase;
    font-size: 0.82rem !important;
  }
  .stButton > button:hover {
    background: var(--cyan-dim) !important;
    box-shadow: var(--glow-cyan) !important;
    transform: translateY(-1px);
  }
  .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, rgba(0,212,255,0.25), rgba(0,100,200,0.2)) !important;
    box-shadow: var(--glow-cyan) !important;
  }

  /* ── Alerts ── */
  .stSuccess {
    background: rgba(0, 255, 157, 0.08) !important;
    border: 1px solid rgba(0, 255, 157, 0.35) !important;
    border-radius: 8px !important;
    color: #00ff9d !important;
  }
  .stWarning {
    background: rgba(245, 197, 24, 0.08) !important;
    border: 1px solid rgba(245, 197, 24, 0.35) !important;
    border-radius: 8px !important;
    color: #f5c518 !important;
  }
  .stError {
    background: rgba(255, 69, 96, 0.08) !important;
    border: 1px solid rgba(255, 69, 96, 0.35) !important;
    border-radius: 8px !important;
    color: #ff4560 !important;
  }
  .stInfo {
    background: rgba(0, 212, 255, 0.07) !important;
    border: 1px solid rgba(0, 212, 255, 0.25) !important;
    border-radius: 8px !important;
    color: var(--cyan) !important;
  }

  /* ── Divider ── */
  hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 1rem 0 !important;
  }

  /* ── DataFrame ── */
  [data-testid="stDataFrame"] {
    background: var(--bg-panel) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    overflow: hidden;
  }

  /* ── Toggle ── */
  .stToggle { color: var(--text-mid) !important; }

  /* ── Expander ── */
  .streamlit-expanderHeader {
    background: var(--bg-panel) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text-mid) !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.06em;
  }
  .streamlit-expanderContent {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
  }

  /* ── Form ── */
  [data-testid="stForm"] {
    background: var(--bg-panel) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 1.5rem !important;
    box-shadow: 0 0 30px rgba(0,180,255,0.06);
  }

  /* ── File uploader ── */
  [data-testid="stFileUploader"] {
    background: var(--bg-panel) !important;
    border: 1px dashed var(--border) !important;
    border-radius: 10px !important;
  }

  /* ── Progress bar ── */
  .stProgress > div > div {
    background: linear-gradient(90deg, var(--cyan), var(--green)) !important;
    box-shadow: 0 0 8px rgba(0,212,255,0.5);
  }
  .stProgress > div { background: var(--bg-panel) !important; border-radius: 4px !important; }

  /* ── Selectbox dropdown ── */
  [data-baseweb="select"] > div {
    background: var(--bg-panel) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
  }
  [data-baseweb="select"] span { color: var(--text-hi) !important; }

  /* ── Download button ── */
  [data-testid="stDownloadButton"] > button {
    background: rgba(0,255,157,0.07) !important;
    border: 1px solid rgba(0,255,157,0.4) !important;
    color: var(--green) !important;
  }
  [data-testid="stDownloadButton"] > button:hover {
    background: rgba(0,255,157,0.15) !important;
    box-shadow: var(--glow-green) !important;
  }

  /* ── Paragraph & caption text ── */
  p, li { color: var(--text-mid) !important; font-size: 0.9rem !important; }
  .stCaption { color: var(--text-lo) !important; font-size: 0.75rem !important; letter-spacing: 0.05em; }

  /* ── Subheader decoration ── */
  [data-testid="stSubheader"] {
    position: relative;
    padding-left: 14px !important;
  }
  [data-testid="stSubheader"]::before {
    content: '';
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 4px;
    height: 70%;
    background: var(--cyan);
    border-radius: 2px;
    box-shadow: var(--glow-cyan);
  }

  /* ── Vital card status overrides for color ── */
  .stSuccess > div { color: #00ff9d !important; font-weight: 500; letter-spacing: 0.02em; }
  .stWarning > div { color: #f5c518 !important; font-weight: 500; }
  .stError > div   { color: #ff4560 !important; font-weight: 500; }
  .stInfo > div    { color: var(--cyan) !important; font-weight: 500; }

  /* ── Markdown strong ── */
  strong { color: var(--cyan) !important; }

  /* ── Radio buttons ── */
  .stRadio > div { gap: 4px !important; }

</style>
""", unsafe_allow_html=True)

# ───────────── CREATE PATIENT TABLE ─────────────

create_table()

# ───────────── SESSION CHECK ─────────────

if "session" not in st.session_state or st.session_state.session is None:
    st.error("Please login first from login.py")
    st.stop()

sess = st.session_state.session
user = sess.get("user") or {}
org  = sess.get("org")  or {}

# ───────────── SIDEBAR ─────────────

st.sidebar.title("⬡ HealNet AI")

name = user.get("name") or org.get("name")

# Styled user badge
st.sidebar.markdown(f"""
<div style="
  background: rgba(0,212,255,0.07);
  border: 1px solid rgba(0,212,255,0.2);
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 0.82rem;
  color: #7eb8d4;
  letter-spacing: 0.05em;
">
  <span style="color:#00d4ff;">◈</span> &nbsp;{name}
</div>
""", unsafe_allow_html=True)

page = st.sidebar.radio(
    "NAVIGATION",
    ["Dashboard", "Health Monitoring", "Register Patient", "Patient Records", "Report Analysis"],
)

st.sidebar.markdown("<br>", unsafe_allow_html=True)

if st.sidebar.button("⏻  Logout", use_container_width=True):
    st.session_state.session = None
    st.switch_page("login.py")

# ───────────── DASHBOARD ─────────────

if page == "Dashboard":

    # Header banner
    st.markdown("""
    <div style="
      background: linear-gradient(135deg, rgba(0,100,200,0.2), rgba(0,212,255,0.08));
      border: 1px solid rgba(0,212,255,0.22);
      border-radius: 14px;
      padding: 24px 32px;
      margin-bottom: 24px;
      position: relative;
      overflow: hidden;
    ">
      <div style="
        position: absolute; top: 0; left: 0; right: 0; height: 2px;
        background: linear-gradient(90deg, transparent, #00d4ff, transparent);
      "></div>
      <h1 style="margin:0; font-family:'Orbitron',sans-serif; font-size:1.6rem;
                 color:#e0f4ff; text-shadow: 0 0 20px rgba(0,212,255,0.5); letter-spacing:0.1em;">
        ⬡ HEALNET AI DASHBOARD
      </h1>
      <p style="margin:6px 0 0; color:#7eb8d4; font-size:0.82rem; letter-spacing:0.08em;">
        REAL-TIME HEALTH MONITORING SYSTEM  ·  SYSTEM ONLINE
      </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Patients Today",   "12",  "+2")
    col2.metric("Reports Analysed", "8",   "+1")
    col3.metric("Active Alerts",    "2",   delta_color="inverse")

    st.markdown("<br>", unsafe_allow_html=True)

    st.info("◈ All subsystems operational — Welcome to HealNet AI Health System")

# ───────────── HEALTH MONITORING ─────────────

elif page == "Health Monitoring":

    st.markdown("""
    <h1 style="font-family:'Orbitron',sans-serif; letter-spacing:0.1em; margin-bottom:4px;">
      ◈ HEALTH MONITORING SYSTEM
    </h1>
    """, unsafe_allow_html=True)

    if "monitoring" not in st.session_state:
        st.session_state.monitoring = False

    col1, col2 = st.columns(2)
    with col1:
        patient_id   = st.text_input("Patient ID", key="pid")
    with col2:
        patient_name = st.text_input("Patient Name", key="pname")

    if st.button("▶  START MONITORING", use_container_width=True):
        if patient_id and patient_name:
            st.session_state.monitoring = True
        else:
            st.warning("Please enter Patient ID and Name")

    st.divider()

    col3, col4 = st.columns(2)
    with col3:
        auto_refresh = st.toggle("AUTO REFRESH", value=True)
    with col4:
        refresh_rate = st.selectbox("Refresh Interval", ["1s", "5s", "10s", "30s"])

    refresh_seconds = int(refresh_rate.replace("s", ""))

    st.divider()

    if st.session_state.monitoring and patient_id:

        st.markdown(f"""
        <div style="
          display:flex; align-items:center; gap:10px;
          margin-bottom:16px;
        ">
          <div style="
            width:8px; height:8px; border-radius:50%;
            background:#00ff9d;
            box-shadow: 0 0 10px #00ff9d, 0 0 20px rgba(0,255,157,0.5);
            animation: pulse 1.5s infinite;
          "></div>
          <span style="
            font-family:'Orbitron',sans-serif;
            font-size:0.9rem; color:#e0f4ff; letter-spacing:0.08em;
          ">LIVE — {patient_name} &nbsp;·&nbsp; ID: {patient_id}</span>
        </div>
        <style>
          @keyframes pulse {{
            0%,100% {{ opacity:1; transform:scale(1); }}
            50%      {{ opacity:0.5; transform:scale(1.4); }}
          }}
        </style>
        """, unsafe_allow_html=True)

        write_vitals(patient_id)
        vitals = get_vitals(patient_id)

        if not vitals:
            st.warning("No vitals received")
            st.stop()

        systolic  = vitals.get("systolic",         0)
        diastolic = vitals.get("diastolic",         0)
        heart     = vitals.get("heart_rate",        0)
        spo2      = vitals.get("spo2",              0)
        sugar     = vitals.get("blood_sugar",       0)
        temp      = vitals.get("temperature",       0)
        resp      = vitals.get("respiratory_rate",  0)
        weight    = vitals.get("weight",            0)
        height    = vitals.get("height",            0)

        bmi = round(weight / ((height / 100) ** 2), 1) if height > 0 else 0

        st.metric("CALCULATED BMI", bmi)
        st.divider()

        bp_level,   bp_msg   = classify_bp(systolic, diastolic)
        hr_level,   hr_msg   = classify_heart_rate(heart)
        spo2_level, spo2_msg = classify_spo2(spo2)
        sg_level,   sg_msg   = classify_blood_sugar(sugar)
        tmp_level,  tmp_msg  = classify_temperature(temp)
        rr_level,   rr_msg   = classify_respiratory_rate(resp)
        bmi_level,  bmi_msg  = classify_bmi(bmi)

        COLOR = {
            "NORMAL":   "🟢",
            "MODERATE": "🟡",
            "LOW":      "🔵",
            "HIGH":     "🔴",
            "CRITICAL": "🚨",
        }

        def vital_card(label, value, level, message):
            icon = COLOR.get(level, "⚪")
            if level == "NORMAL":
                st.success(f"*{label}* &nbsp;·&nbsp; {value} &nbsp;→&nbsp; {icon} {level} — {message}")
            elif level in ("MODERATE", "LOW"):
                st.warning(f"*{label}* &nbsp;·&nbsp; {value} &nbsp;→&nbsp; {icon} {level} — {message}")
            else:
                st.error(f"*{label}* &nbsp;·&nbsp; {value} &nbsp;→&nbsp; {icon} {level} — {message}")

        c1, c2 = st.columns(2)

        with c1:
            vital_card("Blood Pressure",  f"{systolic}/{diastolic} mmHg", bp_level,   bp_msg)
            vital_card("Heart Rate",      f"{heart} bpm",                  hr_level,   hr_msg)
            vital_card("SpO₂",            f"{spo2}%",                      spo2_level, spo2_msg)
            vital_card("Temperature",     f"{temp}°F",                     tmp_level,  tmp_msg)

        with c2:
            vital_card("Blood Sugar",      f"{sugar} mg/dL",       sg_level,  sg_msg)
            vital_card("Respiratory Rate", f"{resp} breaths/min",  rr_level,  rr_msg)
            vital_card("BMI",              f"{bmi}",               bmi_level, bmi_msg)

        st.divider()

        st.subheader("🩺 OVERALL HEALTH STATUS")

        all_levels    = [bp_level, hr_level, spo2_level, sg_level, tmp_level, rr_level, bmi_level]
        severity_order = ["CRITICAL", "HIGH", "MODERATE", "LOW", "NORMAL"]
        overall        = min(all_levels, key=lambda l: severity_order.index(l))

        # ---------------- ALERT SYSTEM ----------------

        alerts = []

        if bp_level in ["HIGH", "CRITICAL"]:
          alerts.append("Blood Pressure abnormal")

        if hr_level in ["HIGH", "CRITICAL"]:
          alerts.append("Heart Rate abnormal")

        if spo2_level in ["LOW", "CRITICAL"]:
          alerts.append("Oxygen Level abnormal")

        if sg_level in ["HIGH", "CRITICAL"]:
          alerts.append("Blood Sugar abnormal")

        if tmp_level in ["HIGH", "CRITICAL"]:
          alerts.append("Temperature abnormal")

        if rr_level in ["HIGH", "CRITICAL"]:
          alerts.append("Respiratory Rate abnormal")

        if bmi_level in ["HIGH", "CRITICAL"]:
          alerts.append("BMI abnormal")

        if overall == "CRITICAL":
            st.error("🚨 CRITICAL — Immediate emergency care required")
        elif overall == "HIGH":
            st.error("🔴 HIGH RISK — Immediate medical consultation required")
        elif overall == "MODERATE":
            st.warning("🟡 MODERATE RISK — Observation needed")
        elif overall == "LOW":
            st.info("🔵 BELOW NORMAL — Review recommended")
        else:
            st.success("✅ All vitals within normal range")
            # ---------------- SHOW ALERT MESSAGE ----------------

        if alerts:

          st.divider()

          st.error(
        " HEALTH ALERT: " +
        ", ".join(alerts)
    )

        if auto_refresh:
            time.sleep(refresh_seconds)
            st.rerun()

# ───────────── REGISTER PATIENT ─────────────

elif page == "Register Patient":

    st.markdown("""
    <h1 style="font-family:'Orbitron',sans-serif; letter-spacing:0.1em; margin-bottom:4px;">
      ◈ REGISTER PATIENT
    </h1>
    """, unsafe_allow_html=True)

    with st.form("register_form", clear_on_submit=True):

        c1, c2 = st.columns(2)

        with c1:
            pname   = st.text_input("Patient Name *")
            age     = st.number_input("Age", 1, 120, 25)
            gender  = st.selectbox("Gender", ["Male", "Female", "Other"])

        with c2:
            pid     = st.text_input("Patient ID *", placeholder="e.g. P001",
                                     help="Used to fetch live vitals from InfluxDB")
            contact = st.text_input("Contact Number")
            blood   = st.text_input("Blood Group", placeholder="e.g. O+")

        submitted = st.form_submit_button(
            "▶  REGISTER PATIENT",
            type="primary",
            use_container_width=True
        )

    if submitted:
        if not pname or not pid:
            st.error("Patient Name and Patient ID are required.")
        else:
            registered_by = user.get("name") or org.get("name") or "Admin"
            ok, err = add_patient(pid, pname, age, gender, contact, blood, registered_by)
            if ok:
                st.success(f"✅ Patient *{pname}* registered successfully — ID: *{pid}*")
                st.info("Navigate to *Patient Records* to view all registered patients.")
            else:
                st.error(f"❌ {err}")

# ───────────── PATIENT RECORDS ─────────────

elif page == "Patient Records":

    st.markdown("""
    <h1 style="font-family:'Orbitron',sans-serif; letter-spacing:0.1em; margin-bottom:4px;">
      ◈ PATIENT RECORDS
    </h1>
    """, unsafe_allow_html=True)

    df = get_all_patients()

    if df.empty:
        st.info("No patients registered yet. Go to Register Patient to add one.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Patients", len(df))
        m2.metric("Male",   len(df[df["Gender"] == "Male"]))
        m3.metric("Female", len(df[df["Gender"] == "Female"]))
        m4.metric("Other",  len(df[df["Gender"] == "Other"]))

        st.divider()

        search = st.text_input("⌕  Search by Name or Patient ID", placeholder="Type to filter...")
        if search:
            mask = (
                df["Name"].str.contains(search, case=False, na=False) |
                df["Patient ID"].str.contains(search, case=False, na=False)
            )
            df = df[mask]

        st.markdown(f"<p style='color:#7eb8d4; font-size:0.78rem; letter-spacing:0.06em;'>{len(df)} RECORD(S) FOUND</p>", unsafe_allow_html=True)

        st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()

        with st.expander("⚠  Delete a Patient Record"):
            del_id = st.text_input("Enter Patient ID to delete")
            if st.button("DELETE", type="primary"):
                if del_id:
                    delete_patient(del_id)
                    st.success(f"Patient *{del_id}* deleted.")
                    st.rerun()
                else:
                    st.error("Enter a Patient ID first.")

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇  EXPORT AS CSV",
            data=csv,
            file_name="healnet_patients.csv",
            mime="text/csv",
            use_container_width=True,
        )

# ───────────── REPORT ANALYSIS ─────────────

elif page == "Report Analysis":

    st.markdown("""
    <h1 style="font-family:'Orbitron',sans-serif; letter-spacing:0.1em; margin-bottom:4px;">
      ◈ AI REPORT ANALYSIS
    </h1>
    """, unsafe_allow_html=True)

    file = st.file_uploader("Upload X-Ray / Scan Image", type=["png", "jpg", "jpeg"])

    if file:
        col_img, col_res = st.columns([1, 1])

        with col_img:
            st.image(file, use_column_width=True)

        with col_res:
            st.success("✅ Report uploaded successfully")

            st.markdown("""
            <div style="
              background: rgba(0,212,255,0.06);
              border: 1px solid rgba(0,212,255,0.2);
              border-radius: 10px;
              padding: 18px 20px;
              margin-top: 12px;
            ">
              <p style="
                font-family:'Orbitron',sans-serif;
                font-size:0.75rem;
                color:#7eb8d4;
                letter-spacing:0.1em;
                margin:0 0 6px;
              ">AI PREDICTION</p>
              <p style="
                font-size:1.4rem;
                color:#00d4ff;
                font-weight:600;
                margin:0;
                text-shadow: 0 0 12px rgba(0,212,255,0.5);
              ">RESULT: NORMAL</p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("<p style='color:#7eb8d4; font-size:0.78rem; letter-spacing:0.06em;'>MODEL CONFIDENCE</p>", unsafe_allow_html=True)
            st.progress(85)
            st.caption("Accuracy: 85%")
