"""
realtime_engine.py — HealNet AI · Real-Time Monitoring Engine
=============================================================
Provides RealTimeEngine — a thin wrapper that:

  1. Calls influx_plugin.get_vitals()  (Supabase → simulation)
  2. Runs vital classification via vital_ranges
  3. Persists each reading via influx_plugin.write_vitals()
  4. Persists critical/warning alerts via patient_db.save_alert()
  5. Returns structured monitoring_result for the UI

IoT integration points
----------------------
  • IoT devices push rows to Supabase `vitals_readings` (source='iot')
  • RealTimeEngine.tick() picks them up automatically on the next poll
  • Device heartbeat / last-seen is tracked via influx_plugin.get_latest_device_reading()

Usage (from app.py)
-------------------
    engine = RealTimeEngine(patient_id, patient_name)
    result = engine.tick()
    # result["vitals"]          → dict of current values
    # result["classified"]      → dict name→(value, level, message)
    # result["critical_alerts"] → list of alert dicts
    # result["warning_alerts"]  → list of alert dicts
    # result["source"]          → 'iot' | 'manual' | 'camera'
    # result["device_id"]       → str | None
"""

from __future__ import annotations

import time
import datetime
import logging
from typing import Optional

logger = logging.getLogger("healnet.realtime_engine")


class RealTimeEngine:
    """Per-patient monitoring engine."""

    def __init__(
        self,
        patient_id: str,
        patient_name: str,
        persist_every: int = 5,    # save a vitals row every N ticks
        alert_cooldown: int = 300, # seconds between repeat email alerts
    ):
        self.patient_id   = patient_id
        self.patient_name = patient_name
        self.persist_every = persist_every
        self.alert_cooldown = alert_cooldown

        self._tick_count   = 0
        self._last_alert_t: dict[str, float] = {}  # vital → epoch

    # ------------------------------------------------------------------
    def tick(self) -> dict:
        """
        Run one monitoring cycle.

        Returns
        -------
        dict with keys:
            vitals, classified, critical_alerts, warning_alerts,
            source, device_id, timestamp
        """
        from influx_plugin import get_vitals, write_vitals, get_latest_device_reading
        from vital_ranges import (
            classify_bp, classify_heart_rate, classify_spo2,
            classify_blood_sugar, classify_temperature,
            classify_respiratory_rate, classify_bmi,
        )
        from patient_db import save_alert

        self._tick_count += 1
        now_str = datetime.datetime.now().strftime("%d %b %Y, %I:%M:%S %p")

        # 1. Fetch vitals (IoT → simulation)
        vitals = get_vitals(self.patient_id)

        # Determine source (peek at latest DB row)
        device_info = get_latest_device_reading(self.patient_id)
        if device_info:
            source    = device_info.get("source", "manual")
            device_id = device_info.get("device_id")
        else:
            source    = "manual"
            device_id = None

        # 2. Classify each vital
        sys_bp = vitals.get("systolic_bp", 120)
        dia_bp = vitals.get("diastolic_bp", 80)
        bp_level, bp_msg = classify_bp(sys_bp, dia_bp)

        classified: dict[str, tuple] = {
            "Blood Pressure":    (f"{sys_bp}/{dia_bp}", bp_level, bp_msg),
            "Heart Rate":        _cls(vitals, "heart_rate",       classify_heart_rate),
            "SpO₂":              _cls(vitals, "spo2",             classify_spo2),
            "Blood Sugar":       _cls(vitals, "blood_sugar",      classify_blood_sugar),
            "Temperature":       _cls(vitals, "temperature",      classify_temperature),
            "Respiratory Rate":  _cls(vitals, "respiratory_rate", classify_respiratory_rate),
            "BMI":               _cls(vitals, "bmi",              classify_bmi),
        }

        # 3. Split into critical / warning
        critical_alerts, warning_alerts = [], []
        for vital_name, (val, level, msg) in classified.items():
            entry = {"vital": vital_name, "value": val, "level": level, "message": msg}
            if level in ("CRITICAL", "HIGH"):
                critical_alerts.append({**entry, "category": "Critical"})
            elif level in ("MODERATE", "LOW"):
                warning_alerts.append({**entry, "category": "Warning"})

        # 4. Persist vitals (throttled)
        if self._tick_count % self.persist_every == 0:
            write_vitals(
                patient_id=self.patient_id,
                vitals=vitals,
                source=source,
                device_id=device_id,
            )

        # 5. Persist new alerts (with cooldown per vital)
        now_epoch = time.time()
        for alert in critical_alerts + warning_alerts:
            vn = alert["vital"]
            last_t = self._last_alert_t.get(vn, 0)
            if now_epoch - last_t >= self.alert_cooldown:
                save_alert(
                    patient_id=self.patient_id,
                    patient_name=self.patient_name,
                    vital=vn,
                    value=str(alert["value"]),
                    level=alert["level"],
                    category=alert["category"],
                    message=alert["message"],
                    device_id=device_id,
                )
                self._last_alert_t[vn] = now_epoch

        return {
            "vitals":          vitals,
            "classified":      classified,
            "critical_alerts": critical_alerts,
            "warning_alerts":  warning_alerts,
            "source":          source,
            "device_id":       device_id,
            "timestamp":       now_str,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _cls(vitals: dict, field: str, fn) -> tuple:
    """Call a single-argument classify function safely."""
    val = vitals.get(field)
    if val is None:
        return ("—", "NORMAL", "No reading")
    try:
        level, msg = fn(val)
        return (val, level, msg)
    except Exception as exc:
        logger.warning("classify error for %s: %s", field, exc)
        return (val, "NORMAL", "")
