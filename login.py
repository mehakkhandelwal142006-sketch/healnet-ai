"""
HealNet — Login Page
Run: pip install streamlit  →  streamlit run login.py
"""

import streamlit as st
import sqlite3, hashlib, random, string

# ── PAGE CONFIG ───────────────────────────────────────────────────
st.set_page_config(page_title="HealNet", page_icon="🏥",
                   layout="centered", initial_sidebar_state="collapsed")

# ── DATABASE ──────────────────────────────────────────────────────
DB = "healnet_auth.db"

def db():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS organisations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL, org_code TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS staff(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id INTEGER, name TEXT, username TEXT,
        password TEXT, role TEXT, phone TEXT, staff_id TEXT,
        UNIQUE(username,org_id));
    CREATE TABLE IF NOT EXISTS org_patients(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id INTEGER, name TEXT, username TEXT,
        password TEXT, age INTEGER, gender TEXT,
        contact TEXT, patient_id TEXT, UNIQUE(username,org_id));
    CREATE TABLE IF NOT EXISTS solo_users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT UNIQUE, username TEXT UNIQUE,
        password TEXT, gender TEXT, dob TEXT,
        blood TEXT, contact TEXT, healnet_id TEXT UNIQUE);
    """)
    con.commit(); con.close()

init_db()

# ── HELPERS ───────────────────────────────────────────────────────
def hp(p): return hashlib.sha256(p.encode()).hexdigest()

def gen_code():
    return "HN-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))

def org_by_code(code):
    con = db()
    r = con.execute("SELECT * FROM organisations WHERE org_code=?",
                    (code.upper().strip(),)).fetchone()
    con.close()
    return dict(r) if r else None

# ── SESSION ───────────────────────────────────────────────────────
def S(k, v):
    if k not in st.session_state: st.session_state[k] = v

S("screen", "entry"); S("session", None); S("msg", None); S("msg_type", "error")

def go(s):
    st.session_state.screen = s
    st.session_state.msg = None


def alert(m, t="error"):
    st.session_state.msg = m
    st.session_state.msg_type = t


def do_login(kind, user=None, org=None):
    st.session_state.session = {"kind": kind, "user": user, "org": org}
    st.session_state.msg = None
    st.switch_page("pages/app.py")


def show_msg():
    if st.session_state.msg:
        t = st.session_state.msg_type
        if t == "success":
            st.success(st.session_state.msg)
        elif t == "info":
            st.info(st.session_state.msg)
        else:
            st.error(st.session_state.msg)

# ── GLOBAL CSS ────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&display=swap');

html, body { font-family: 'Sora', sans-serif !important; }
.stApp { background: #f0f4f8 !important; }
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }

div.block-container {
  max-width: 520px !important;
  padding-top: 28px !important;
  padding-bottom: 0px !important;
}

/* ── logo ── */
.hn-logo { display:flex; align-items:center; gap:10px; margin-bottom:6px; }
.hn-logo-box {
  width:36px; height:36px; background:#0d9488; border-radius:9px;
  display:flex; align-items:center; justify-content:center;
}
.hn-logo-name { font-size:21px; font-weight:700; color:#0f172a; }
.hn-tagline   { font-size:13px; color:#64748b; margin:0 0 24px; }

/* ── section titles ── */
.hn-title { font-size:18px; font-weight:700; color:#0f172a; margin:0 0 4px; }
.hn-sub   { font-size:13px; color:#64748b; margin:0 0 22px; }

/* ── portal header ── */
.rp-portal-header {
  display:flex; align-items:center; gap:12px; margin-bottom:20px;
}
.rp-portal-icon {
  width:46px; height:46px; border-radius:11px;
  display:flex; align-items:center; justify-content:center;
  font-size:24px; flex-shrink:0;
}
.rp-portal-title { font-size:19px; font-weight:700; color:#0f172a; }
.rp-portal-sub   { font-size:12px; color:#64748b; }

/* ── option card buttons ── */
div[data-testid="opt_org"]        > button,
div[data-testid="opt_staff"]      > button,
div[data-testid="opt_orgpatient"] > button,
div[data-testid="opt_solo"]       > button {
  width: 100% !important;
  text-align: left !important;
  white-space: pre-line !important;
  line-height: 1.5 !important;
  padding: 14px 16px !important;
  border-radius: 13px !important;
  font-family: 'Sora', sans-serif !important;
  font-size: 14px !important;
  font-weight: 400 !important;
  margin-bottom: 8px !important;
  transition: all .2s !important;
  cursor: pointer !important;
  box-shadow: none !important;
}
div[data-testid="opt_org"] > button {
  background: #f0fdfa !important; color: #0f172a !important;
  border: 1.5px solid #ccfbf1 !important;
}
div[data-testid="opt_org"] > button:hover {
  border-color: #0d9488 !important;
  box-shadow: 0 4px 16px rgba(13,148,136,.15) !important;
  transform: translateX(3px) !important;
}
div[data-testid="opt_staff"] > button {
  background: #eff6ff !important; color: #0f172a !important;
  border: 1.5px solid #bfdbfe !important;
}
div[data-testid="opt_staff"] > button:hover {
  border-color: #3b82f6 !important;
  box-shadow: 0 4px 16px rgba(59,130,246,.15) !important;
  transform: translateX(3px) !important;
}
div[data-testid="opt_orgpatient"] > button {
  background: #f5f3ff !important; color: #0f172a !important;
  border: 1.5px solid #ddd6fe !important;
}
div[data-testid="opt_orgpatient"] > button:hover {
  border-color: #8b5cf6 !important;
  box-shadow: 0 4px 16px rgba(139,92,246,.15) !important;
  transform: translateX(3px) !important;
}
div[data-testid="opt_solo"] > button {
  background: #fffbeb !important; color: #0f172a !important;
  border: 1.5px solid #fde68a !important;
}
div[data-testid="opt_solo"] > button:hover {
  border-color: #f59e0b !important;
  box-shadow: 0 4px 16px rgba(245,158,11,.15) !important;
  transform: translateX(3px) !important;
}

/* ── primary button ── */
div.stButton > button[kind="primary"] {
  background: #0d9488 !important; color: white !important;
  border: none !important; border-radius: 9px !important;
  font-family: 'Sora', sans-serif !important; font-weight: 600 !important;
  font-size: 14px !important; width: 100%; padding: 11px 18px !important;
  box-shadow: 0 3px 12px rgba(13,148,136,.35) !important;
  transition: all .18s !important;
}
div.stButton > button[kind="primary"]:hover {
  background: #0f766e !important; transform: translateY(-1px) !important;
}

/* ── secondary button ── */
div.stButton > button[kind="secondary"] {
  background: white !important; color: #475569 !important;
  border: 1.5px solid #e2e8f0 !important; border-radius: 9px !important;
  font-family: 'Sora', sans-serif !important; font-weight: 600 !important;
  font-size: 14px !important; padding: 8px 16px !important;
  box-shadow: none !important; transition: all .18s !important;
}
div.stButton > button[kind="secondary"]:hover {
  border-color: #0d9488 !important; color: #0d9488 !important;
  background: white !important;
}

/* ── inputs ── */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
  background: #f8fafc !important;
  border: 1.5px solid #e2e8f0 !important;
  border-radius: 9px !important;
  font-family: 'Sora', sans-serif !important;
  font-size: 14px !important;
  color: #0f172a !important;
  padding: 10px 14px !important;
}

/* ── FIX INPUT LABEL VISIBILITY ── */
div[data-testid="stTextInput"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stSelectbox"] label {
  color: #0f172a !important;
  font-weight: 600 !important;
  font-size: 14px !important;
}

/* ── selectbox styling ── */
div[data-testid="stSelectbox"] > div > div {
  background: #f8fafc !important;
  border: 1.5px solid #e2e8f0 !important;
  border-radius: 9px !important;
}   

/* ── tabs ── */
/* tabs container */
div[data-baseweb="tab-list"] {
  background: #f1f5f9 !important;
  border-radius: 9px !important;
  padding: 3px !important;
}

/* tabs */
button[data-baseweb="tab"] {
  font-family: 'Sora', sans-serif !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  color: #64748b !important;
}

/* active tab */
button[data-baseweb="tab"][aria-selected="true"] {
  color: #0f172a !important;
  background: white !important;
}

/* ── radio pills ── */
div[data-testid="stRadio"] > div {
  display: flex !important; flex-direction: row !important;
  flex-wrap: wrap !important; gap: 8px !important;
}
div[data-testid="stRadio"] > div > label {
  padding: 7px 16px !important; border-radius: 999px !important;
  border: 1.5px solid #e2e8f0 !important; font-size: 13px !important;
  font-weight: 600 !important; cursor: pointer !important;
  background: transparent !important; color: #64748b !important;
  transition: all .2s !important; margin: 0 !important;
}
div[data-testid="stRadio"] > div > label:has(input:checked) {
  border-color: #3b82f6 !important; background: #eff6ff !important; color: #3b82f6 !important;
}
div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] { display: none !important; }

/* ── alerts ── */
div[data-testid="stAlert"] { border-radius: 9px !important; font-size: 13px !important; }

/* ── info / note boxes ── */
.hn-info {
  background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 10px;
  padding: 11px 14px; font-size: 13px; color: #166534; line-height: 1.6; margin-bottom: 16px;
}
.hn-note {
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 11px 14px; font-size: 12px; color: #64748b; line-height: 1.65; margin-top: 10px;
}

/* ── dashboard ── */
.hn-banner {
  border-radius: 12px; padding: 15px 18px; margin-bottom: 20px;
  border: 1.5px solid; font-size: 14px; color: #475569; line-height: 1.7;
}
.prof-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; background: #f8fafc; border-radius: 9px;
  margin-bottom: 7px; font-size: 14px;
}
.mem-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 13px; background: #f8fafc; border-radius: 10px; margin-bottom: 6px;
}
.mem-av {
  width: 34px; height: 34px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.stat-chip { border-radius: 12px; padding: 16px; text-align: center; margin-bottom: 12px; }

/* ── divider ── */
.divider-wrap {
  display: flex; align-items: center; gap: 10px; margin: 14px 0;
}
.divider-line { flex: 1; height: 1px; background: #e2e8f0; }
.divider-text { font-size: 11px; color: #94a3b8; }

/* ── footer ── */
.hn-footer {
  text-align: center; font-size: 11px; color: #94a3b8;
  padding: 18px 0 10px; border-top: 1px solid #e2e8f0; margin-top: 28px;
}
</style>
""", unsafe_allow_html=True)


# ── SHARED COMPONENTS ─────────────────────────────────────────────
def logo():
    st.markdown("""
    <div class="hn-logo">
      <div class="hn-logo-box">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
             stroke="white" stroke-width="2.5" stroke-linecap="round">
          <polyline points="2 12 6 12 8 4 10 20 12 12 14 16 16 12 22 12"/>
        </svg>
      </div>
      <span class="hn-logo-name">HealNet</span>
    </div>
    <p class="hn-tagline">AI Clinical Health Platform</p>
    """, unsafe_allow_html=True)

def footer():
    st.markdown("""
    <div class="hn-footer">
      A product made by <strong>IoTrenetics Solutions Pvt. Ltd.</strong>
    </div>
    """, unsafe_allow_html=True)

def portal_header(icon, bg, title, sub):
    st.markdown(f"""
    <div class="rp-portal-header">
      <div class="rp-portal-icon" style="background:{bg};">{icon}</div>
      <div>
        <div class="rp-portal-title">{title}</div>
        <div class="rp-portal-sub">{sub}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def back_btn():
    if st.button("← Back", key="back_btn", type="secondary"):
        go("entry"); st.rerun()

def divider(label=""):
    if label:
        st.markdown(f"""
        <div class="divider-wrap">
          <div class="divider-line"></div>
          <span class="divider-text">{label}</span>
          <div class="divider-line"></div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown('<div style="height:1px;background:#e2e8f0;margin:14px 0;"></div>',
                    unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# SCREEN: ENTRY
# ════════════════════════════════════════════════════════════════
def screen_entry():
    logo()
    st.markdown('<div class="hn-title">Who are you?</div>', unsafe_allow_html=True)
    st.markdown('<div class="hn-sub">Select how you\'d like to sign in.</div>',
                unsafe_allow_html=True)

    OPTIONS = [
        ("org",        "🏥  Organisation",
         "Hospital / Clinic  ·  Register your facility, manage staff & patients"),
        ("staff",      "👨‍⚕️  Doctor / Staff",
         "Needs Org Code  ·  You work at a registered hospital or clinic"),
        ("orgpatient", "🏨  Patient at a Hospital",
         "Needs Org Code  ·  Your hospital gave you a code to register"),
        ("solo",       "🧑  Individual / Personal",
         "No code needed ✓  ·  No hospital? Sign up free — no code, no hassle"),
    ]

    for key, title, sub in OPTIONS:
        if st.button(f"{title}\n{sub}", key=f"opt_{key}"):
            go(key); st.rerun()

    st.markdown("""
    <div class="hn-note">
      <strong style="color:#475569;">Not sure?</strong>
      If a hospital gave you a code → pick <em>Patient at a Hospital</em>.
      No code at all → pick <em>Individual / Personal</em>.
    </div>
    """, unsafe_allow_html=True)
    footer()


# ════════════════════════════════════════════════════════════════
# SCREEN: ORGANISATION
# ════════════════════════════════════════════════════════════════
def screen_org():
    back_btn()
    portal_header("🏥", "#f0fdfa", "Organisation Portal", "Hospital · Clinic · Healthcare Facility")
    show_msg()

    t1, t2 = st.tabs(["Sign In", "Register Org"])

    with t1:
        st.markdown("<br>", unsafe_allow_html=True)
        u = st.text_input("Username", placeholder="admin", key="ol_u")
        p = st.text_input("Password", type="password", placeholder="••••••••", key="ol_p")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sign In as Organisation", key="ol_btn", type="primary"):
            if not u or not p:
                alert("Please fill in all fields."); st.rerun()
            else:
                con = db()
                row = con.execute(
                    "SELECT * FROM organisations WHERE username=? AND password=?",
                    (u, hp(p))).fetchone()
                con.close()
                if row: do_login("org", org=dict(row)); st.rerun()
                else:   alert("Invalid username or password."); st.rerun()

    with t2:
        st.markdown("<br>", unsafe_allow_html=True)
        n   = st.text_input("Organisation Name", placeholder="City General Hospital", key="or_n")
        ru  = st.text_input("Username", placeholder="admin", key="or_u")
        rp  = st.text_input("Password", type="password", placeholder="••••••••", key="or_p")
        rp2 = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="or_p2")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Register Organisation", key="or_btn", type="primary"):
            if not all([n, ru, rp, rp2]):
                alert("All fields are required."); st.rerun()
            elif rp != rp2:
                alert("Passwords don't match."); st.rerun()
            elif len(rp) < 6:
                alert("Password must be at least 6 characters."); st.rerun()
            else:
                con = db()
                try:
                    code = gen_code()
                    con.execute(
                        "INSERT INTO organisations(name,username,password,org_code) VALUES(?,?,?,?)",
                        (n, ru, hp(rp), code))
                    con.commit()
                    alert(f"✅ Registered! Your Org Code is: {code}  —  share this with your staff and patients.", "success")
                except sqlite3.IntegrityError:
                    alert("Username already exists.")
                finally:
                    con.close()
                st.rerun()
    footer()


# ════════════════════════════════════════════════════════════════
# SCREEN: STAFF
# ════════════════════════════════════════════════════════════════
def screen_staff():
    back_btn()
    portal_header("👨‍⚕️", "#eff6ff", "Staff Portal", "Doctor · Nurse · Technician · Admin")
    show_msg()

    t1, t2 = st.tabs(["Sign In", "Create Account"])

    with t1:
        st.markdown("<br>", unsafe_allow_html=True)
        code = st.text_input("Organisation Code", placeholder="HN-XXXXX", key="sl_code",
                              help="Get this from your hospital admin")
        u    = st.text_input("Username", placeholder="dr.username", key="sl_u")
        p    = st.text_input("Password", type="password", placeholder="••••••••", key="sl_p")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sign In", key="sl_btn", type="primary"):
            if not all([code, u, p]):
                alert("All fields are required."); st.rerun()
            else:
                org = org_by_code(code)
                if not org:
                    alert("Invalid organisation code. Ask your admin."); st.rerun()
                else:
                    con = db()
                    row = con.execute(
                        "SELECT * FROM staff WHERE username=? AND password=? AND org_id=?",
                        (u, hp(p), org["id"])).fetchone()
                    con.close()
                    if row: do_login("staff", user=dict(row), org=org); st.rerun()
                    else:   alert("Invalid credentials."); st.rerun()

    with t2:
        st.markdown("<br>", unsafe_allow_html=True)
        rc  = st.text_input("Organisation Code", placeholder="HN-XXXXX", key="sr_code",
                             help="Get this from your hospital admin")
        rn  = st.text_input("Full Name", placeholder="Dr. Full Name", key="sr_name")
        st.markdown("**Role**")
        rr  = st.radio("Role", ["Doctor", "Nurse", "Technician", "Admin"],
                       key="sr_role", label_visibility="collapsed")
        rph = st.text_input("Phone (optional)", placeholder="+91 98765 43210", key="sr_phone")
        divider()
        ru  = st.text_input("Username", placeholder="dr.username", key="sr_u")
        rp  = st.text_input("Password", type="password", placeholder="••••••••", key="sr_p")
        rp2 = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="sr_p2")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Create Staff Account", key="sr_btn", type="primary"):
            if not all([rc, rn, ru, rp, rp2]):
                alert("Name, username and password are required."); st.rerun()
            elif rp != rp2:
                alert("Passwords don't match."); st.rerun()
            elif len(rp) < 6:
                alert("Password must be at least 6 characters."); st.rerun()
            else:
                org = org_by_code(rc)
                if not org:
                    alert("Invalid organisation code."); st.rerun()
                else:
                    con = db()
                    count = con.execute("SELECT COUNT(*) FROM staff WHERE org_id=?",
                                        (org["id"],)).fetchone()[0]
                    sid = rr[:2].upper() + "-" + str(count + 1).zfill(4)
                    try:
                        con.execute(
                            "INSERT INTO staff(org_id,name,username,password,role,phone,staff_id) VALUES(?,?,?,?,?,?,?)",
                            (org["id"], rn, ru, hp(rp), rr, rph, sid))
                        con.commit()
                        alert(f"✅ Account created! Your Staff ID is {sid}. You can now sign in.", "success")
                    except sqlite3.IntegrityError:
                        alert("Username already exists in this organisation.")
                    finally:
                        con.close()
                    st.rerun()
    footer()


# ════════════════════════════════════════════════════════════════
# SCREEN: HOSPITAL PATIENT
# ════════════════════════════════════════════════════════════════
def screen_orgpatient():
    back_btn()
    portal_header("🏨", "#f5f3ff", "Patient Portal", "Registered under a hospital or clinic")
    show_msg()

    t1, t2 = st.tabs(["Sign In", "Register"])

    with t1:
        st.markdown("<br>", unsafe_allow_html=True)
        code = st.text_input("Organisation Code", placeholder="HN-XXXXX", key="opl_code",
                              help="Get this from your hospital or doctor's office")
        u    = st.text_input("Username", placeholder="yourname", key="opl_u")
        p    = st.text_input("Password", type="password", placeholder="••••••••", key="opl_p")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sign In", key="opl_btn", type="primary"):
            if not all([code, u, p]):
                alert("All fields are required."); st.rerun()
            else:
                org = org_by_code(code)
                if not org:
                    alert("Invalid organisation code."); st.rerun()
                else:
                    con = db()
                    row = con.execute(
                        "SELECT * FROM org_patients WHERE username=? AND password=? AND org_id=?",
                        (u, hp(p), org["id"])).fetchone()
                    con.close()
                    if row: do_login("orgpatient", user=dict(row), org=org); st.rerun()
                    else:   alert("Invalid credentials."); st.rerun()

    with t2:
        st.markdown("<br>", unsafe_allow_html=True)
        rc   = st.text_input("Organisation Code", placeholder="HN-XXXXX", key="opr_code",
                              help="Get this from your hospital reception or admin")
        rn   = st.text_input("Full Name", placeholder="Your full name", key="opr_name")
        c1, c2 = st.columns(2)
        with c1: ra  = st.number_input("Age", 1, 120, 25, key="opr_age")
        with c2: rg  = st.selectbox("Gender", ["Female", "Male", "Other"], key="opr_gender")
        rct  = st.text_input("Contact Number", placeholder="+91 98765 43210", key="opr_contact")
        divider()
        ru   = st.text_input("Username", placeholder="yourname", key="opr_u")
        rp   = st.text_input("Password", type="password", placeholder="••••••••", key="opr_p")
        rp2  = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="opr_p2")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Register as Patient", key="opr_btn", type="primary"):
            if not all([rc, rn, ru, rp, rp2]):
                alert("Name, username and password are required."); st.rerun()
            elif rp != rp2:
                alert("Passwords don't match."); st.rerun()
            elif len(rp) < 6:
                alert("Password must be at least 6 characters."); st.rerun()
            else:
                org = org_by_code(rc)
                if not org:
                    alert("Invalid organisation code."); st.rerun()
                else:
                    con = db()
                    count = con.execute("SELECT COUNT(*) FROM org_patients WHERE org_id=?",
                                        (org["id"],)).fetchone()[0]
                    pid = "PT-" + str(count + 1).zfill(4)
                    try:
                        con.execute(
                            "INSERT INTO org_patients(org_id,name,username,password,age,gender,contact,patient_id) VALUES(?,?,?,?,?,?,?,?)",
                            (org["id"], rn, ru, hp(rp), ra, rg, rct, pid))
                        con.commit()
                        alert(f"✅ Registered! Your Patient ID is {pid}. You can now sign in.", "success")
                    except sqlite3.IntegrityError:
                        alert("Username already exists.")
                    finally:
                        con.close()
                    st.rerun()
    footer()


# ════════════════════════════════════════════════════════════════
# SCREEN: INDIVIDUAL — no org code
# ════════════════════════════════════════════════════════════════
def screen_solo():
    back_btn()
    portal_header("🧑", "#fffbeb", "Personal Account", "No hospital or organisation needed")

    st.markdown("""
    <div class="hn-info">
      <strong>You're in the right place.</strong>
      Create a free personal account with just your name and email —
      no hospital, no code, no referral needed.
    </div>
    """, unsafe_allow_html=True)

    show_msg()

    t1, t2 = st.tabs(["Sign In", "Create Account"])

    with t1:
        st.markdown("<br>", unsafe_allow_html=True)
        u = st.text_input("Username", placeholder="your username", key="solo_l_u")
        p = st.text_input("Password", type="password", placeholder="••••••••", key="solo_l_p")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sign In", key="solo_l_btn", type="primary"):
            if not all([u, p]):
                alert("Please enter username and password."); st.rerun()
            else:
                con = db()
                row = con.execute(
                    "SELECT * FROM solo_users WHERE username=? AND password=?",
                    (u, hp(p))).fetchone()
                con.close()
                if row:
                    do_login("solo", user=dict(row),
                             org={"name": "HealNet Personal", "org_code": "PERSONAL"})
                    st.rerun()
                else:
                    alert("No account found. Register using the Create Account tab."); st.rerun()

    with t2:
        st.markdown("<br>", unsafe_allow_html=True)
        rn  = st.text_input("Full Name *", placeholder="Your full name", key="solo_r_name")
        re  = st.text_input("Email Address *", placeholder="you@example.com", key="solo_r_email")
        c1, c2 = st.columns(2)
        with c1: rg  = st.selectbox("Gender", ["Female", "Male", "Other"], key="solo_r_gender")
        with c2: rd  = st.text_input("Date of Birth", placeholder="DD/MM/YYYY", key="solo_r_dob")
        c3, c4 = st.columns(2)
        with c3: rb  = st.text_input("Blood Group", placeholder="e.g. O+", key="solo_r_blood")
        with c4: rph = st.text_input("Phone", placeholder="+91 98765 43210", key="solo_r_phone")
        divider("Set your login credentials")
        ru  = st.text_input("Username *", placeholder="choose a username", key="solo_r_u")
        rp  = st.text_input("Password *", type="password", placeholder="••••••••", key="solo_r_p")
        rp2 = st.text_input("Confirm Password *", type="password", placeholder="••••••••", key="solo_r_p2")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Create My Free Account", key="solo_r_btn", type="primary"):
            if not all([rn, re, ru, rp, rp2]):
                alert("Name, email, username and password are required."); st.rerun()
            elif "@" not in re or "." not in re:
                alert("Please enter a valid email address."); st.rerun()
            elif rp != rp2:
                alert("Passwords don't match."); st.rerun()
            elif len(rp) < 6:
                alert("Password must be at least 6 characters."); st.rerun()
            else:
                con = db()
                count = con.execute("SELECT COUNT(*) FROM solo_users").fetchone()[0]
                hid = "HN-" + str(count + 1).zfill(5)
                try:
                    con.execute(
                        "INSERT INTO solo_users(name,email,username,password,gender,dob,blood,contact,healnet_id) VALUES(?,?,?,?,?,?,?,?,?)",
                        (rn, re, ru, hp(rp), rg, rd, rb, rph, hid))
                    con.commit()
                    alert(f"✅ Account created! Your HealNet ID is {hid}. Switch to Sign In to log in.", "success")
                except sqlite3.IntegrityError:
                    alert("Email or username already registered.")
                finally:
                    con.close()
                st.rerun()
    footer()


# ════════════════════════════════════════════════════════════════
# SCREEN: DASHBOARD
# ════════════════════════════════════════════════════════════════
def screen_dashboard():
    sess = st.session_state.session
    kind = sess["kind"]
    user = sess.get("user") or {}
    org  = sess.get("org")  or {}

    COLORS = {
        "org":        ("#0d9488", "#f0fdfa"),
        "staff":      ("#3b82f6", "#eff6ff"),
        "orgpatient": ("#8b5cf6", "#f5f3ff"),
        "solo":       ("#f59e0b", "#fffbeb"),
    }
    ICONS  = {"org":"🏥","staff":"👨‍⚕️","orgpatient":"🏨","solo":"🧑"}
    color, bg = COLORS[kind]
    icon = ICONS[kind]

    display_name = org.get("name","") if kind == "org" else user.get("name","")
    id_line = {
        "org":        f"Admin  ·  {org.get('org_code','')}",
        "staff":      f"{user.get('role','')}  ·  {user.get('staff_id','')}",
        "orgpatient": f"Patient  ·  {user.get('patient_id','')}",
        "solo":       f"Personal Account  ·  {user.get('healnet_id','')}",
    }[kind]

    hc1, hc2 = st.columns([5, 1])
    with hc1:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
          <span style="font-size:26px;background:{bg};border-radius:11px;
            width:48px;height:48px;display:flex;align-items:center;justify-content:center;">{icon}</span>
          <div>
            <div style="font-size:16px;font-weight:700;color:#0f172a;">{display_name}</div>
            <div style="font-size:12px;color:{color};font-weight:600;">{id_line}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    with hc2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sign out", key="logout", type="secondary"):
            st.session_state.session = None
            go("entry"); st.rerun()

    banners = {
        "org":        f'Your org code is <code style="background:white;padding:2px 8px;border-radius:6px;color:{color};font-weight:700;">{org.get("org_code","")}</code>. Share this with your staff and patients.',
        "staff":      f'Signed in as <strong>{user.get("role","")}</strong> at <strong>{org.get("name","")}</strong>. Staff ID: <code style="background:white;padding:2px 8px;border-radius:6px;color:{color};font-weight:700;">{user.get("staff_id","")}</code>',
        "orgpatient": f'Registered at <strong>{org.get("name","")}</strong>. Patient ID: <code style="background:white;padding:2px 8px;border-radius:6px;color:{color};font-weight:700;">{user.get("patient_id","")}</code>',
        "solo":       f'Welcome, <strong>{user.get("name","")}</strong>. HealNet ID: <code style="background:white;padding:2px 8px;border-radius:6px;color:{color};font-weight:700;">{user.get("healnet_id","")}</code>',
    }
    st.markdown(f"""
    <div class="hn-banner" style="background:linear-gradient(135deg,{bg},white);border-color:{color}22;">
      {banners[kind]}
    </div>
    """, unsafe_allow_html=True)

    if kind == "org":
        con = db()
        sl = [dict(r) for r in con.execute("SELECT * FROM staff WHERE org_id=?",        (org["id"],)).fetchall()]
        pl = [dict(r) for r in con.execute("SELECT * FROM org_patients WHERE org_id=?", (org["id"],)).fetchall()]
        con.close()

        sc1, sc2 = st.columns(2)
        with sc1:
            st.markdown(f'<div class="stat-chip" style="background:#eff6ff;"><div style="font-size:28px;font-weight:700;color:#3b82f6;">{len(sl)}</div><div style="font-size:11px;color:#64748b;">Staff Members</div></div>', unsafe_allow_html=True)
        with sc2:
            st.markdown(f'<div class="stat-chip" style="background:#f5f3ff;"><div style="font-size:28px;font-weight:700;color:#8b5cf6;">{len(pl)}</div><div style="font-size:11px;color:#64748b;">Patients</div></div>', unsafe_allow_html=True)

        if sl:
            st.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin:4px 0 8px;">Staff</div>', unsafe_allow_html=True)
            for s in sl:
                st.markdown(f'<div class="mem-row"><div class="mem-av" style="background:#dbeafe;color:#3b82f6;">{s["name"][:2].upper()}</div><div><div style="font-size:13px;font-weight:600;color:#0f172a;">{s["name"]}</div><div style="font-size:11px;color:#64748b;">{s["role"]} · {s["staff_id"]}</div></div></div>', unsafe_allow_html=True)

        if pl:
            st.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin:12px 0 8px;">Patients</div>', unsafe_allow_html=True)
            for p in pl:
                st.markdown(f'<div class="mem-row"><div class="mem-av" style="background:#ede9fe;color:#8b5cf6;">{p["name"][:2].upper()}</div><div><div style="font-size:13px;font-weight:600;color:#0f172a;">{p["name"]}</div><div style="font-size:11px;color:#64748b;">{p["patient_id"]} · Age {p["age"]} · {p["gender"]}</div></div></div>', unsafe_allow_html=True)

        if not sl and not pl:
            st.markdown(f'<div style="text-align:center;padding:32px;color:#94a3b8;font-size:13px;">No members yet. Share code <strong style="color:#0d9488;">{org.get("org_code","")}</strong> to get started.</div>', unsafe_allow_html=True)

    else:
        rows = {
            "solo":       [("Email",user.get("email","")),("Gender",user.get("gender","")),("Date of Birth",user.get("dob") or "—"),("Blood Group",user.get("blood") or "—"),("Phone",user.get("contact") or "—")],
            "orgpatient": [("Age",user.get("age","")),("Gender",user.get("gender","")),("Contact",user.get("contact") or "—"),("Hospital",org.get("name",""))],
            "staff":      [("Role",user.get("role","")),("Staff ID",user.get("staff_id","")),("Phone",user.get("phone") or "—"),("Organisation",org.get("name",""))],
        }.get(kind, [])
        for k, v in rows:
            st.markdown(f'<div class="prof-row"><span style="color:#64748b;">{k}</span><span style="font-weight:600;color:#0f172a;">{v}</span></div>', unsafe_allow_html=True)

    footer()


# ════════════════════════════════════════════════════════════════
# ROUTER
# ════════════════════════════════════════════════════════════════
SCREENS = {
    "entry":      screen_entry,
    "org":        screen_org,
    "staff":      screen_staff,
    "orgpatient": screen_orgpatient,
    "solo":       screen_solo,
    "dashboard":  screen_dashboard,
}

SCREENS.get(st.session_state.screen, screen_entry)()

