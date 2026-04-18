"""
healnet_ai.py  —  HealNet AI Layer
===================================
Drop this file next to app.py (same folder).

In app.py, after the vitals_map is built and BEFORE the alert section, add:

    from healnet_ai import HealNetAI
    ai = HealNetAI(patient_id, vitals_map, st.session_state.get("alert_log", []))
    ai.render()

That's it.  The AI panel renders itself via Streamlit.
"""

import streamlit as st
import datetime
from collections import defaultdict


# ─────────────────────────────────────────────────────────────────────
#  RULE WEIGHTS  (how much each abnormal vital contributes to risk %)
# ─────────────────────────────────────────────────────────────────────
VITAL_WEIGHTS = {
    "Blood Pressure":   {"CRITICAL": 30, "HIGH": 20, "MODERATE": 10, "LOW": 5,  "NORMAL": 0},
    "Heart Rate":       {"CRITICAL": 25, "HIGH": 18, "MODERATE":  8, "LOW": 4,  "NORMAL": 0},
    "SpO₂":            {"CRITICAL": 30, "HIGH": 22, "MODERATE": 12, "LOW": 5,  "NORMAL": 0},
    "Blood Sugar":      {"CRITICAL": 20, "HIGH": 14, "MODERATE":  7, "LOW": 3,  "NORMAL": 0},
    "Temperature":      {"CRITICAL": 20, "HIGH": 14, "MODERATE":  6, "LOW": 3,  "NORMAL": 0},
    "Respiratory Rate": {"CRITICAL": 20, "HIGH": 14, "MODERATE":  6, "LOW": 3,  "NORMAL": 0},
    "BMI":              {"CRITICAL": 10, "HIGH":  7, "MODERATE":  3, "LOW": 2,  "NORMAL": 0},
}

MAX_RAW_SCORE = sum(w["CRITICAL"] for w in VITAL_WEIGHTS.values())   # 155

# ─────────────────────────────────────────────────────────────────────
#  RECOMMENDATION RULES  (checked in priority order, first match wins)
# ─────────────────────────────────────────────────────────────────────
RECOMMENDATIONS = [
    # (condition_fn, icon, message)
    (lambda v: _level(v, "SpO₂")         in ("CRITICAL","HIGH"),
     "🆘", "SpO₂ critically low — administer supplemental oxygen immediately and call emergency services."),

    (lambda v: _level(v, "Blood Pressure") == "CRITICAL",
     "🚨", "Blood pressure is dangerously high — risk of stroke/heart attack. Seek emergency care NOW."),

    (lambda v: _level(v, "Heart Rate")    == "CRITICAL",
     "🚨", "Severe arrhythmia detected — patient needs immediate cardiac evaluation."),

    (lambda v: _level(v, "Blood Pressure") == "HIGH",
     "🔴", "Stage 2 hypertension — consult a physician today. Reduce sodium, monitor closely."),

    (lambda v: _level(v, "Heart Rate")    == "HIGH",
     "🔴", "Tachycardia/Bradycardia detected — avoid stimulants, rest, and consult a cardiologist."),

    (lambda v: _level(v, "Blood Sugar")   in ("CRITICAL","HIGH"),
     "🔴", "Blood sugar is elevated — check for diabetes. Reduce sugar intake and consult a physician."),

    (lambda v: _level(v, "Temperature")   in ("CRITICAL","HIGH"),
     "🔴", "High fever — check for infection or heat stroke. Hydrate and seek medical attention."),

    (lambda v: _level(v, "Respiratory Rate") in ("CRITICAL","HIGH"),
     "🔴", "Abnormal respiratory rate — may indicate respiratory distress. Monitor breathing carefully."),

    (lambda v: _level(v, "BMI")           == "CRITICAL",
     "🟡", "BMI indicates severe obesity — recommend dietary assessment and exercise program."),

    (lambda v: _level(v, "BMI")           == "HIGH",
     "🟡", "BMI is above healthy range — encourage balanced diet and regular physical activity."),

    (lambda v: _level(v, "SpO₂")         == "MODERATE",
     "🟡", "SpO₂ slightly below normal — avoid strenuous activity and monitor breathing."),

    (lambda v: all(_level(v, k) == "NORMAL" for k in VITAL_WEIGHTS),
     "✅", "All vitals are within normal range — continue regular check-ups and healthy lifestyle."),

    # default
    (lambda v: True,
     "🟡", "Some vitals need attention — consult your physician at the next available appointment."),
]


def _level(vitals_map: dict, vital_name: str) -> str:
    """Return the level string for a vital, or 'NORMAL' if not present."""
    entry = vitals_map.get(vital_name)
    if entry is None:
        return "NORMAL"
    # vitals_map values are (value_str, level, message)
    return entry[1]


# ─────────────────────────────────────────────────────────────────────
#  CORE CLASS
# ─────────────────────────────────────────────────────────────────────
class HealNetAI:
    """
    Parameters
    ----------
    patient_id  : str   — e.g. "P001"
    vitals_map  : dict  — same dict built in app.py:
                          { "Blood Pressure": ("149/100 mmHg", "HIGH", "msg"), ... }
    alert_log   : list  — st.session_state["alert_log"]
    """

    def __init__(self, patient_id: str, vitals_map: dict, alert_log: list):
        self.pid        = patient_id
        self.vitals     = vitals_map
        self.alert_log  = [e for e in alert_log if e.get("patient_id") == patient_id]
        self.risk_score = self._compute_risk()
        self.risk_label, self.risk_color = self._risk_label()
        self.trends     = self._detect_trends()
        self.recs       = self._get_recommendations()

    # ── 1. RISK SCORE ────────────────────────────────────────────────
    def _compute_risk(self) -> int:
        """
        Rule-based weighted scoring, normalised to 0-100 %.
        Each vital's level maps to a weight; sum is scaled to percentage.
        """
        raw = 0
        for vital, weights in VITAL_WEIGHTS.items():
            level = _level(self.vitals, vital)
            raw  += weights.get(level, 0)

        # Clamp to 0–100
        pct = min(100, round((raw / MAX_RAW_SCORE) * 100))
        return pct

    def _risk_label(self):
        s = self.risk_score
        if s >= 70:  return "CRITICAL RISK",  "#b01030"
        if s >= 45:  return "HIGH RISK",       "#b07800"
        if s >= 20:  return "MODERATE RISK",   "#cc8800"
        return       "LOW RISK",               "#007040"

    # ── 2. TREND DETECTION ───────────────────────────────────────────
    def _detect_trends(self) -> list[dict]:
        """
        Scan the last 10 alert-log entries for this patient.
        Flag any vital that appeared as Critical/High 3+ times → trending up.
        Flag any vital that cleared (no recent entry)          → improving.
        Returns a list of { vital, trend, count, note }.
        """
        recent   = self.alert_log[:20]           # newest first
        counts   = defaultdict(int)
        cat_seen = defaultdict(set)

        for entry in recent:
            v = entry.get("vital", "")
            c = entry.get("category", "")
            counts[v] += 1
            cat_seen[v].add(c)

        trends = []
        for vital, count in counts.items():
            cats = cat_seen[vital]
            if count >= 3 and "Critical" in cats:
                trends.append({
                    "vital":  vital,
                    "trend":  "📈 Worsening",
                    "count":  count,
                    "note":   f"Flagged as Critical {count}× in recent history — persistent risk.",
                    "color":  "#6a0018",
                })
            elif count >= 2 and "Warning" in cats and "Critical" not in cats:
                trends.append({
                    "vital":  vital,
                    "trend":  "⚠️ Watch",
                    "count":  count,
                    "note":   f"Flagged {count}× as Warning — monitor closely.",
                    "color":  "#4a2d00",
                })

        # Check for vitals that were previously bad but are now NORMAL
        previously_flagged = {e.get("vital") for e in recent}
        for vital in previously_flagged:
            if _level(self.vitals, vital) == "NORMAL" and vital not in counts:
                trends.append({
                    "vital":  vital,
                    "trend":  "📉 Improving",
                    "count":  0,
                    "note":   "Previously flagged — now within normal range.",
                    "color":  "#003d1a",
                })

        return trends

    # ── 3. RECOMMENDATIONS ───────────────────────────────────────────
    def _get_recommendations(self) -> list[tuple]:
        """Return all matching recommendations (icon, message)."""
        results = []
        for condition, icon, msg in RECOMMENDATIONS:
            try:
                if condition(self.vitals):
                    results.append((icon, msg))
                    # Stop after first critical-tier match to avoid noise
                    if icon == "🆘":
                        break
            except Exception:
                continue
        # Return top 4 max
        return results[:4]

    # ── 4. RENDER ────────────────────────────────────────────────────
    def render(self):
        """Call this in app.py to render the entire AI panel."""
        st.markdown("---")
        st.subheader("🤖 AI Predictive Insights")

        # ── Row 1: Risk Gauge + summary ──────────────────────────────
        g_col, s_col = st.columns([1, 2])

        with g_col:
            gauge_html = self._gauge_html()
            st.html(gauge_html)

        with s_col:
            st.markdown(f"""
<div style="background:rgba(255,255,255,0.60);border:1px solid rgba(255,255,255,0.85);
border-radius:14px;padding:18px 22px;backdrop-filter:blur(12px);margin-top:6px;">
  <div style="font-size:.68rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.14em;color:#6a9abf;margin-bottom:6px;">AI Risk Assessment</div>
  <div style="font-size:2rem;font-weight:800;color:{self.risk_color};
  font-family:'Outfit',sans-serif;">{self.risk_score}%
    <span style="font-size:.9rem;font-weight:600;color:{self.risk_color};
    margin-left:8px;">{self.risk_label}</span>
  </div>
  <div style="font-size:.80rem;color:#2d5a8e;margin-top:8px;line-height:1.6;">
    Composite score calculated from <strong>{len(self.vitals)}</strong> vital signs
    using weighted rule-based analysis.<br>
    Based on <strong>{len(self.alert_log)}</strong> logged alert(s) for this patient.
  </div>
</div>
""", unsafe_allow_html=True)

        # ── Row 2: Trend Detection ────────────────────────────────────
        st.markdown("#### 📊 Trend Analysis")
        if not self.trends:
            st.info("Not enough history to detect trends yet. Trends appear after a few monitoring cycles.")
        else:
            t_cols = st.columns(min(len(self.trends), 3))
            for i, t in enumerate(self.trends[:3]):
                with t_cols[i]:
                    st.html(f"""
<div style="background:rgba(255,255,255,0.58);border:1px solid rgba(255,255,255,0.85);
border-radius:12px;padding:14px 16px;backdrop-filter:blur(10px);height:100%;">
  <div style="font-size:.68rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.12em;color:#6a9abf;margin-bottom:4px;">{t['vital']}</div>
  <div style="font-size:1rem;font-weight:800;color:{t['color']};margin-bottom:6px;">{t['trend']}</div>
  <div style="font-size:.75rem;color:#1e3a52;line-height:1.5;">{t['note']}</div>
</div>""")

        # ── Row 3: Recommendations ────────────────────────────────────
        st.markdown("#### 💡 AI Recommendations")
        for icon, msg in self.recs:
            bg = {
                "🆘": "rgba(255,200,205,0.90)",
                "🚨": "rgba(255,210,215,0.90)",
                "🔴": "rgba(255,244,195,0.90)",
                "🟡": "rgba(255,252,220,0.88)",
                "✅": "rgba(220,255,235,0.88)",
            }.get(icon, "rgba(255,255,255,0.70)")
            border = {
                "🆘": "#b01030", "🚨": "#b01030",
                "🔴": "#b07800", "🟡": "#cc8800", "✅": "#00a860",
            }.get(icon, "#aaa")
            text_color = {
                "🆘": "#5a0012", "🚨": "#5a0012",
                "🔴": "#4a2d00", "🟡": "#3d2600", "✅": "#003d1a",
            }.get(icon, "#1e2d3d")
            st.html(f"""
<div style="background:{bg};border-left:4px solid {border};border-radius:10px;
padding:12px 18px;margin-bottom:8px;">
  <span style="font-size:.88rem;font-weight:700;color:{text_color};">
    {icon}&nbsp; {msg}
  </span>
</div>""")

        # ── Row 4: Vital Breakdown Table ─────────────────────────────
        with st.expander("📋 View AI Scoring Breakdown", expanded=False):
            rows = ""
            for vital, weights in VITAL_WEIGHTS.items():
                level  = _level(self.vitals, vital)
                score  = weights.get(level, 0)
                max_s  = weights["CRITICAL"]
                pct    = round((score / max_s) * 100) if max_s else 0
                bar_c  = {"CRITICAL":"#b01030","HIGH":"#b07800",
                           "MODERATE":"#cc8800","LOW":"#5577aa","NORMAL":"#00a860"}.get(level,"#aaa")
                rows += f"""
<tr>
  <td style="padding:8px 12px;font-weight:600;color:#0a2540;font-size:.82rem;">{vital}</td>
  <td style="padding:8px 12px;font-size:.82rem;color:{bar_c};font-weight:700;">{level}</td>
  <td style="padding:8px 12px;">
    <div style="background:#e8f0f8;border-radius:4px;height:8px;width:100%;min-width:80px;">
      <div style="background:{bar_c};width:{pct}%;height:8px;border-radius:4px;"></div>
    </div>
  </td>
  <td style="padding:8px 12px;font-size:.82rem;color:#2d5a8e;font-weight:600;">
    {score} / {max_s} pts
  </td>
</tr>"""
            st.html(f"""
<table style="width:100%;border-collapse:collapse;background:rgba(255,255,255,0.55);
border-radius:12px;overflow:hidden;border:1px solid rgba(255,255,255,0.85);">
  <thead>
    <tr style="background:rgba(100,160,220,0.12);">
      <th style="padding:10px 12px;text-align:left;font-size:.70rem;text-transform:uppercase;
      letter-spacing:.10em;color:#2d5a8e;">Vital</th>
      <th style="padding:10px 12px;text-align:left;font-size:.70rem;text-transform:uppercase;
      letter-spacing:.10em;color:#2d5a8e;">Status</th>
      <th style="padding:10px 12px;text-align:left;font-size:.70rem;text-transform:uppercase;
      letter-spacing:.10em;color:#2d5a8e;">Risk Bar</th>
      <th style="padding:10px 12px;text-align:left;font-size:.70rem;text-transform:uppercase;
      letter-spacing:.10em;color:#2d5a8e;">Score</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
  <tfoot>
    <tr style="background:rgba(100,160,220,0.08);">
      <td colspan="3" style="padding:10px 12px;font-size:.80rem;font-weight:800;
      color:#0a2540;text-align:right;">Total Risk Score</td>
      <td style="padding:10px 12px;font-size:.90rem;font-weight:800;
      color:{self.risk_color};">{self.risk_score}% — {self.risk_label}</td>
    </tr>
  </tfoot>
</table>""")

    # ── GAUGE SVG ─────────────────────────────────────────────────────
    def _gauge_html(self) -> str:
        """Semi-circle SVG gauge showing risk %."""
        pct    = self.risk_score / 100
        # Arc from 180° to 0° (left to right)
        import math
        angle  = 180 - (pct * 180)          # degrees on the semicircle
        rad    = math.radians(angle)
        cx, cy, r = 90, 80, 65
        nx     = cx + r * math.cos(rad)
        ny     = cy - r * math.sin(rad)
        # Needle tip
        nlen   = 52
        nrad   = math.radians(angle)
        nx2    = cx + nlen * math.cos(nrad)
        ny2    = cy - nlen * math.sin(nrad)

        # Arc colour stops
        arc_grad = (
            '<defs><linearGradient id="rg" x1="0%" y1="0%" x2="100%" y2="0%">'
            '<stop offset="0%"   stop-color="#00a860"/>'
            '<stop offset="40%"  stop-color="#cc8800"/>'
            '<stop offset="70%"  stop-color="#b07800"/>'
            '<stop offset="100%" stop-color="#b01030"/>'
            '</linearGradient></defs>'
        )
        return f"""
<div style="text-align:center;padding:6px 0;">
<svg viewBox="0 0 180 100" width="180" height="100"
     style="display:block;margin:0 auto;">
  {arc_grad}
  <!-- Track arc -->
  <path d="M {cx-r},{cy} A {r},{r} 0 0,1 {cx+r},{cy}"
        fill="none" stroke="rgba(180,200,230,0.35)" stroke-width="10"
        stroke-linecap="round"/>
  <!-- Filled arc -->
  <path d="M {cx-r},{cy} A {r},{r} 0 0,1 {nx:.2f},{ny:.2f}"
        fill="none" stroke="url(#rg)" stroke-width="10"
        stroke-linecap="round"/>
  <!-- Needle -->
  <line x1="{cx}" y1="{cy}" x2="{nx2:.2f}" y2="{ny2:.2f}"
        stroke="{self.risk_color}" stroke-width="2.5"
        stroke-linecap="round"/>
  <circle cx="{cx}" cy="{cy}" r="5"
          fill="{self.risk_color}" stroke="#fff" stroke-width="1.5"/>
  <!-- Labels -->
  <text x="24" y="98" font-size="8" fill="#00a860" font-weight="700">LOW</text>
  <text x="142" y="98" font-size="8" fill="#b01030" font-weight="700">HIGH</text>
  <text x="{cx}" y="{cy-8}" font-size="18" fill="{self.risk_color}"
        font-weight="800" text-anchor="middle" font-family="Outfit,sans-serif">
    {self.risk_score}%
  </text>
</svg>
<div style="font-size:.70rem;font-weight:800;color:{self.risk_color};
text-transform:uppercase;letter-spacing:.10em;">{self.risk_label}</div>
</div>"""