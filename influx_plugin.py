"""
influx_plugin.py — HealNet AI · Vitals I/O Layer
=================================================
Replaces direct InfluxDB dependency with a multi-source vitals engine:

    Priority 1: Real IoT device data (Supabase vitals_readings, source='iot')
    Priority 2: Camera-derived data  (source='camera')
    Priority 3: Manual / simulated   (source='manual')

If Supabase is active, `get_vitals()` polls the latest row from
`vitals_readings` for the given patient — enabling real IoT devices to
push data and have it appear live in the dashboard.

`write_vitals()` persists a reading via patient_db.save_vitals_reading()
so all data ends up in one place regardless of source.

Environment variables:
    SUPABASE_URL / SUPABASE_KEY  — handled by patient_db; no extra config needed
    IOT_POLL_SECONDS             — how stale a DB reading can be before falling
                                   back to simulation (default: 30)
"""

from __future__ import annotations

import os
import time
import random
import datetime
import logging
from typing import Optional

logger = logging.getLogger("healnet.influx_plugin")

# Pull the backend helpers from patient_db
from patient_db import (
    save_vitals_reading,
    get_vitals_history,
    get_backend_info,
    _USE_SUPABASE,          # private — intentional; avoids re-checking env
)

_IOT_STALE_SECONDS = int(os.getenv("IOT_POLL_SECONDS", "30"))


# ──────────────────────────────────────────────────────────────────────────────
# Vital field registry
#   name          → (display_label, unit, sim_range, round_digits)
# ──────────────────────────────────────────────────────────────────────────────
VITAL_FIELDS = {
    "heart_rate":       ("Heart Rate",        "bpm",  (55, 105),  0),
    "spo2":             ("SpO₂",              "%",    (92, 100),  1),
    "systolic_bp":      ("Systolic BP",       "mmHg", (90, 160),  0),
    "diastolic_bp":     ("Diastolic BP",      "mmHg", (60, 100),  0),
    "temperature":      ("Temperature",       "°C",   (36.0, 38.5), 1),
    "blood_sugar":      ("Blood Sugar",       "mg/dL",(70, 180),  0),
    "respiratory_rate": ("Respiratory Rate",  "rpm",  (12, 22),   0),
    "bmi":              ("BMI",               "kg/m²",(18.5, 35.0), 1),
}


# ──────────────────────────────────────────────────────────────────────────────
# Internal state (per patient, in-memory for simulation continuity)
# ──────────────────────────────────────────────────────────────────────────────
_sim_state: dict[str, dict] = {}  # patient_id → {field: last_value}


def _sim_value(patient_id: str, field: str) -> float:
    """Generate a smoothly drifting simulated vital value."""
    _, _, (lo, hi), digits = VITAL_FIELDS[field]
    state = _sim_state.setdefault(patient_id, {})
    prev  = state.get(field, (lo + hi) / 2)
    delta = (hi - lo) * 0.03 * random.gauss(0, 1)
    new   = max(lo - (hi - lo) * 0.05, min(hi + (hi - lo) * 0.05, prev + delta))
    state[field] = new
    return round(new, digits)


def _row_to_vitals(row: dict) -> dict:
    """Convert a vitals_readings DB row to the format expected by the UI."""
    out = {}
    for field in VITAL_FIELDS:
        val = row.get(field)
        if val is not None:
            try:
                _, _, _, digits = VITAL_FIELDS[field]
                out[field] = round(float(val), digits)
            except (TypeError, ValueError):
                pass
    return out


def _is_fresh(row: dict) -> bool:
    """Return True if the row's recorded_at is within IOT_STALE_SECONDS."""
    ts_str = row.get("recorded_at", "")
    if not ts_str:
        return False
    try:
        # Handle both timezone-aware and naive ISO strings
        ts_str = ts_str.replace("Z", "+00:00")
        ts = datetime.datetime.fromisoformat(ts_str)
        # Make naive for comparison
        if ts.tzinfo is not None:
            now = datetime.datetime.now(tz=datetime.timezone.utc)
        else:
            now = datetime.datetime.utcnow()
        age = (now - ts).total_seconds()
        return age <= _IOT_STALE_SECONDS
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def get_vitals(patient_id: str) -> dict:
    """
    Return the latest vitals dict for *patient_id*.

    Fetch order:
      1. Supabase → latest IoT row (source='iot'), if fresh
      2. Supabase → latest row (any source), if fresh
      3. Simulation (smooth drift)

    The returned dict has exactly the keys in VITAL_FIELDS, e.g.
        { "heart_rate": 72, "spo2": 98.5, ... }
    """
    if _USE_SUPABASE:
        history = get_vitals_history(patient_id, limit=1)
        if history:
            row = history[0]
            if _is_fresh(row):
                vitals = _row_to_vitals(row)
                if vitals:
                    source = row.get("source", "db")
                    logger.debug("vitals from DB (%s) for %s", source, patient_id)
                    return vitals

    # Fall back to simulation
    return {field: _sim_value(patient_id, field) for field in VITAL_FIELDS}


def write_vitals(
    patient_id: str,
    vitals: dict,
    source: str = "manual",
    device_id: str = None,
) -> bool:
    """
    Persist a vitals snapshot.

    Parameters
    ----------
    patient_id : str
    vitals     : dict with any subset of VITAL_FIELDS keys
    source     : 'manual' | 'iot' | 'camera'
    device_id  : IoT device identifier (optional)

    Returns True on success.
    """
    # Update sim state so subsequent get_vitals() stays coherent
    _sim_state.setdefault(patient_id, {}).update(vitals)

    ok, err = save_vitals_reading(
        patient_id=patient_id,
        heart_rate=vitals.get("heart_rate"),
        spo2=vitals.get("spo2"),
        systolic_bp=vitals.get("systolic_bp"),
        diastolic_bp=vitals.get("diastolic_bp"),
        temperature=vitals.get("temperature"),
        blood_sugar=vitals.get("blood_sugar"),
        respiratory_rate=vitals.get("respiratory_rate"),
        bmi=vitals.get("bmi"),
        device_id=device_id,
        source=source,
    )
    if not ok:
        logger.warning("write_vitals failed for %s: %s", patient_id, err)
    return ok


def get_vitals_dataframe(patient_id: str, limit: int = 200):
    """
    Return a pandas DataFrame of historical vitals for charting.
    Columns: recorded_at + all VITAL_FIELDS keys.
    """
    import pandas as pd
    rows = get_vitals_history(patient_id, limit=limit)
    if not rows:
        return pd.DataFrame(columns=["recorded_at"] + list(VITAL_FIELDS.keys()))
    df = pd.DataFrame(rows)
    df["recorded_at"] = pd.to_datetime(df["recorded_at"], utc=True, errors="coerce")
    df = df.sort_values("recorded_at")
    # Coerce numeric fields
    for field in VITAL_FIELDS:
        if field in df.columns:
            df[field] = pd.to_numeric(df[field], errors="coerce")
    return df


def get_source_breakdown(patient_id: str) -> dict:
    """
    Return count of readings per source for a patient.
    Useful for an IoT diagnostics panel.
    """
    rows = get_vitals_history(patient_id, limit=1000)
    breakdown: dict[str, int] = {}
    for r in rows:
        src = r.get("source", "unknown")
        breakdown[src] = breakdown.get(src, 0) + 1
    return breakdown


def get_latest_device_reading(patient_id: str) -> Optional[dict]:
    """
    Return the most recent IoT device reading, or None.
    Useful for showing a "Last device sync" timestamp.
    """
    rows = get_vitals_history(patient_id, limit=5, source="iot")
    return rows[0] if rows else None
