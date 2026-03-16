# =====================================================
# HEALNET — REAL-TIME VITAL RANGES
# Clinical reference: AHA, WHO, NIH guidelines
# =====================================================

# ── BLOOD PRESSURE (Systolic / Diastolic mmHg) ─────
def classify_bp(systolic, diastolic):
    if systolic >= 180 or diastolic >= 120:
        return "CRITICAL", "🔴 Hypertensive Crisis — seek emergency care"
    elif systolic >= 140 or diastolic >= 90:
        return "HIGH", "🔴 High Blood Pressure (Stage 2 Hypertension)"
    elif systolic >= 130 or diastolic >= 80:
        return "HIGH", "🟠 High Blood Pressure (Stage 1 Hypertension)"
    elif systolic >= 120 and diastolic < 80:
        return "MODERATE", "🟡 Elevated — monitor regularly"
    elif systolic < 90 or diastolic < 60:
        return "LOW", "🔵 Low Blood Pressure (Hypotension)"
    else:
        return "NORMAL", "🟢 Normal Blood Pressure"


# ── HEART RATE (bpm) ────────────────────────────────
def classify_heart_rate(bpm):
    if bpm > 150:
        return "CRITICAL", "🔴 Critically High Heart Rate — immediate attention"
    elif bpm > 100:
        return "HIGH", "🔴 High Heart Rate (Tachycardia)"
    elif bpm >= 60:
        return "NORMAL", "🟢 Normal Heart Rate"
    elif bpm >= 50:
        return "LOW", "🟡 Slightly Low — monitor"
    else:
        return "CRITICAL", "🔴 Critically Low Heart Rate (Bradycardia)"


# ── BLOOD OXYGEN / SPO2 (%) ─────────────────────────
def classify_spo2(spo2):
    if spo2 >= 95:
        return "NORMAL", "🟢 Normal Oxygen Level"
    elif spo2 >= 90:
        return "MODERATE", "🟡 Moderate — supplemental oxygen may be needed"
    elif spo2 >= 85:
        return "HIGH", "🔴 Low Oxygen Level — medical attention needed"
    else:
        return "CRITICAL", "🔴 Critical — emergency oxygen required"


# ── BLOOD SUGAR (mg/dL) — Fasting ───────────────────
def classify_blood_sugar(mg_dl):
    if mg_dl >= 200:
        return "CRITICAL", "🔴 Critical — possible diabetic emergency"
    elif mg_dl >= 126:
        return "HIGH", "🔴 High Blood Sugar (Diabetes range)"
    elif mg_dl >= 100:
        return "MODERATE", "🟡 Pre-diabetic range — lifestyle changes advised"
    elif mg_dl >= 70:
        return "NORMAL", "🟢 Normal Blood Sugar"
    else:
        return "LOW", "🔵 Low Blood Sugar (Hypoglycemia)"


# ── BODY TEMPERATURE (°F) ────────────────────────────
def classify_temperature(temp_f):
    if temp_f >= 104:
        return "CRITICAL", "🔴 Critically High Fever — emergency care needed"
    elif temp_f >= 100.4:
        return "HIGH", "🔴 Fever"
    elif temp_f >= 97.0:
        return "NORMAL", "🟢 Normal Temperature"
    else:
        return "LOW", "🔵 Hypothermia risk — below normal temperature"


# ── RESPIRATORY RATE (breaths/min) ──────────────────
def classify_respiratory_rate(rate):
    if rate > 30:
        return "CRITICAL", "🔴 Critically High Respiratory Rate"
    elif rate > 20:
        return "HIGH", "🔴 High Respiratory Rate (Tachypnea)"
    elif rate >= 12:
        return "NORMAL", "🟢 Normal Respiratory Rate"
    else:
        return "LOW", "🔵 Low Respiratory Rate (Bradypnea)"


# ── BMI ──────────────────────────────────────────────
def classify_bmi(bmi):
    if bmi >= 40:
        return "CRITICAL", "🔴 Severely Obese"
    elif bmi >= 30:
        return "HIGH", "🔴 Obese"
    elif bmi >= 25:
        return "MODERATE", "🟡 Overweight"
    elif bmi >= 18.5:
        return "NORMAL", "🟢 Normal BMI"
    else:
        return "LOW", "🔵 Underweight"


# ── FULL VITALS ASSESSMENT ───────────────────────────
def assess_all_vitals(systolic, diastolic, heart_rate, spo2,
                      blood_sugar, temperature, respiratory_rate, bmi):
    results = {
        "Blood Pressure":      classify_bp(systolic, diastolic),
        "Heart Rate":          classify_heart_rate(heart_rate),
        "SpO2":                classify_spo2(spo2),
        "Blood Sugar":         classify_blood_sugar(blood_sugar),
        "Temperature":         classify_temperature(temperature),
        "Respiratory Rate":    classify_respiratory_rate(respiratory_rate),
        "BMI":                 classify_bmi(bmi),
    }

    # overall severity — worst reading wins
    severity_order = ["CRITICAL", "HIGH", "MODERATE", "LOW", "NORMAL"]
    overall = "NORMAL"
    for vital, (level, _) in results.items():
        if severity_order.index(level) < severity_order.index(overall):
            overall = level

    return results, overall
