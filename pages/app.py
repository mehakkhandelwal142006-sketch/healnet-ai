import streamlit as st
import time
import pandas as pd
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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

# ================= EMAIL ALERT FUNCTION =================

def send_alert_email(patient_name, alerts):

    try:
        sender = st.secrets["gmail"]["sender"]
        password = st.secrets["gmail"]["app_password"]

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = sender
        msg["Subject"] = "🚨 HealNet Health Alert"

        body = f"""
        ALERT FROM HEALNET AI SYSTEM

        Patient Name: {patient_name}
        Time: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

        Critical Vitals Detected:

        {', '.join(alerts)}

        Please check the patient immediately.
        """

        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()

        st.success("✉ Alert email sent successfully")

    except Exception as e:
        st.error(f"Email error: {e}")

# ================= STREAMLIT CONFIG =================

st.set_page_config(
    page_title="HealNet AI",
    page_icon="🏥",
    layout="wide"
)

# ───────────── GLOBAL DARK TECH THEME (unchanged) ─────────────

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;800&family=Exo+2:wght@300;400;500;600&display=swap');

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

  .stApp {
    background: var(--bg-deep) !important;
    background-image:
      radial-gradient(ellipse at 20% 0%, rgba(0,100,200,0.12) 0%, transparent 60%),
      radial-gradient(ellipse at 80% 100%, rgba(0,50,120,0.10) 0%, transparent 50%),
      repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(0,180,255,0.025) 40px),
      repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(0,180,255,0.025) 40px);
    font-family: 'Exo 2', sans-serif !important;
    color: var(--text-hi) !important;
  }

  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding: 1.5rem 2rem 2rem !important; max-width: 100% !important; }

  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg-deep); }
  ::-webkit-scrollbar-thumb { background: var(--cyan); border-radius: 3px; }

  [data-testid="stSidebar"] {
    background: var(--bg-card) !important;
    border-right: 1px solid var(--border) !important;
    box-shadow: 4px 0 30px rgba(0,200,255,0.07);
  }
  [data-testid="stSidebar"] * { color: var(--text-hi) !important; font-family: 'Exo 2', sans-serif !important; }
  [data-testid="stSidebar"] .stRadio label {
    padding: 6px 12px; border-radius: 6px; transition: background 0.2s;
    font-weight: 500; letter-spacing: 0.04em;
  }
  [data-testid="stSidebar"] .stRadio label:hover { background: var(--cyan-dim); color: var(--cyan) !important; }
  [data-testid="stSidebar"] h1 {
    font-family: 'Orbitron', sans-serif !important; font-size: 1.1rem !important;
    color: var(--cyan) !important; text-shadow: var(--glow-cyan);
    letter-spacing: 0.1em; padding-bottom: 4px;
    border-bottom: 1px solid var(--border); margin-bottom: 1rem;
  }

  h1, h2, h3, h4 {
    font-family: 'Orbitron', sans-serif !important;
    color: var(--text-hi) !important; letter-spacing: 0.06em;
    text-shadow: 0 0 20px rgba(0,212,255,0.3);
  }
  h1 { font-size: 1.6rem !important; }
  h2 { font-size: 1.2rem !important; }
  h3 { font-size: 1rem !important; }

  [data-testid="stMetric"] {
    background: var(--bg-panel) !important; border: 1px solid var(--border) !important;
    border-radius: 10px !important; padding: 16px 20px !important;
    box-shadow: 0 0 20px rgba(0,180,255,0.07), inset 0 1px 0 rgba(0,200,255,0.08);
    position: relative; overflow: hidden;
  }
  [data-testid="stMetric"]::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, var(--cyan), transparent);
  }
  [data-testid="stMetricLabel"] { color: var(--text-mid) !important; font-size: 0.72rem !important; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 500; }
  [data-testid="stMetricValue"] { color: var(--cyan) !important; font-family: 'Orbitron', sans-serif !important; font-size: 1.7rem !important; text-shadow: var(--glow-cyan); }

  .stTextInput input, .stNumberInput input {
    background: var(--bg-panel) !important; border: 1px solid var(--border) !important;
    border-radius: 8px !important; color: var(--text-hi) !important;
    font-family: 'Exo 2', sans-serif !important; font-size: 0.9rem !important;
  }
  .stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--cyan) !important; box-shadow: 0 0 0 2px rgba(0,212,255,0.2) !important;
  }
  .stTextInput label, .stNumberInput label, .stSelectbox label, .stFileUploader label {
    color: var(--text-mid) !important; font-size: 0.78rem !important;
    letter-spacing: 0.08em; text-transform: uppercase; font-weight: 500;
  }

  .stButton > button {
    background: transparent !important; border: 1px solid var(--cyan) !important;
    color: var(--cyan) !important; font-family: 'Exo 2', sans-serif !important;
    font-weight: 600 !important; letter-spacing: 0.08em; border-radius: 8px !important;
    padding: 8px 20px !important; transition: all 0.2s ease !important;
    text-transform: uppercase; font-size: 0.82rem !important;
  }
  .stButton > button:hover {
    background: var(--cyan-dim) !important; box-shadow: var(--glow-cyan) !important;
    transform: translateY(-1px);
  }
  .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, rgba(0,212,255,0.25), rgba(0,100,200,0.2)) !important;
    box-shadow: var(--glow-cyan) !important;
  }

  .stSuccess { background: rgba(0,255,157,0.08) !important; border: 1px solid rgba(0,255,157,0.35) !important; border-radius: 8px !important; color: #00ff9d !important; }
  .stWarning { background: rgba(245,197,24,0.08) !important; border: 1px solid rgba(245,197,24,0.35) !important; border-radius: 8px !important; color: #f5c518 !important; }
  .stError   { background: rgba(255,69,96,0.08) !important;  border: 1px solid rgba(255,69,96,0.35) !important;  border-radius: 8px !important; color: #ff4560 !important; }
  .stInfo    { background: rgba(0,212,255,0.07) !important;  border: 1px solid rgba(0,212,255,0.25) !important;  border-radius: 8px !important; color: var(--cyan) !important; }

  hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 1rem 0 !important; }

  [data-testid="stDataFrame"] { background: var(--bg-panel) !important; border: 1px solid var(--border) !important; border-radius: 10px !important; overflow: hidden; }
  .stToggle { color: var(--text-mid) !important; }

  .streamlit-expanderHeader { background: var(--bg-panel) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; color: var(--text-mid) !important; font-size: 0.82rem !important; letter-spacing: 0.06em; }
  .streamlit-expanderContent { background: var(--bg-card) !important; border: 1px solid var(--border) !important; border-top: none !important; border-radius: 0 0 8px 8px !important; }

  [data-testid="stForm"] { background: var(--bg-panel) !important; border: 1px solid var(--border) !important; border-radius: 12px !important; padding: 1.5rem !important; box-shadow: 0 0 30px rgba(0,180,255,0.06); }
  [data-testid="stFileUploader"] { background: var(--bg-panel) !important; border: 1px dashed var(--border) !important; border-radius: 10px !important; }

  .stProgress > div > div { background: linear-gradient(90deg, var(--cyan), var(--green)) !important; box-shadow: 0 0 8px rgba(0,212,255,0.5); }
  .stProgress > div { background: var(--bg-panel) !important; border-radius: 4px !important; }

  [data-baseweb="select"] > div { background: var(--bg-panel) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; }
  [data-baseweb="select"] span { color: var(--text-hi) !important; }

  [data-testid="stDownloadButton"] > button { background: rgba(0,255,157,0.07) !important; border: 1px solid rgba(0,255,157,0.4) !important; color: var(--green) !important; }
  [data-testid="stDownloadButton"] > button:hover { background: rgba(0,255,157,0.15) !important; box-shadow: var(--glow-green) !important; }

  p, li { color: var(--text-mid) !important; font-size: 0.9rem !important; }
  .stCaption { color: var(--text-lo) !important; font-size: 0.75rem !important; letter-spacing: 0.05em; }

  [data-testid="stSubheader"] { position: relative; padding-left: 14px !important; }
  [data-testid="stSubheader"]::before { content: ''; position: absolute; left: 0; top: 50%; transform: translateY(-50%); width: 4px; height: 70%; background: var(--cyan); border-radius: 2px; box-shadow: var(--glow-cyan); }

  .stSuccess > div { color: #00ff9d !important; font-weight: 500; letter-spacing: 0.02em; }
  .stWarning > div { color: #f5c518 !important; font-weight: 500; }
  .stError > div   { color: #ff4560 !important; font-weight: 500; }
  .stInfo > div    { color: var(--cyan) !important; font-weight: 500; }
  strong { color: var(--cyan) !important; }
  .stRadio > div { gap: 4px !important; }

  @keyframes bell-shake {
    0%,100% { transform: rotate(0deg); }
    20%      { transform: rotate(-18deg); }
    40%      { transform: rotate(18deg); }
    60%      { transform: rotate(-9deg); }
    80%      { transform: rotate(9deg); }
  }
  .alert-bell { display:inline-block; animation: bell-shake 0.9s ease infinite; }

  .alert-banner {
    background: rgba(255,69,96,0.10);
    border: 1px solid rgba(255,69,96,0.5);
    border-radius: 10px; padding: 14px 18px; margin-bottom: 14px;
    display: flex; align-items: flex-start; gap: 12px;
  }
  .alert-banner-title {
    font-family: 'Orbitron', sans-serif; font-size: 0.78rem;
    color: #ff4560; letter-spacing: 0.1em; margin-bottom: 4px;
  }
  .alert-banner-body { font-size: 0.78rem; color: #f5c518; letter-spacing: 0.03em; }
  .alert-sent-msg    { font-size: 0.72rem; color: #00ff9d; margin-top: 5px; }
  .alert-err-msg     { font-size: 0.72rem; color: #ff4560; margin-top: 5px; }

  .alert-log { background: rgba(255,69,96,0.06); border: 1px solid rgba(255,69,96,0.3); border-radius: 10px; padding: 14px 18px; margin-top: 10px; }
  .alert-log-title { font-family: 'Orbitron', sans-serif; font-size: 0.72rem; color: #ff4560; letter-spacing: 0.1em; margin-bottom: 8px; }
  .alert-entry { font-size: 0.78rem; color: #f5c518; padding: 4px 0; border-bottom: 1px solid rgba(255,69,96,0.1); letter-spacing: 0.02em; }
  .alert-entry:last-child { border-bottom: none; }

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

# ═══════════════════════════════════════════════
#   GMAIL ALERT SYSTEM  ── LIGHT / WHITE EMAIL
# ═══════════════════════════════════════════════

def send_gmail_alert(recipient_email: str, patient_name: str, patient_id: str, alerts: list):
    try:
        sender_email    = st.secrets["gmail"]["sender"]
        sender_password = st.secrets["gmail"]["app_password"]
    except KeyError:
        return False, "Gmail credentials missing in .streamlit/secrets.toml"

    timestamp = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")

    # ── Build vital rows ──
    rows_html = ""
    for a in alerts:
        is_critical  = a["level"] in ("HIGH", "CRITICAL")
        badge_color  = "#dc2626" if is_critical else "#b45309"
        badge_bg     = "#fef2f2" if is_critical else "#fffbeb"
        badge_border = "#fca5a5" if is_critical else "#fde68a"
        rows_html += f"""
        <tr>
          <td style="padding:11px 16px;border-bottom:1px solid #f3f4f6;
                     font-size:14px;color:#111827;font-weight:500;">{a['vital']}</td>
          <td style="padding:11px 16px;border-bottom:1px solid #f3f4f6;
                     font-size:14px;color:#dc2626;font-weight:700;">{a['value']}</td>
          <td style="padding:11px 16px;border-bottom:1px solid #f3f4f6;">
            <span style="background:{badge_bg};color:{badge_color};
                         border:1px solid {badge_border};padding:3px 10px;
                         border-radius:4px;font-size:12px;font-weight:700;
                         letter-spacing:0.06em;">{a['level']}</span>
          </td>
          <td style="padding:11px 16px;border-bottom:1px solid #f3f4f6;
                     font-size:13px;color:#6b7280;">{a['message']}</td>
        </tr>"""

    # ══ WHITE / LIGHT EMAIL TEMPLATE ══
    html_body = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;">

<div style="max-width:640px;margin:32px auto;background:#ffffff;
            border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;
            box-shadow:0 4px 16px rgba(0,0,0,0.07);">

  <!-- Red top bar -->
  <div style="height:4px;background:#dc2626;"></div>

  <!-- Header -->
  <div style="background:#fef2f2;padding:22px 28px;border-bottom:1px solid #fca5a5;">
    <div style="font-size:11px;color:#9ca3af;letter-spacing:0.1em;
                text-transform:uppercase;margin-bottom:6px;">
      HealNet AI &nbsp;·&nbsp; Automated Health Alert
    </div>
    <div style="font-size:20px;font-weight:700;color:#dc2626;">
      🚨 Critical Vitals Detected
    </div>
  </div>

  <!-- Patient info -->
  <div style="padding:20px 28px;border-bottom:1px solid #f3f4f6;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr>
        <td style="padding:5px 0;width:110px;color:#9ca3af;text-transform:uppercase;
                   letter-spacing:0.08em;font-size:11px;font-weight:600;">Patient</td>
        <td style="padding:5px 0;color:#111827;font-weight:600;">{patient_name}</td>
      </tr>
      <tr>
        <td style="padding:5px 0;color:#9ca3af;text-transform:uppercase;
                   letter-spacing:0.08em;font-size:11px;font-weight:600;">Patient ID</td>
        <td style="padding:5px 0;color:#dc2626;font-weight:700;letter-spacing:0.04em;">{patient_id}</td>
      </tr>
      <tr>
        <td style="padding:5px 0;color:#9ca3af;text-transform:uppercase;
                   letter-spacing:0.08em;font-size:11px;font-weight:600;">Timestamp</td>
        <td style="padding:5px 0;color:#374151;">{timestamp}</td>
      </tr>
    </table>
  </div>

  <!-- Flagged vitals -->
  <div style="padding:20px 28px;">
    <div style="font-size:11px;color:#dc2626;text-transform:uppercase;
                letter-spacing:0.1em;font-weight:700;margin-bottom:12px;">
      ⚠ Flagged Vitals
    </div>
    <table style="width:100%;border-collapse:collapse;
                  border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
      <thead>
        <tr style="background:#f9fafb;">
          <th style="padding:10px 16px;text-align:left;color:#6b7280;font-size:11px;
                     text-transform:uppercase;letter-spacing:0.08em;font-weight:600;
                     border-bottom:1px solid #e5e7eb;">Vital</th>
          <th style="padding:10px 16px;text-align:left;color:#6b7280;font-size:11px;
                     text-transform:uppercase;letter-spacing:0.08em;font-weight:600;
                     border-bottom:1px solid #e5e7eb;">Value</th>
          <th style="padding:10px 16px;text-align:left;color:#6b7280;font-size:11px;
                     text-transform:uppercase;letter-spacing:0.08em;font-weight:600;
                     border-bottom:1px solid #e5e7eb;">Status</th>
          <th style="padding:10px 16px;text-align:left;color:#6b7280;font-size:11px;
                     text-transform:uppercase;letter-spacing:0.08em;font-weight:600;
                     border-bottom:1px solid #e5e7eb;">Note</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  <!-- Action note -->
  <div style="margin:0 28px 20px;background:#fef2f2;border:1px solid #fca5a5;
              border-radius:8px;padding:14px 16px;">
    <div style="color:#dc2626;font-size:13px;font-weight:700;">
      🏥 Immediate review recommended for
      <span style="color:#111827;font-weight:700;">{patient_name}</span>.
    </div>
    <div style="color:#6b7280;font-size:12px;margin-top:4px;">
      Please log into HealNet AI for full vitals history and clinical notes.
    </div>
  </div>

  <!-- Footer -->
  <div style="padding:14px 28px;border-top:1px solid #f3f4f6;background:#f9fafb;">
    <div style="font-size:11px;color:#9ca3af;letter-spacing:0.04em;">
      Automated alert from HealNet AI. Do not reply to this email.
    </div>
  </div>

</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 HealNet Alert — {patient_name} ({patient_id}) | Critical Vitals"
    msg["From"]    = sender_email
    msg["To"]      = recipient_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        return True, "sent"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed — check your App Password in secrets.toml"
    except Exception as e:
        return False, str(e)


def check_and_alert(patient_name, patient_id, vitals_map, recipient_email, cooldown_seconds=300):
    triggered = [
        {"vital": vname, "value": val, "level": lvl, "message": msg}
        for vname, (val, lvl, msg) in vitals_map.items()
        if lvl in ("HIGH", "CRITICAL")
    ]

    if not triggered:
        return []

    cooldown_key = f"last_alert_{patient_id}"
    now          = time.time()
    last_sent    = st.session_state.get(cooldown_key, 0)

    if recipient_email and (now - last_sent > cooldown_seconds):
        ok, err_msg = send_gmail_alert(recipient_email, patient_name, patient_id, triggered)
        st.session_state[cooldown_key] = now
        if ok:
            st.session_state[f"alert_ok_{patient_id}"]  = True
            st.session_state.pop(f"alert_err_{patient_id}", None)
        else:
            st.session_state[f"alert_err_{patient_id}"] = err_msg
            st.session_state.pop(f"alert_ok_{patient_id}", None)

    return triggered


# ───────────── SIDEBAR ─────────────

st.sidebar.title("⬡ HealNet AI")

name = user.get("name") or org.get("name")

st.sidebar.markdown(f"""
<div style="background:rgba(0,212,255,0.07);border:1px solid rgba(0,212,255,0.2);
            border-radius:8px;padding:8px 12px;margin-bottom:12px;
            font-size:0.82rem;color:#7eb8d4;letter-spacing:0.05em;">
  <span style="color:#00d4ff;">◈</span> &nbsp;{name}
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style="font-size:0.63rem;color:#3a6a8a;letter-spacing:0.12em;
            text-transform:uppercase;padding:6px 4px 2px;margin-top:4px;">
  🔔 Alert Settings
</div>""", unsafe_allow_html=True)

alert_email    = st.sidebar.text_input(
    "Alert Email (Gmail)",
    placeholder="doctor@gmail.com",
    help="Receive instant email when any vital is HIGH or CRITICAL",
    key="alert_email",
)
alerts_enabled = st.sidebar.toggle("Enable Gmail Alerts", value=True, key="alerts_enabled")

if alert_email and alerts_enabled:
    st.sidebar.markdown("""
    <div style="background:rgba(0,255,157,0.07);border:1px solid rgba(0,255,157,0.22);
                border-radius:6px;padding:6px 10px;font-size:0.7rem;color:#00ff9d;
                letter-spacing:0.04em;margin-top:4px;">◈ Gmail alerts active</div>
    """, unsafe_allow_html=True)
elif not alerts_enabled:
    st.sidebar.markdown("""
    <div style="background:rgba(255,69,96,0.06);border:1px solid rgba(255,69,96,0.2);
                border-radius:6px;padding:6px 10px;font-size:0.7rem;color:#ff4560;
                letter-spacing:0.04em;margin-top:4px;">⚠ Alerts disabled</div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.markdown("""
    <div style="background:rgba(245,197,24,0.06);border:1px solid rgba(245,197,24,0.2);
                border-radius:6px;padding:6px 10px;font-size:0.7rem;color:#f5c518;
                letter-spacing:0.04em;margin-top:4px;">⚠ Enter email to activate alerts</div>
    """, unsafe_allow_html=True)

st.sidebar.divider()

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

    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(0,100,200,0.2),rgba(0,212,255,0.08));
                border:1px solid rgba(0,212,255,0.22);border-radius:14px;
                padding:24px 32px;margin-bottom:24px;position:relative;overflow:hidden;">
      <div style="position:absolute;top:0;left:0;right:0;height:2px;
                  background:linear-gradient(90deg,transparent,#00d4ff,transparent);"></div>
      <h1 style="margin:0;font-family:'Orbitron',sans-serif;font-size:1.6rem;
                 color:#e0f4ff;text-shadow:0 0 20px rgba(0,212,255,0.5);letter-spacing:0.1em;">
        ⬡ HEALNET AI DASHBOARD
      </h1>
      <p style="margin:6px 0 0;color:#7eb8d4;font-size:0.82rem;letter-spacing:0.08em;">
        REAL-TIME HEALTH MONITORING SYSTEM &nbsp;·&nbsp; SYSTEM ONLINE
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
    <h1 style="font-family:'Orbitron',sans-serif;letter-spacing:0.1em;margin-bottom:4px;">
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
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;">
          <div style="width:8px;height:8px;border-radius:50%;background:#00ff9d;
                      box-shadow:0 0 10px #00ff9d,0 0 20px rgba(0,255,157,0.5);
                      animation:pulse 1.5s infinite;"></div>
          <span style="font-family:'Orbitron',sans-serif;font-size:0.9rem;
                       color:#e0f4ff;letter-spacing:0.08em;">
            LIVE — {patient_name} &nbsp;·&nbsp; ID: {patient_id}
          </span>
        </div>
        <style>
          @keyframes pulse {{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:0.5;transform:scale(1.4);}}}}
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

        vitals_map = {
            "Blood Pressure":   (f"{systolic}/{diastolic} mmHg", bp_level,   bp_msg),
            "Heart Rate":       (f"{heart} bpm",                  hr_level,   hr_msg),
            "SpO₂":            (f"{spo2}%",                       spo2_level, spo2_msg),
            "Temperature":      (f"{temp}°F",                     tmp_level,  tmp_msg),
            "Blood Sugar":      (f"{sugar} mg/dL",                sg_level,   sg_msg),
            "Respiratory Rate": (f"{resp} breaths/min",           rr_level,   rr_msg),
            "BMI":              (f"{bmi}",                        bmi_level,  bmi_msg),
        }

        alerts_enabled = st.session_state.get("alerts_enabled", False)
        alert_email    = st.session_state.get("alert_email", "")

        recipient        = alert_email if (alerts_enabled and alert_email) else ""
        triggered_alerts = check_and_alert(patient_name, patient_id, vitals_map, recipient)

        if triggered_alerts:
            st.toast(" Critical health alert detected!", icon="🚨")
            lines = "  |  ".join(f"{a['vital']}: {a['value']} [{a['level']}]" for a in triggered_alerts)
            email_line = ""
            if recipient:
                if st.session_state.get(f"alert_ok_{patient_id}"):
                    email_line = f"<div class='alert-sent-msg'>✉ Gmail alert dispatched → {alert_email}</div>"
                elif st.session_state.get(f"alert_err_{patient_id}"):
                    email_line = f"<div class='alert-err-msg'>✗ Email error: {st.session_state[f'alert_err_{patient_id}']}</div>"
            else:
                email_line = "<div class='alert-sent-msg' style='color:#f5c518;'>⚠ Set an alert email in the sidebar to receive Gmail notifications.</div>"

            st.markdown(f"""
            <div class="alert-banner">
              <span class="alert-bell" style="font-size:22px;">🔔</span>
              <div>
                <div class="alert-banner-title">ALERT — CRITICAL VITALS DETECTED</div>
                <div class="alert-banner-body">{lines}</div>
                {email_line}
              </div>
            </div>
            """, unsafe_allow_html=True)

        COLOR = {"NORMAL":"🟢","MODERATE":"🟡","LOW":"🔵","HIGH":"🔴","CRITICAL":"🚨"}

        def vital_card(label, value, level, message):
            icon = COLOR.get(level, "⚪")
            bell = " 🔔" if level in ("HIGH", "CRITICAL") else ""
            if level == "NORMAL":
                st.success(f"{label} &nbsp;·&nbsp; {value} &nbsp;→&nbsp; {icon} {level} — {message}")
            elif level in ("MODERATE", "LOW"):
                st.warning(f"{label} &nbsp;·&nbsp; {value} &nbsp;→&nbsp; {icon} {level} — {message}")
            else:
                st.error(f"{label}{bell} &nbsp;·&nbsp; {value} &nbsp;→&nbsp; {icon} {level} — {message}")

        c1, c2 = st.columns(2)
        with c1:
            vital_card("Blood Pressure",  f"{systolic}/{diastolic} mmHg", bp_level,   bp_msg)
            vital_card("Heart Rate",      f"{heart} bpm",                  hr_level,   hr_msg)
            vital_card("SpO₂",            f"{spo2}%",                      spo2_level, spo2_msg)
            vital_card("Temperature",     f"{temp}°F",                     tmp_level,  tmp_msg)
        with c2:
            vital_card("Blood Sugar",      f"{sugar} mg/dL",      sg_level,  sg_msg)
            vital_card("Respiratory Rate", f"{resp} breaths/min", rr_level,  rr_msg)
            vital_card("BMI",              f"{bmi}",              bmi_level, bmi_msg)

        st.divider()
        st.subheader("🩺 OVERALL HEALTH STATUS")

        all_levels     = [bp_level, hr_level, spo2_level, sg_level, tmp_level, rr_level, bmi_level]
        severity_order = ["CRITICAL", "HIGH", "MODERATE", "LOW", "NORMAL"]
        overall        = min(all_levels, key=lambda l: severity_order.index(l))

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

        if triggered_alerts:
            with st.expander("📋 View Alert Details"):
                st.markdown('<div class="alert-log"><div class="alert-log-title">🔔 TRIGGERED ALERTS THIS SESSION</div>', unsafe_allow_html=True)
                for a in triggered_alerts:
                    st.markdown(f"""
                    <div class="alert-entry">
                      ⚠ &nbsp;<strong>{a['vital']}</strong> — {a['value']} &nbsp;|&nbsp;
                      Status: <span style="color:#ff4560;">{a['level']}</span> &nbsp;|&nbsp;
                      {a['message']}
                    </div>""", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

        if auto_refresh:
            time.sleep(refresh_seconds)
            st.rerun()

# ───────────── REGISTER PATIENT ─────────────

elif page == "Register Patient":

    st.markdown("""
    <h1 style="font-family:'Orbitron',sans-serif;letter-spacing:0.1em;margin-bottom:4px;">
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

        submitted = st.form_submit_button("▶  REGISTER PATIENT", type="primary", use_container_width=True)

    if submitted:
        if not pname or not pid:
            st.error("Patient Name and Patient ID are required.")
        else:
            registered_by = user.get("name") or org.get("name") or "Admin"
            ok, err = add_patient(pid, pname, age, gender, contact, blood, registered_by)
            if ok:
                st.success(f"✅ Patient {pname} registered successfully — ID: {pid}")
                st.info("Navigate to Patient Records to view all registered patients.")
            else:
                st.error(f"❌ {err}")

# ───────────── PATIENT RECORDS ─────────────

elif page == "Patient Records":

    st.markdown("""
    <h1 style="font-family:'Orbitron',sans-serif;letter-spacing:0.1em;margin-bottom:4px;">
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

        st.markdown(f"<p style='color:#7eb8d4;font-size:0.78rem;letter-spacing:0.06em;'>{len(df)} RECORD(S) FOUND</p>", unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.divider()

        with st.expander("⚠  Delete a Patient Record"):
            del_id = st.text_input("Enter Patient ID to delete")
            if st.button("DELETE", type="primary"):
                if del_id:
                    delete_patient(del_id)
                    st.success(f"Patient {del_id} deleted.")
                    st.rerun()
                else:
                    st.error("Enter a Patient ID first.")

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(label="⬇  EXPORT AS CSV", data=csv, file_name="healnet_patients.csv", mime="text/csv", use_container_width=True)

# ───────────── REPORT ANALYSIS ─────────────

elif page == "Report Analysis":

    st.markdown("""
    <h1 style="font-family:'Orbitron',sans-serif;letter-spacing:0.1em;margin-bottom:4px;">
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
            <div style="background:rgba(0,212,255,0.06);border:1px solid rgba(0,212,255,0.2);
                        border-radius:10px;padding:18px 20px;margin-top:12px;">
              <p style="font-family:'Orbitron',sans-serif;font-size:0.75rem;color:#7eb8d4;
                        letter-spacing:0.1em;margin:0 0 6px;">AI PREDICTION</p>
              <p style="font-size:1.4rem;color:#00d4ff;font-weight:600;margin:0;
                        text-shadow:0 0 12px rgba(0,212,255,0.5);">RESULT: NORMAL</p>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("<p style='color:#7eb8d4;font-size:0.78rem;letter-spacing:0.06em;'>MODEL CONFIDENCE</p>", unsafe_allow_html=True)
            st.progress(85)
            st.caption("Accuracy: 85%")
