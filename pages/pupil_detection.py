"""
pages/pupil_detection.py — HealNet Pupil Detection UI
=======================================================
Called from app.py when page == "Pupil Detection".
Provides:
  • Live upload & instant analysis
  • Dual-eye (anisocoria) mode
  • Pull stored pupil image from DB for any user
  • Full clinical report with severity badge
"""

import streamlit as st
import sqlite3
import cv2
import numpy as np
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from pupil_analysis import (
        analyze_pupil_image,
        analyze_both_eyes,
        image_to_bytes,
        PupilResult,
        SEVERITY,
    )
    ENGINE_OK = True
except ImportError as _e:
    ENGINE_OK = False
    _IMPORT_ERR = str(_e)

# ── DB helpers ────────────────────────────────────────────────────────────────
DB = "healnet_auth.db"

def _db():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def _fetch_pupil_blob(table: str, username: str) -> bytes | None:
    con = _db()
    try:
        row = con.execute(
            f"SELECT pupil_image FROM {table} WHERE username=?", (username,)
        ).fetchone()
        return bytes(row["pupil_image"]) if row and row["pupil_image"] else None
    except Exception:
        return None
    finally:
        con.close()

def _all_users():
    """Return list of (display_label, table, username) for all stored users."""
    con = _db()
    results = []
    try:
        for row in con.execute("SELECT username, name FROM solo_users WHERE pupil_image IS NOT NULL").fetchall():
            results.append((f"👤 {row['name']} ({row['username']})", "solo_users", row["username"]))
        for row in con.execute("SELECT username, name FROM staff WHERE pupil_image IS NOT NULL").fetchall():
            results.append((f"🩺 {row['name']} ({row['username']})", "staff", row["username"]))
        for row in con.execute("SELECT username, name FROM org_patients WHERE pupil_image IS NOT NULL").fetchall():
            results.append((f"🏥 {row['name']} ({row['username']})", "org_patients", row["username"]))
    except Exception:
        pass
    finally:
        con.close()
    return results


# ── Severity badge renderer ────────────────────────────────────────────────────
def _severity_badge(severity: str) -> str:
    palette = {
        "NORMAL":   ("#00aa66", "rgba(0,170,102,0.12)"),
        "MILD":     ("#e0a000", "rgba(224,160,0,0.12)"),
        "MODERATE": ("#f57c00", "rgba(245,124,0,0.12)"),
        "SEVERE":   ("#dd2844", "rgba(221,40,68,0.12)"),
        "ERROR":    ("#888888", "rgba(136,136,136,0.12)"),
    }
    col, bg = palette.get(severity, palette["ERROR"])
    icon = SEVERITY.get(severity, ("", ""))[1]
    return (
        f'<span style="display:inline-block;background:{bg};color:{col};'
        f'border:1px solid {col};border-radius:6px;padding:4px 14px;'
        f'font-size:.85rem;font-weight:800;letter-spacing:.08em;">'
        f'{icon} {severity}</span>'
    )


# ── Render single eye result ───────────────────────────────────────────────────
def _render_result(result: PupilResult, label: str = ""):
    if result.error:
        st.error(f"❌ Detection failed: {result.error}")
        return

    sev_col_map = {
        "NORMAL":   "#00aa66",
        "MILD":     "#e0a000",
        "MODERATE": "#f57c00",
        "SEVERE":   "#dd2844",
        "ERROR":    "#888888",
    }
    sev_col = sev_col_map.get(result.severity, "#888888")

    if label:
        st.markdown(f"### {label}")

    col_img, col_stats = st.columns([1, 1], gap="large")

    with col_img:
        if result.annotated_image is not None:
            annotated_bytes = image_to_bytes(result.annotated_image)
            st.image(annotated_bytes, caption="Annotated eye image", use_container_width=True)
        else:
            st.info("No annotated image available.")

    with col_stats:
        # Severity badge
        st.markdown(_severity_badge(result.severity), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # Key metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("PIR",         f"{result.pupil_iris_ratio:.2f}")
        m2.metric("Pupil (px)",  f"{result.pupil_radius_px:.1f}")
        m3.metric("Iris (px)",   f"{result.iris_radius_px:.1f}")

        m4, m5, m6 = st.columns(3)
        m4.metric("Circularity", f"{result.circularity:.2f}")
        m5.metric("Condition",   result.condition)
        m6.metric("Confidence",  f"{result.confidence}%")

        # Flags
        flags = []
        if result.is_dilated:     flags.append("🔵 Dilated (Mydriasis)")
        if result.is_constricted: flags.append("🟡 Constricted (Miosis)")
        if result.is_irregular:   flags.append("🟠 Irregular Shape")
        if not flags:             flags.append("✅ No flags")
        st.markdown("**Flags:** " + "  ·  ".join(flags))

        # Detection method
        st.caption(f"Detection engine: {result.method.upper()}  •  "
                   f"Confidence: {result.confidence}%")

    # PIR gauge
    st.markdown("**Pupil-to-Iris Ratio (PIR) gauge**")
    # Clamp PIR to 0-1 for display
    pir_display = min(1.0, max(0.0, result.pupil_iris_ratio))
    st.progress(pir_display, text=f"PIR = {result.pupil_iris_ratio:.2f}  |  Normal: 0.20 – 0.45")

    # Clinical notes
    with st.expander("📋 Clinical Notes", expanded=True):
        for note in result.clinical_notes:
            st.markdown(f"- {note}")

    # Possible causes
    if result.possible_causes and result.possible_causes[0] != "No abnormality identified — routine follow-up as needed":
        with st.expander("🩺 Possible Causes / Differential Diagnosis"):
            for cause in result.possible_causes:
                st.markdown(f"- {cause}")
            st.caption("⚠️ This is an AI-assisted screening tool. Always confirm with a licensed clinician.")
    else:
        st.success("✅ No significant abnormality detected. Routine follow-up as advised.")


# ── Main page renderer (called from app.py) ───────────────────────────────────
def render_pupil_detection_page():
    """Entry point called by app.py when page == 'Pupil Detection'."""

    st.html('<div class="page-header"><h1>👁 Pupil Detection & Analysis</h1></div>')
    st.markdown(
        "AI-powered pupil screening for **dilation (Mydriasis)**, "
        "**constriction (Miosis)**, **anisocoria** (unequal pupils), "
        "and **shape irregularities**."
    )

    # ── Dependency check ──────────────────────────────────────────────────
    if not ENGINE_OK:
        st.error(
            "⚠️ `pupil_analysis.py` could not be imported. "
            f"Error: `{_IMPORT_ERR}`\n\n"
            "Install dependencies with:\n"
            "```\npip install opencv-python mediapipe numpy\n```"
        )
        return

    # ── Mode selector ─────────────────────────────────────────────────────
    st.markdown("---")
    mode = st.radio(
        "Analysis Mode",
        ["📤 Upload Image", "👥 Dual-Eye (Anisocoria)", "🗄️ Analyse Stored Profile Image"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # MODE 1 — Upload & Analyse
    # ═══════════════════════════════════════════════════════════════════════
    if mode == "📤 Upload Image":
        st.subheader("Upload Eye / Pupil Image")
        st.markdown(
            "Upload a **clear, well-lit, close-up** photo of the eye. "
            "The pupil should be visible and in focus."
        )

        col_up, col_tips = st.columns([2, 1], gap="large")
        with col_up:
            uploaded = st.file_uploader(
                "Choose image", type=["png", "jpg", "jpeg"],
                key="pd_upload_single", label_visibility="collapsed"
            )
        with col_tips:
            st.markdown("""
**Tips for best results:**
- Use a macro/close-up shot
- Avoid heavy flash (causes red-eye artefact)
- Keep subject still, well-lit
- One eye per image
- Minimum 200 × 200 px
            """)

        if uploaded:
            raw_bytes = uploaded.read()
            st.markdown("---")
            with st.spinner("🔍 Analysing pupil…"):
                result = analyze_pupil_image(raw_bytes)
            _render_result(result, "Analysis Result")

    # ═══════════════════════════════════════════════════════════════════════
    # MODE 2 — Dual Eye (Anisocoria check)
    # ═══════════════════════════════════════════════════════════════════════
    elif mode == "👥 Dual-Eye (Anisocoria)":
        st.subheader("Dual-Eye Analysis — Anisocoria Detection")
        st.markdown(
            "Upload **separate images** of the left and right eye to detect "
            "**unequal pupil sizes (anisocoria)**."
        )

        c_left, c_right = st.columns(2, gap="large")
        with c_left:
            st.markdown("**Left Eye**")
            left_up = st.file_uploader(
                "Left eye", type=["png", "jpg", "jpeg"],
                key="pd_left", label_visibility="collapsed"
            )
            if left_up:
                st.image(left_up, caption="Left eye preview", width=220)

        with c_right:
            st.markdown("**Right Eye**")
            right_up = st.file_uploader(
                "Right eye", type=["png", "jpg", "jpeg"],
                key="pd_right", label_visibility="collapsed"
            )
            if right_up:
                st.image(right_up, caption="Right eye preview", width=220)

        if left_up or right_up:
            if st.button("🔍 Run Dual-Eye Analysis", type="primary"):
                left_bytes  = left_up.read()  if left_up  else None
                right_bytes = right_up.read() if right_up else None

                with st.spinner("Analysing both eyes…"):
                    out = analyze_both_eyes(left_bytes, right_bytes)

                st.markdown("---")

                # ── Anisocoria summary banner ──
                if out["anisocoria"]:
                    sev = out["anisocoria_severity"]
                    badge = _severity_badge(sev)
                    st.markdown(
                        f'<div style="background:rgba(221,40,68,0.08);border:1px solid rgba(221,40,68,0.30);'
                        f'border-left:4px solid #dd2844;border-radius:12px;padding:16px 20px;margin-bottom:16px;">'
                        f'<strong style="color:#dd2844;">⚠️ Anisocoria Detected</strong>&nbsp;&nbsp;{badge}<br>'
                        + "".join(f'<div style="font-size:.85rem;color:#660018;margin-top:6px;">• {n}</div>'
                                  for n in out["anisocoria_notes"])
                        + "</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.success("✅ No anisocoria detected — pupils appear symmetric.")

                # ── Per-eye results ──
                tabs = st.tabs(["Left Eye", "Right Eye"])
                with tabs[0]:
                    if out["left"]:
                        _render_result(out["left"], "Left Eye")
                    else:
                        st.info("No left eye image provided.")
                with tabs[1]:
                    if out["right"]:
                        _render_result(out["right"], "Right Eye")
                    else:
                        st.info("No right eye image provided.")

    # ═══════════════════════════════════════════════════════════════════════
    # MODE 3 — Analyse stored profile image
    # ═══════════════════════════════════════════════════════════════════════
    elif mode == "🗄️ Analyse Stored Profile Image":
        st.subheader("Analyse Pupil Image from Registered Profile")
        st.markdown(
            "Retrieve and analyse the pupil image that was uploaded during sign-up "
            "for any registered user."
        )

        users = _all_users()
        if not users:
            st.warning(
                "⚠️ No users with stored pupil images found in the database. "
                "Users must upload a pupil image during sign-up to use this feature."
            )
            return

        labels = [u[0] for u in users]
        choice = st.selectbox("Select user", labels, key="pd_user_sel")
        idx = labels.index(choice)
        _, table, username = users[idx]

        if st.button("🔍 Analyse Profile Pupil Image", type="primary"):
            blob = _fetch_pupil_blob(table, username)
            if not blob:
                st.error("⚠️ No pupil image found for this user (may have been deleted).")
                return

            with st.spinner("Analysing stored pupil image…"):
                result = analyze_pupil_image(blob)

            st.markdown("---")
            _render_result(result, f"Analysis — {choice}")

    # ── Reference card ─────────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("📖 Reference — PIR Interpretation Guide"):
        st.markdown("""
| Pupil-to-Iris Ratio (PIR) | Condition | Severity |
|---|---|---|
| < 0.18 | **Constricted (Miosis)** | Moderate – Severe |
| 0.18 – 0.20 | **Borderline Miosis** | Mild |
| **0.20 – 0.45** | **Normal** | ✅ |
| 0.45 – 0.50 | **Borderline Mydriasis** | Mild |
| > 0.50 | **Dilated (Mydriasis)** | Moderate – Severe |

**Circularity** (1.0 = perfect circle): values below **0.70** suggest irregular pupil shape.

**Anisocoria**: PIR difference > 0.10 between left and right eyes is clinically significant.

> ⚠️ This tool is for **screening purposes only**. All findings must be verified by a qualified clinician.
        """)
