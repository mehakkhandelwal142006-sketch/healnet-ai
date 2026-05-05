"""
auth_db.py — HealNet AI · Authentication & Session Layer
=========================================================
Manages user accounts and session tokens.

Backend: Supabase (users table) with bcrypt password hashing.
Fallback: SQLite with the same schema.

Tables
------
  users
    id          UUID / TEXT PK
    email       TEXT UNIQUE
    name        TEXT
    kind        TEXT  ('solo' | 'org' | 'staff' | 'orgpatient')
    org_id      TEXT  (NULL for solo / org accounts)
    password_hash TEXT
    created_at  TIMESTAMPTZ
    last_login  TIMESTAMPTZ

  sessions  (optional — for multi-device SSO; Streamlit uses session_state)

Environment variables:
    SUPABASE_URL / SUPABASE_KEY  (same as patient_db)
    SECRET_KEY                   (used for HMAC token signing; set something strong)
"""

from __future__ import annotations

import os
import sqlite3
import datetime
import hashlib
import hmac
import uuid
import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger("healnet.auth_db")

# ─── bcrypt with graceful fallback ───────────────────────────────────────────
try:
    import bcrypt
    def _hash_password(pw: str) -> str:
        return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    def _check_password(pw: str, hashed: str) -> bool:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    _BCRYPT = True
except ImportError:
    import hashlib
    _BCRYPT = False
    _SECRET = os.getenv("SECRET_KEY", "healnet-change-me-in-production")
    def _hash_password(pw: str) -> str:  # type: ignore[misc]
        return hashlib.sha256(f"{pw}{_SECRET}".encode()).hexdigest()
    def _check_password(pw: str, hashed: str) -> bool:  # type: ignore[misc]
        return hmac.compare_digest(_hash_password(pw), hashed)

# ─── Backend selection (mirrors patient_db) ──────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
FORCE_SQLITE = os.getenv("DB_FALLBACK", "0") == "1"

_USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY and not FORCE_SQLITE)
_sb = None

if _USE_SUPABASE:
    try:
        from supabase import create_client
        _sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as exc:
        logger.warning("auth_db Supabase init failed: %s", exc)
        _USE_SUPABASE = False

_SQLITE_DB = os.path.join(os.path.dirname(__file__), "healnet.db")

# ─── SQLite helpers ──────────────────────────────────────────────────────────
@contextmanager
def _conn():
    c = sqlite3.connect(_SQLITE_DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

_USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    name          TEXT,
    kind          TEXT DEFAULT 'solo',
    org_id        TEXT,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now')),
    last_login    TEXT
);
"""

# ─── Supabase SQL (run once in SQL editor) ───────────────────────────────────
SUPABASE_USERS_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    name          TEXT,
    kind          TEXT DEFAULT 'solo',
    org_id        TEXT,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now(),
    last_login    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS users_email_idx ON users(email);
"""


def init_auth_tables():
    """Create auth tables if using SQLite (Supabase tables are migration-managed)."""
    if not _USE_SUPABASE:
        with _conn() as c:
            c.execute(_USERS_DDL)


# ─── Core auth functions ─────────────────────────────────────────────────────

def register_user(
    email: str,
    password: str,
    name: str = "",
    kind: str = "solo",
    org_id: str = None,
) -> tuple[bool, str]:
    """
    Create a new user.  Returns (success, error_message).
    """
    uid = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    pw_hash = _hash_password(password)
    row = {
        "id": uid,
        "email": email.strip().lower(),
        "name": name.strip(),
        "kind": kind,
        "org_id": org_id,
        "password_hash": pw_hash,
        "created_at": now,
    }

    if _USE_SUPABASE:
        try:
            _sb.table("users").insert(row).execute()
            return True, ""
        except Exception as exc:
            msg = str(exc)
            if "duplicate" in msg.lower() or "unique" in msg.lower():
                return False, "An account with this email already exists."
            return False, msg
    else:
        try:
            with _conn() as c:
                cols = ", ".join(row.keys())
                ph   = ", ".join(["?"] * len(row))
                c.execute(f"INSERT INTO users ({cols}) VALUES ({ph})", list(row.values()))
            return True, ""
        except sqlite3.IntegrityError:
            return False, "An account with this email already exists."
        except Exception as exc:
            return False, str(exc)


def login_user(email: str, password: str) -> tuple[Optional[dict], str]:
    """
    Authenticate a user.
    Returns (session_dict, error_message).

    session_dict looks like:
        {
            "user": {"id": ..., "name": ..., "email": ..., "kind": ...},
            "org":  {},          # populated for org/staff accounts
            "kind": "solo",
        }
    """
    email = email.strip().lower()

    if _USE_SUPABASE:
        try:
            res = (
                _sb.table("users")
                .select("*")
                .eq("email", email)
                .limit(1)
                .execute()
            )
            rows = res.data or []
        except Exception as exc:
            return None, f"Database error: {exc}"
    else:
        with _conn() as c:
            row = c.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        rows = [dict(row)] if row else []

    if not rows:
        return None, "No account found with this email."

    user = rows[0]
    if not _check_password(password, user["password_hash"]):
        return None, "Incorrect password."

    # Update last_login
    _touch_last_login(user["id"])

    session = {
        "user": {
            "id":    user["id"],
            "name":  user.get("name", ""),
            "email": user["email"],
            "kind":  user.get("kind", "solo"),
        },
        "org":  {},
        "kind": user.get("kind", "solo"),
    }
    return session, ""


def _touch_last_login(user_id: str):
    now = datetime.datetime.utcnow().isoformat()
    if _USE_SUPABASE:
        try:
            _sb.table("users").update({"last_login": now}).eq("id", user_id).execute()
        except Exception:
            pass
    else:
        with _conn() as c:
            c.execute("UPDATE users SET last_login=? WHERE id=?", (now, user_id))


def change_password(user_id: str, old_pw: str, new_pw: str) -> tuple[bool, str]:
    """Change password after verifying the old one."""
    # Fetch current hash
    if _USE_SUPABASE:
        try:
            res = _sb.table("users").select("password_hash").eq("id", user_id).limit(1).execute()
            rows = res.data or []
        except Exception as exc:
            return False, str(exc)
    else:
        with _conn() as c:
            row = c.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
        rows = [dict(row)] if row else []

    if not rows:
        return False, "User not found."
    if not _check_password(old_pw, rows[0]["password_hash"]):
        return False, "Current password is incorrect."

    new_hash = _hash_password(new_pw)
    if _USE_SUPABASE:
        try:
            _sb.table("users").update({"password_hash": new_hash}).eq("id", user_id).execute()
            return True, ""
        except Exception as exc:
            return False, str(exc)
    else:
        with _conn() as c:
            c.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user_id))
        return True, ""


def get_user_by_id(user_id: str) -> Optional[dict]:
    if _USE_SUPABASE:
        try:
            res = _sb.table("users").select("id,name,email,kind,org_id,created_at,last_login").eq("id", user_id).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception:
            return None
    else:
        with _conn() as c:
            row = c.execute(
                "SELECT id,name,email,kind,org_id,created_at,last_login FROM users WHERE id=?",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None
