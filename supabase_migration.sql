-- ═══════════════════════════════════════════════════════════════════════════
-- HealNet AI — Supabase Schema Migration
-- Run this ONCE in your Supabase project's SQL editor.
-- https://supabase.com → Your Project → SQL Editor → New Query → Run
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── 1. Users / Auth ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    name          TEXT,
    kind          TEXT DEFAULT 'solo'
                  CHECK (kind IN ('solo','org','staff','orgpatient')),
    org_id        TEXT,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now(),
    last_login    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS users_email_idx ON users(email);

-- ─── 2. Patients ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patients (
    patient_id          TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    age                 INTEGER CHECK (age > 0 AND age < 151),
    gender              TEXT,
    contact             TEXT,
    blood_group         TEXT,
    email               TEXT,
    address             TEXT,
    registered_by       TEXT,
    allergies           TEXT,
    chronic_conditions  TEXT,
    current_medications TEXT,
    past_surgeries      TEXT,
    family_history      TEXT,
    medical_notes       TEXT,
    emergency_name      TEXT,
    emergency_relation  TEXT,
    emergency_contact   TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS patients_name_idx ON patients(name);
CREATE INDEX IF NOT EXISTS patients_created_idx ON patients(created_at DESC);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS patients_updated_at ON patients;
CREATE TRIGGER patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ─── 3. Vitals Readings (IoT-ready) ─────────────────────────────────────────
-- IoT devices POST directly to this table via the Supabase REST API.
-- Example curl from a Raspberry Pi / ESP32:
--
--   curl -X POST https://<project>.supabase.co/rest/v1/vitals_readings \
--     -H "apikey: <anon_key>" \
--     -H "Authorization: Bearer <anon_key>" \
--     -H "Content-Type: application/json" \
--     -d '{"patient_id":"P001","heart_rate":72,"spo2":98,"source":"iot","device_id":"RPi-001"}'
--
CREATE TABLE IF NOT EXISTS vitals_readings (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    device_id        TEXT,
    source           TEXT DEFAULT 'manual'
                     CHECK (source IN ('manual','iot','camera')),
    heart_rate       NUMERIC(6,1),
    spo2             NUMERIC(5,1),
    systolic_bp      NUMERIC(5,1),
    diastolic_bp     NUMERIC(5,1),
    temperature      NUMERIC(5,2),
    blood_sugar      NUMERIC(6,1),
    respiratory_rate NUMERIC(5,1),
    bmi              NUMERIC(5,2),
    recorded_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS vitals_patient_idx  ON vitals_readings(patient_id);
CREATE INDEX IF NOT EXISTS vitals_recorded_idx ON vitals_readings(recorded_at DESC);
CREATE INDEX IF NOT EXISTS vitals_source_idx   ON vitals_readings(source);
CREATE INDEX IF NOT EXISTS vitals_device_idx   ON vitals_readings(device_id);


-- ─── 4. Alert Log ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_log (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id     TEXT NOT NULL,
    patient_name   TEXT,
    vital          TEXT,
    value          TEXT,
    level          TEXT,
    category       TEXT CHECK (category IN ('Critical','Warning')),
    message        TEXT,
    email_sent     BOOLEAN DEFAULT false,
    email_error    TEXT,
    acknowledged   BOOLEAN DEFAULT false,
    ack_by         TEXT,
    ack_time       TIMESTAMPTZ,
    device_id      TEXT,
    recorded_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS alert_patient_idx  ON alert_log(patient_id);
CREATE INDEX IF NOT EXISTS alert_level_idx    ON alert_log(level);
CREATE INDEX IF NOT EXISTS alert_recorded_idx ON alert_log(recorded_at DESC);
CREATE INDEX IF NOT EXISTS alert_ack_idx      ON alert_log(acknowledged);


-- ─── 5. IoT Device Registry ──────────────────────────────────────────────────
-- Optional: register known IoT devices
CREATE TABLE IF NOT EXISTS iot_devices (
    device_id      TEXT PRIMARY KEY,
    patient_id     TEXT REFERENCES patients(patient_id) ON DELETE SET NULL,
    device_type    TEXT DEFAULT 'generic',  -- 'esp32'|'raspberry_pi'|'wearable'|...
    firmware_ver   TEXT,
    ip_address     TEXT,
    last_seen      TIMESTAMPTZ,
    registered_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS iot_patient_idx ON iot_devices(patient_id);


-- ─── 6. Row-Level Security (optional — enable when ready) ────────────────────
-- Uncomment to restrict access by authenticated user:
--
-- ALTER TABLE patients        ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE vitals_readings ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE alert_log       ENABLE ROW LEVEL SECURITY;
--
-- CREATE POLICY "users_own_data" ON patients
--     USING (registered_by = auth.uid()::text);
--
-- CREATE POLICY "iot_insert_vitals" ON vitals_readings
--     FOR INSERT WITH CHECK (true);  -- allow all inserts (IoT)
--
-- CREATE POLICY "read_own_vitals" ON vitals_readings
--     FOR SELECT USING (
--         patient_id IN (
--             SELECT patient_id FROM patients
--             WHERE registered_by = auth.uid()::text
--         )
--     );


-- ─── 7. Realtime (enable for live IoT dashboard) ─────────────────────────────
-- Run in Supabase dashboard: Database → Replication → enable vitals_readings
-- Or via SQL:
-- ALTER PUBLICATION supabase_realtime ADD TABLE vitals_readings;
-- ALTER PUBLICATION supabase_realtime ADD TABLE alert_log;


-- ─── Done ─────────────────────────────────────────────────────────────────────
SELECT 'HealNet AI schema installed successfully.' AS status;
