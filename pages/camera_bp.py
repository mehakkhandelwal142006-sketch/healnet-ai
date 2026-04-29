"""
camera_bp.py  —  HealNet AI
────────────────────────────────────────────────────────────────
Blood Pressure Log, Trend Tracker & Lifestyle Advisor.

What this module does (correctly):
  • User enters BP readings from their physical cuff manually
  • Readings are tagged with posture / meal context
  • Session trend chart shows systolic & diastolic over time
  • Each reading is classified (Normal / Elevated / Stage 1 / Stage 2 / Crisis)
  • Lifestyle advice is shown based on the reading level
  • Export session readings as CSV for doctor consultations

What it does NOT do:
  • It does NOT measure BP through the camera.
    A standard smartphone camera cannot measure blood pressure.
    Camera is used only for heart rate (see Camera Vitals page).

Usage (in app.py):
    from camera_bp import render_camera_bp_page
    render_camera_bp_page()

Requirements: No extra pip installs needed.
"""

import streamlit as st
import datetime
import csv
import io


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS  (same pattern as camera_vitals.py)
# ─────────────────────────────────────────────────────────────────────────────

def _sub_label(text: str):
    st.html(f'<div class="sub-label">{text}</div>')


def _info_card(title: str, body: str, color: str = "#3399ff"):
    st.html(f"""
    <div style="background:rgba(255,255,255,0.55);border:1px solid {color}33;
                border-left:4px solid {color};border-radius:12px;
                padding:14px 18px;margin-bottom:10px;
                backdrop-filter:blur(10px);">
      <div style="font-size:.80rem;font-weight:700;color:{color};
                  text-transform:uppercase;letter-spacing:.10em;margin-bottom:6px;">{title}</div>
      <div style="font-size:.84rem;color:#1e2d3d;line-height:1.65;">{body}</div>
    </div>""")


# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

SESSION_KEY = "bp_log_readings"

POSTURE_OPTIONS = [
    "Sitting (resting)",
    "Lying down",
    "Standing",
    "Before meal",
    "After meal",
    "After exercise",
    "Morning (just woke up)",
    "After medication",
]

# Classification thresholds (AHA 2017 guidelines)
BP_LEVELS = [
    ("Hypertensive Crisis", "#e74c3c", "rgba(231,76,60,0.10)",  180, 120),
    ("Stage 2 Hypertension","#e67e22", "rgba(230,126,34,0.10)", 140,  90),
    ("Stage 1 Hypertension","#f5a623", "rgba(245,166,35,0.10)", 130,  80),
    ("Elevated",            "#3b9edb", "rgba(59,158,219,0.10)", 120,  80),
    ("Normal",              "#00c896", "rgba(0,200,150,0.10)",    0,   0),
]

LIFESTYLE_ADVICE = {
    "Normal": [
        "✅ Keep up your current healthy habits.",
        "🧂 Maintain a low-sodium diet (less than 2,300 mg/day).",
        "🏃 Continue regular physical activity (150 min/week).",
        "😴 Aim for 7–8 hours of quality sleep.",
        "📅 Check your BP at least once a year.",
    ],
    "Elevated": [
        "🧂 Reduce sodium intake — avoid processed and packaged foods.",
        "🏃 Increase physical activity to at least 150 min/week.",
        "🧘 Try stress-reduction techniques like deep breathing or meditation.",
        "🚭 Avoid smoking and limit alcohol consumption.",
        "📅 Monitor BP every 3–6 months and consult your doctor.",
    ],
    "Stage 1 Hypertension": [
        "🩺 Consult your doctor — lifestyle changes or medication may be needed.",
        "🧂 Strictly limit sodium to under 1,500 mg/day.",
        "⚖️ If overweight, losing even 5 kg can significantly lower BP.",
        "🏃 30 minutes of moderate exercise most days of the week.",
        "🚫 Avoid alcohol, caffeine, and smoking.",
        "📅 Monitor BP weekly and keep a log to share with your doctor.",
    ],
    "Stage 2 Hypertension": [
        "🚨 See a doctor soon — medication is likely required.",
        "💊 Take prescribed medications consistently — do not skip doses.",
        "🧂 Eliminate added salt from your diet completely.",
        "🏥 Monitor BP daily and note any symptoms like headaches or dizziness.",
        "🚫 Avoid physical exertion until BP is controlled.",
        "📅 Follow up with your healthcare provider within 1 week.",
    ],
    "Hypertensive Crisis": [
        "🆘 SEEK EMERGENCY MEDICAL CARE IMMEDIATELY.",
        "📞 Call emergency services or go to the nearest hospital.",
        "🛑 Do not drive yourself — ask someone to take you.",
        "💊 If prescribed, take your emergency BP medication now.",
        "🛏️ Lie down calmly and avoid any physical or emotional stress.",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
#  CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def classify_bp(sys_val: int, dia_val: int):
    """Return (level_name, color, bg_color) for a BP reading."""
    if sys_val >= 180 or dia_val >= 120:
        return "Hypertensive Crisis", "#e74c3c", "rgba(231,76,60,0.10)"
    if sys_val >= 140 or dia_val >= 90:
        return "Stage 2 Hypertension", "#e67e22", "rgba(230,126,34,0.10)"
    if sys_val >= 130 or dia_val >= 80:
        return "Stage 1 Hypertension", "#f5a623", "rgba(245,166,35,0.10)"
    if sys_val >= 120:
        return "Elevated", "#3b9edb", "rgba(59,158,219,0.10)"
    if sys_val < 90 or dia_val < 60:
        return "Low (Hypotension)", "#9b59b6", "rgba(155,89,182,0.10)"
    return "Normal", "#00c896", "rgba(0,200,150,0.10)"


# ─────────────────────────────────────────────────────────────────────────────
#  SESSION STORAGE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_readings():
    return st.session_state.get(SESSION_KEY, [])


def _save_reading(sys_val, dia_val, hr_val, posture, note):
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = []
    level, color, bg = classify_bp(sys_val, dia_val)
    entry = {
        "timestamp":  datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "systolic":   sys_val,
        "diastolic":  dia_val,
        "heart_rate": hr_val,
        "posture":    posture,
        "level":      level,
        "color":      color,
        "bg":         bg,
        "note":       note,
    }
    st.session_state[SESSION_KEY].append(entry)
    # Keep last 50 readings
    if len(st.session_state[SESSION_KEY]) > 50:
        st.session_state[SESSION_KEY] = st.session_state[SESSION_KEY][-50:]


def _readings_to_csv():
    readings = _get_readings()
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["timestamp", "systolic", "diastolic",
                    "heart_rate", "posture", "level", "note"],
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(readings)
    return buf.getvalue().encode()


# ─────────────────────────────────────────────────────────────────────────────
#  UI COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────

def _render_reading_card(r: dict):
    """Render a single BP reading as a styled card."""
    fg  = r["color"]
    bg  = r["bg"]
    hr_str = f"❤️ {r['heart_rate']} bpm" if r.get("heart_rate") else ""
    note_str = f"<div style='font-size:.74rem;color:#7a9ab8;margin-top:5px;'>📝 {r['note']}</div>" \
               if r.get("note") else ""

    st.html(f"""
    <div style="background:{bg};border:1px solid {fg}44;border-left:4px solid {fg};
                border-radius:12px;padding:14px 18px;margin-bottom:10px;">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
        <div>
          <span style="font-size:1.7rem;font-weight:800;color:{fg};
                       font-family:'Rajdhani',sans-serif;">
            {r['systolic']}/{r['diastolic']}
          </span>
          <span style="font-size:.76rem;color:#7a9ab8;margin-left:5px;">mmHg</span>
          &nbsp;
          <span style="background:{bg};color:{fg};border:1px solid {fg}55;
                       padding:2px 10px;border-radius:20px;font-size:.72rem;font-weight:700;">
            {r['level']}
          </span>
        </div>
        <div style="font-size:.74rem;color:#7a9ab8;text-align:right;">
          {hr_str}<br>
          🕐 {r['timestamp']}<br>
          🪑 {r['posture']}
        </div>
      </div>
      {note_str}
    </div>
    """)


def _render_trend_chart(readings: list):
    """
    Render BP trend chart with AHA threshold lines using Plotly.
    Shows:
      - Systolic readings line  (red)
      - Diastolic readings line (blue)
      - Horizontal threshold lines for every BP category
      - Shaded zones between thresholds so the danger bands are visible
    """
    if len(readings) < 1:
        return

    import pandas as pd
    import plotly.graph_objects as go

    df = pd.DataFrame(readings)[["timestamp", "systolic", "diastolic"]].copy()
    labels = df["timestamp"].tolist()
    n      = len(labels)

    fig = go.Figure()

    # ── Shaded zone bands (drawn first so lines sit on top) ──────────────
    # Each band: (y_bottom, y_top, fill_color, label)
    zones = [
        (0,   90,  "rgba(155,89,182,0.08)",  "Low"),
        (90,  120, "rgba(0,200,150,0.07)",   "Normal"),
        (120, 130, "rgba(59,158,219,0.08)",  "Elevated"),
        (130, 140, "rgba(245,166,35,0.09)",  "Stage 1"),
        (140, 180, "rgba(230,126,34,0.09)",  "Stage 2"),
        (180, 220, "rgba(231,76,60,0.10)",   "Crisis"),
    ]
    for y0, y1, fill, zlabel in zones:
        fig.add_hrect(
            y0=y0, y1=y1,
            fillcolor=fill,
            line_width=0,
            annotation_text=zlabel,
            annotation_position="right",
            annotation_font=dict(size=9, color="#888"),
        )

    # ── Threshold lines ───────────────────────────────────────────────────
    thresholds = [
        (120, "#3b9edb",  "Normal / Elevated  120"),
        (130, "#f5a623",  "Elevated / Stage 1  130"),
        (140, "#e67e22",  "Stage 1 / Stage 2  140"),
        (180, "#e74c3c",  "Crisis  180"),
        (80,  "#3b9edb",  "Dia Normal  80"),
        (90,  "#f5a623",  "Dia Stage 1  90"),
    ]
    for y_val, t_color, t_label in thresholds:
        fig.add_hline(
            y=y_val,
            line_dash="dot",
            line_color=t_color,
            line_width=1.4,
            annotation_text=t_label,
            annotation_position="top left",
            annotation_font=dict(size=8, color=t_color),
        )

    # ── Systolic line ─────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=labels,
        y=df["systolic"].tolist(),
        name="Systolic",
        mode="lines+markers",
        line=dict(color="#e74c3c", width=2.5),
        marker=dict(size=7, color="#e74c3c",
                    line=dict(width=1.5, color="#fff")),
        hovertemplate="<b>Systolic</b>: %{y} mmHg<br>%{x}<extra></extra>",
    ))

    # ── Diastolic line ────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=labels,
        y=df["diastolic"].tolist(),
        name="Diastolic",
        mode="lines+markers",
        line=dict(color="#3b9edb", width=2.5),
        marker=dict(size=7, color="#3b9edb",
                    line=dict(width=1.5, color="#fff")),
        hovertemplate="<b>Diastolic</b>: %{y} mmHg<br>%{x}<extra></extra>",
    ))

    # ── Layout ────────────────────────────────────────────────────────────
    fig.update_layout(
        height=340,
        margin=dict(l=10, r=80, t=24, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,20,40,0.03)",
        font=dict(family="Segoe UI, sans-serif", size=11, color="#1a3a5c"),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left",   x=0,
            font=dict(size=11),
        ),
        xaxis=dict(
            showgrid=False,
            tickangle=-30,
            tickfont=dict(size=9),
            title="",
        ),
        yaxis=dict(
            range=[50, 225],
            gridcolor="rgba(100,160,220,0.12)",
            title="mmHg",
            titlefont=dict(size=10),
            tickfont=dict(size=9),
        ),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # ── Legend for threshold lines ─────────────────────────────────────────
    st.html("""
    <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:2px;margin-bottom:6px;">
      <span style="font-size:.70rem;color:#9b59b6;">&#9135; Low &lt;90/60</span>
      <span style="font-size:.70rem;color:#00c896;">&#9135; Normal &lt;120/80</span>
      <span style="font-size:.70rem;color:#3b9edb;">&#9135; Elevated 120–129</span>
      <span style="font-size:.70rem;color:#f5a623;">&#9135; Stage 1  130–139</span>
      <span style="font-size:.70rem;color:#e67e22;">&#9135; Stage 2  &#8805;140</span>
      <span style="font-size:.70rem;color:#e74c3c;">&#9135; Crisis   &#8805;180/120</span>
    </div>
    """)


def _render_summary_stats(readings: list):
    """Show average / latest / highest stats."""
    if not readings:
        return
    sys_vals = [r["systolic"]  for r in readings]
    dia_vals = [r["diastolic"] for r in readings]
    latest   = readings[-1]
    fg, _, _ = classify_bp(latest["systolic"], latest["diastolic"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latest",        f"{latest['systolic']}/{latest['diastolic']}")
    c2.metric("Avg Systolic",  f"{round(sum(sys_vals)/len(sys_vals))} mmHg")
    c3.metric("Avg Diastolic", f"{round(sum(dia_vals)/len(dia_vals))} mmHg")
    c4.metric("Total Readings", len(readings))


def _render_lifestyle_advice(level: str):
    """Show lifestyle advice cards for the given BP level."""
    advice_list = LIFESTYLE_ADVICE.get(level, LIFESTYLE_ADVICE["Normal"])
    _, color, bg = classify_bp(
        180 if level == "Hypertensive Crisis"
        else 140 if level == "Stage 2 Hypertension"
        else 130 if level == "Stage 1 Hypertension"
        else 120 if level == "Elevated"
        else 100,
        80
    )
    st.html(f"""
    <div style="background:{bg};border:1px solid {color}44;border-left:4px solid {color};
                border-radius:12px;padding:16px 20px;margin-bottom:12px;">
      <div style="font-size:.75rem;font-weight:700;color:{color};
                  text-transform:uppercase;letter-spacing:.12em;margin-bottom:10px;">
        Lifestyle Advice for: {level}
      </div>
      {"".join(f'<div style="font-size:.83rem;color:#1e2d3d;padding:4px 0;border-bottom:1px solid {color}18;">{a}</div>' for a in advice_list)}
    </div>
    """)


# ─────────────────────────────────────────────────────────────────────────────
#  BP REFERENCE TABLE (HTML widget — no external deps)
# ─────────────────────────────────────────────────────────────────────────────

BP_REFERENCE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: transparent; padding: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: .80rem; }
  th {
    background: rgba(0,100,160,0.10);
    color: #1a3a5c;
    font-weight: 700;
    font-size: .68rem;
    text-transform: uppercase;
    letter-spacing: .10em;
    padding: 9px 12px;
    text-align: left;
  }
  td { padding: 9px 12px; border-bottom: 1px solid rgba(100,160,220,0.12); }
  tr:last-child td { border-bottom: none; }
  .dot {
    display: inline-block;
    width: 10px; height: 10px;
    border-radius: 50%;
    margin-right: 7px;
    vertical-align: middle;
  }
</style>
</head>
<body>
<table>
  <thead>
    <tr>
      <th>Category</th>
      <th>Systolic</th>
      <th>Diastolic</th>
      <th>Action</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="dot" style="background:#00c896;"></span>Normal</td>
      <td>Less than 120</td><td>Less than 80</td>
      <td style="color:#00a07a;font-size:.74rem;">Maintain healthy habits</td>
    </tr>
    <tr>
      <td><span class="dot" style="background:#3b9edb;"></span>Elevated</td>
      <td>120–129</td><td>Less than 80</td>
      <td style="color:#1a70a0;font-size:.74rem;">Lifestyle changes advised</td>
    </tr>
    <tr>
      <td><span class="dot" style="background:#f5a623;"></span>Stage 1 Hypertension</td>
      <td>130–139</td><td>80–89</td>
      <td style="color:#b07000;font-size:.74rem;">See doctor, lifestyle changes</td>
    </tr>
    <tr>
      <td><span class="dot" style="background:#e67e22;"></span>Stage 2 Hypertension</td>
      <td>140 or higher</td><td>90 or higher</td>
      <td style="color:#a04000;font-size:.74rem;">See doctor promptly, medication likely</td>
    </tr>
    <tr>
      <td><span class="dot" style="background:#e74c3c;"></span>Hypertensive Crisis</td>
      <td>180 or higher</td><td>120 or higher</td>
      <td style="color:#c0000a;font-size:.74rem;font-weight:700;">Emergency — seek care immediately</td>
    </tr>
    <tr>
      <td><span class="dot" style="background:#9b59b6;"></span>Low (Hypotension)</td>
      <td>Less than 90</td><td>Less than 60</td>
      <td style="color:#6a2090;font-size:.74rem;">Stay hydrated, consult doctor</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN PAGE RENDERER  (called from app.py)
# ─────────────────────────────────────────────────────────────────────────────

def render_camera_bp_page():
    """
    Call this from app.py inside the `elif page == "BP Camera":` block.
    """

    st.html('<div class="page-header"><h1>🩺 BP Tracker — Blood Pressure Log & Monitor</h1></div>')

    # ── How it works ─────────────────────────────────────────────────────────
    with st.expander("ℹ️ How does this work?", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            _info_card(
                "Manual BP Log",
                """Measure your BP using your <b>home cuff or clinic device</b>,
                then enter the reading here.<br><br>
                HealNet saves your readings, classifies them by AHA guidelines,
                shows your trend over time, and gives you personalised lifestyle
                advice — exactly like the top BP tracking apps.""",
                "#3b9edb"
            )
        with col2:
            _info_card(
                "Why not camera BP?",
                """A standard smartphone camera <b>cannot measure blood pressure</b>.<br><br>
                The camera is used only for <b>heart rate</b> (see Camera Vitals page),
                which works by detecting pulse through your fingertip.<br><br>
                Any app claiming to measure BP through a phone camera alone is
                <b>not scientifically validated</b> for clinical use.""",
                "#e0a000"
            )

    st.markdown("---")

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_log, tab_history, tab_advice, tab_reference, tab_export = st.tabs([
        "📝 Log Reading",
        "📈 History & Trends",
        "💡 Lifestyle Advice",
        "📋 BP Reference",
        "📤 Export",
    ])

    # ═════════════════════════════════════════════════════════════════════════
    #  TAB 1 — LOG A READING
    # ═════════════════════════════════════════════════════════════════════════
    with tab_log:
        _sub_label("📝 Enter Your BP Reading")
        st.caption("Measure with your physical BP cuff, then enter the values below.")

        col_sys, col_dia, col_hr = st.columns(3)
        with col_sys:
            sys_val = st.number_input(
                "Systolic (mmHg)",
                min_value=60, max_value=250,
                value=120, step=1,
                key="bp_sys_input",
                help="The top number — pressure when heart beats"
            )
        with col_dia:
            dia_val = st.number_input(
                "Diastolic (mmHg)",
                min_value=40, max_value=150,
                value=80, step=1,
                key="bp_dia_input",
                help="The bottom number — pressure when heart rests"
            )
        with col_hr:
            hr_val = st.number_input(
                "Heart Rate (bpm)",
                min_value=0, max_value=220,
                value=72, step=1,
                key="bp_hr_input",
                help="Optional — from your cuff or Camera Vitals page"
            )

        posture = st.selectbox(
            "Context / Posture",
            POSTURE_OPTIONS,
            key="bp_posture_input",
            help="Select your position and situation when you took this reading"
        )

        note = st.text_input(
            "Note (optional)",
            key="bp_note_input",
            placeholder="e.g. After coffee, mild headache, clinic visit…"
        )

        # ── Live classification preview ───────────────────────────────────
        level, color, bg = classify_bp(sys_val, dia_val)
        st.html(f"""
        <div style="background:{bg};border:1px solid {color}55;
                    border-radius:10px;padding:12px 18px;margin:14px 0;
                    display:flex;align-items:center;gap:14px;flex-wrap:wrap;">
          <div style="font-size:1.9rem;font-weight:800;color:{color};
                      font-family:'Rajdhani',sans-serif;">{sys_val}/{dia_val}</div>
          <div>
            <div style="font-size:.70rem;font-weight:700;color:{color};
                        text-transform:uppercase;letter-spacing:.10em;">{level}</div>
            <div style="font-size:.76rem;color:#5a8ab0;margin-top:2px;">
              {posture}
            </div>
          </div>
        </div>
        """)

        if st.button("💾 Save Reading", type="primary", use_container_width=True):
            _save_reading(sys_val, dia_val, hr_val if hr_val > 0 else None, posture, note)
            st.success(f"✅ Reading saved — {sys_val}/{dia_val} mmHg ({level})")
            if level == "Hypertensive Crisis":
                st.error("🆘 Hypertensive Crisis detected — please seek emergency medical care immediately.")
            elif level in ("Stage 1 Hypertension", "Stage 2 Hypertension"):
                st.warning("⚠️ Elevated BP detected — consult your doctor and check the Lifestyle Advice tab.")

    # ═════════════════════════════════════════════════════════════════════════
    #  TAB 2 — HISTORY & TRENDS
    # ═════════════════════════════════════════════════════════════════════════
    with tab_history:
        readings = _get_readings()

        if not readings:
            st.info("No readings yet. Log your first BP reading in the **Log Reading** tab.")
        else:
            _sub_label("📈 BP Trend")
            _render_trend_chart(readings)

            st.markdown("---")
            _sub_label("📊 Summary")
            _render_summary_stats(readings)

            st.markdown("---")
            _sub_label("📋 All Readings")

            # Filter controls
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filter_level = st.selectbox(
                    "Filter by level",
                    ["All", "Normal", "Elevated",
                     "Stage 1 Hypertension", "Stage 2 Hypertension",
                     "Hypertensive Crisis", "Low (Hypotension)"],
                    key="bp_filter_level"
                )
            with col_f2:
                filter_posture = st.selectbox(
                    "Filter by context",
                    ["All"] + POSTURE_OPTIONS,
                    key="bp_filter_posture"
                )

            filtered = readings[::-1]   # newest first
            if filter_level != "All":
                filtered = [r for r in filtered if r["level"] == filter_level]
            if filter_posture != "All":
                filtered = [r for r in filtered if r["posture"] == filter_posture]

            if not filtered:
                st.info("No readings match the selected filters.")
            else:
                for r in filtered[:20]:
                    _render_reading_card(r)

            if st.button("🗑️ Clear All Readings", key="bp_clear_all"):
                st.session_state[SESSION_KEY] = []
                st.rerun()

    # ═════════════════════════════════════════════════════════════════════════
    #  TAB 3 — LIFESTYLE ADVICE
    # ═════════════════════════════════════════════════════════════════════════
    with tab_advice:
        _sub_label("💡 Personalised Lifestyle Advice")

        readings = _get_readings()

        # Base advice on latest reading if available, else let user select
        if readings:
            latest_level = readings[-1]["level"]
            latest_bp    = readings[-1]
            st.caption(
                f"Based on your latest reading: "
                f"**{latest_bp['systolic']}/{latest_bp['diastolic']} mmHg** "
                f"— {latest_level} ({latest_bp['timestamp']})"
            )
            selected_level = st.selectbox(
                "Or view advice for a different level:",
                ["Normal", "Elevated", "Stage 1 Hypertension",
                 "Stage 2 Hypertension", "Hypertensive Crisis"],
                index=["Normal", "Elevated", "Stage 1 Hypertension",
                       "Stage 2 Hypertension", "Hypertensive Crisis"]
                       .index(latest_level) if latest_level in
                       ["Normal", "Elevated", "Stage 1 Hypertension",
                        "Stage 2 Hypertension", "Hypertensive Crisis"]
                       else 0,
                key="bp_advice_level"
            )
        else:
            st.caption("Log a reading first to get personalised advice, or select a level below:")
            selected_level = st.selectbox(
                "Select BP level:",
                ["Normal", "Elevated", "Stage 1 Hypertension",
                 "Stage 2 Hypertension", "Hypertensive Crisis"],
                key="bp_advice_level_empty"
            )

        _render_lifestyle_advice(selected_level)

        st.markdown("---")
        _info_card(
            "General Tips for Everyone",
            """🧂 <b>Reduce sodium</b> — aim for less than 2,300 mg per day (about 1 teaspoon of salt).<br>
            🥦 <b>DASH diet</b> — fruits, vegetables, whole grains, lean protein, low-fat dairy.<br>
            🏃 <b>Exercise</b> — at least 150 minutes of moderate activity per week.<br>
            😴 <b>Sleep</b> — poor sleep raises BP; aim for 7–8 hours per night.<br>
            🧘 <b>Stress</b> — chronic stress elevates BP; try meditation, yoga, or breathing exercises.<br>
            🚭 <b>No smoking</b> — smoking damages blood vessels and raises BP permanently.<br>
            🍺 <b>Limit alcohol</b> — no more than 1 drink/day for women, 2 for men.""",
            "#00c896"
        )

    # ═════════════════════════════════════════════════════════════════════════
    #  TAB 4 — BP REFERENCE TABLE
    # ═════════════════════════════════════════════════════════════════════════
    with tab_reference:
        _sub_label("📋 AHA Blood Pressure Categories")
        st.caption("American Heart Association (AHA) 2017 Guidelines")
        import streamlit.components.v1 as components
        components.html(BP_REFERENCE_HTML, height=310, scrolling=False)

        st.markdown("---")
        col_a, col_b = st.columns(2)
        with col_a:
            _info_card(
                "How to Measure Correctly",
                """1. Sit quietly for <b>5 minutes</b> before measuring.<br>
                2. Sit with back supported, feet flat on the floor.<br>
                3. Rest your arm at <b>heart level</b> on a table.<br>
                4. Do not talk during the measurement.<br>
                5. Take <b>2–3 readings</b>, 1 minute apart, and record the average.<br>
                6. Measure at the <b>same time each day</b> for consistent tracking.""",
                "#3b9edb"
            )
        with col_b:
            _info_card(
                "When to See a Doctor",
                """🔴 <b>Any reading ≥ 180/120</b> — emergency care immediately.<br>
                🟠 <b>Consistently ≥ 140/90</b> — see doctor within 1 week.<br>
                🟡 <b>Consistently 130–139 / 80–89</b> — schedule a check-up.<br>
                🟣 <b>BP < 90/60 with symptoms</b> (dizziness, fainting) — see doctor.<br><br>
                Always bring your BP log to appointments — it helps your doctor
                see the full picture, not just one reading.""",
                "#e67e22"
            )

    # ═════════════════════════════════════════════════════════════════════════
    #  TAB 5 — EXPORT
    # ═════════════════════════════════════════════════════════════════════════
    with tab_export:
        readings = _get_readings()
        _sub_label("📤 Export for Doctor Consultation")

        if not readings:
            st.info("No readings to export yet. Log some readings first.")
        else:
            st.caption(
                f"Your {len(readings)} reading(s) will be exported as a CSV file. "
                "Share this with your healthcare provider for a more complete consultation."
            )

            fname = f"healnet_bp_{datetime.date.today().isoformat()}.csv"
            st.download_button(
                label="⬇️ Download BP Log as CSV",
                data=_readings_to_csv(),
                file_name=fname,
                mime="text/csv",
                use_container_width=True,
                type="primary",
            )

            st.markdown("---")
            _sub_label("👁️ Preview (latest 10)")
            import pandas as pd
            df = pd.DataFrame(readings[::-1][:10])[[
                "timestamp", "systolic", "diastolic",
                "heart_rate", "posture", "level", "note"
            ]].copy()
            df.columns = [
                "Time", "Systolic", "Diastolic",
                "Heart Rate", "Context", "Level", "Note"
            ]
            st.dataframe(df, use_container_width=True, hide_index=True)
