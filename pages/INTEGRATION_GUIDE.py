# ════════════════════════════════════════════════════════════════
#  HOW TO INTEGRATE camera_vitals.py INTO YOUR app.py
#  ──────────────────────────────────────────────────────────────
#  3 small changes needed. Everything else stays the same.
# ════════════════════════════════════════════════════════════════


# ────────────────────────────────────────────────────────────────
# CHANGE 1 — Add import at the top of app.py (near line 30)
#            Right after the pupil_detection import block
# ────────────────────────────────────────────────────────────────

try:
    from camera_vitals import render_camera_vitals_page
    CAMERA_VITALS_OK = True
except ImportError:
    CAMERA_VITALS_OK = False


# ────────────────────────────────────────────────────────────────
# CHANGE 2 — Add "Camera Vitals" to the sidebar nav list
#            Find this line in app.py:
#
#   nav_options = ["Dashboard","Patient Management","Health Monitoring","Report Analysis","Pupil Detection"]
#
#            Replace it with:
# ────────────────────────────────────────────────────────────────

nav_options = [
    "Dashboard",
    "Patient Management",
    "Health Monitoring",
    "Report Analysis",
    "Pupil Detection",
    "Camera Vitals",       # <── ADD THIS
]


# ────────────────────────────────────────────────────────────────
# CHANGE 3 — Add the page handler at the very end of app.py
#            After the "Pupil Detection" elif block, add:
# ────────────────────────────────────────────────────────────────

# elif page == "Camera Vitals":
#     breadcrumb(["Dashboard", "Camera Vitals"], "Camera Vitals")
#     if CAMERA_VITALS_OK:
#         render_camera_vitals_page()
#     else:
#         st.error("camera_vitals.py not found. Place it in the pages/ folder.")


# ────────────────────────────────────────────────────────────────
# CHANGE 4 (Optional) — Add quick-action card on Dashboard
#            Inside the Dashboard section, add a 6th column card:
#            (Find the 5-column qa block and add qa6)
# ────────────────────────────────────────────────────────────────

# with qa6:
#     st.html("""<div class="dashboard-card"><h3>📷 Camera Vitals</h3>
#       <p>Measure heart rate using your phone camera — no hardware needed.</p></div>""")
#     if st.button("Measure via Camera →", key="d_cam", use_container_width=True):
#         st.session_state.page = "Camera Vitals"; st.rerun()


# ════════════════════════════════════════════════════════════════
#  FILE PLACEMENT
# ════════════════════════════════════════════════════════════════
#  Place camera_vitals.py in the SAME folder as app.py
#  (same place where pupil_detection.py lives)
#
#  your_project/
#  ├── app.py
#  ├── camera_vitals.py        ← put it here
#  ├── pupil_detection.py
#  ├── login.py
#  └── ...
#
# ════════════════════════════════════════════════════════════════
#  NO pip installs needed — uses browser WebRTC + vanilla JS
# ════════════════════════════════════════════════════════════════
