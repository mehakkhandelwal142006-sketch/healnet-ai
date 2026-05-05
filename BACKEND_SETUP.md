# HealNet AI — Backend Setup & Integration Guide

## What Was Changed

| File | Before | After |
|------|--------|-------|
| `patient_db.py` | SQLite only, no IoT hooks | **Supabase primary + SQLite fallback, IoT-ready** |
| `influx_plugin.py` | InfluxDB dependency | **Supabase polling + smooth simulation fallback** |
| `realtime_engine.py` | In-memory alerts only | **Persists vitals & alerts to DB every 5 ticks** |
| `auth_db.py` | *(new)* | **Supabase/SQLite user auth with bcrypt** |
| `iot_device_client.py` | *(new)* | **Reference client for ESP32 / Raspberry Pi** |
| `supabase_migration.sql` | *(new)* | **One-shot schema for Supabase SQL editor** |

---

## Step 1 — Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) → **New Project**
2. Note your **Project URL** and **anon/service-role key**  
   *(Settings → API → Project URL + API Keys)*

---

## Step 2 — Run the Migration

Open **SQL Editor** in your Supabase dashboard and paste the entire contents of `supabase_migration.sql`, then click **Run**.

This creates:
- `users` — authentication
- `patients` — patient records
- `vitals_readings` — all vitals (manual + IoT + camera)
- `alert_log` — persistent alert history
- `iot_devices` — device registry

---

## Step 3 — Configure Environment Variables

### Local development
```bash
cp .env.example .env
# Edit .env with your Supabase URL and key
```

Then load it at runtime:
```python
from dotenv import load_dotenv
load_dotenv()   # add this at the top of app.py
```

### Streamlit Cloud
Go to **App settings → Secrets** and add:
```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-service-role-key"
SECRET_KEY   = "long-random-string"
```

---

## Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 5 — Update app.py Imports

The three replaced modules (`patient_db`, `influx_plugin`, `realtime_engine`) have **identical public APIs** — no changes needed in `app.py`.

The only addition needed is alert persistence. In `check_and_alert()` in `app.py`, after building `critical_alerts + warning_alerts`, add:

```python
from patient_db import save_alert

for a in critical_alerts + warning_alerts:
    save_alert(
        patient_id=patient_id,
        patient_name=patient_name,
        vital=a["vital"],
        value=str(a["value"]),
        level=a["level"],
        category=a["category"],
        message=a["message"],
        email_sent=(email_sent if a["category"] == "Critical" else False),
    )
```

And to load the alert log from the database instead of session state:
```python
from patient_db import get_alert_log
alert_log = get_alert_log(limit=300)   # replaces st.session_state["alert_log"]
```

---

## IoT Device Integration

### How it works
Any IoT device with network access can push vitals by sending a **single HTTP POST**:

```bash
curl -X POST https://YOUR_PROJECT.supabase.co/rest/v1/vitals_readings \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "P001",
    "device_id":  "RPi-Ward3-Bed12",
    "source":     "iot",
    "heart_rate": 72,
    "spo2":       98.5,
    "temperature": 36.8
  }'
```

### Raspberry Pi / Python device
```bash
python iot_device_client.py \
    --patient-id P001 \
    --device-id RPi-001 \
    --interval 10
```

### Arduino / ESP32 (C++)
```cpp
// POST to Supabase REST API
HTTPClient http;
http.begin("https://YOUR_PROJECT.supabase.co/rest/v1/vitals_readings");
http.addHeader("Content-Type", "application/json");
http.addHeader("apikey", SUPABASE_ANON_KEY);
http.addHeader("Authorization", "Bearer " + String(SUPABASE_ANON_KEY));

String body = "{\"patient_id\":\"P001\",\"heart_rate\":" + String(hr) +
              ",\"spo2\":" + String(spo2) + ",\"source\":\"iot\"}";
http.POST(body);
```

### Dashboard polling
The `get_vitals()` function in `influx_plugin.py` checks for fresh IoT rows
(within `IOT_POLL_SECONDS`, default 30s) before falling back to simulation.
No dashboard code changes needed — it's fully automatic.

---

## Data Flow

```
IoT Device              Streamlit App
    │                        │
    │  POST /vitals_readings  │
    ├──────────────────────► Supabase ◄── patient_db (CRUD)
    │                        │
    │                    influx_plugin
    │                   get_vitals()
    │                        │
    │                   realtime_engine
    │                    tick()
    │                        │
    │                 classify → alert
    │                        │
    │               save_alert() ──────► alert_log table
    │                        │
    │               send_gmail() ──────► Doctor email
    │                        │
    │                     Streamlit UI
```

---

## Database Schema Overview

### `vitals_readings`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Auto-generated |
| `patient_id` | TEXT | FK → patients |
| `device_id` | TEXT | e.g. `"RPi-Ward3"` |
| `source` | TEXT | `'manual'` / `'iot'` / `'camera'` |
| `heart_rate` | NUMERIC | bpm |
| `spo2` | NUMERIC | % |
| `systolic_bp` | NUMERIC | mmHg |
| `diastolic_bp` | NUMERIC | mmHg |
| `temperature` | NUMERIC | °C |
| `blood_sugar` | NUMERIC | mg/dL |
| `respiratory_rate` | NUMERIC | rpm |
| `bmi` | NUMERIC | kg/m² |
| `recorded_at` | TIMESTAMPTZ | Auto |

### `alert_log`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Auto |
| `patient_id` | TEXT | |
| `vital` | TEXT | e.g. `"Heart Rate"` |
| `level` | TEXT | `CRITICAL` / `HIGH` / etc. |
| `category` | TEXT | `Critical` / `Warning` |
| `email_sent` | BOOLEAN | |
| `acknowledged` | BOOLEAN | |
| `device_id` | TEXT | Source device |
| `recorded_at` | TIMESTAMPTZ | |

---

## Scalability Notes

| Concern | Solution |
|---------|----------|
| Many IoT devices | Supabase handles 10k+ concurrent connections |
| High vitals frequency | Batch with `persist_every=5` in RealTimeEngine |
| Multi-hospital | Add `org_id` to patients + Row Level Security |
| Historical analytics | Use Supabase's built-in PostgREST for queries |
| Real-time push to UI | Enable Supabase Realtime on `vitals_readings` |
| Alert deduplication | Cooldown per vital per patient in RealTimeEngine |

---

## Fallback Mode (SQLite)

If Supabase credentials are not set, all three modules fall back automatically to a local `healnet.db` SQLite file — zero code changes, same API surface.

```bash
DB_FALLBACK=1 streamlit run app.py  # force SQLite
```
