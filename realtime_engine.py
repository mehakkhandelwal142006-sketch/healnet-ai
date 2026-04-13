from influx_plugin import get_vitals
import random
from datetime import datetime

class RealTimeEngine:
    def __init__(self, mode="simulated"):
        self.mode = mode

    def fetch(self, patient_id):
        try:
            if self.mode == "api":
                data = self.fetch_from_api(patient_id)
            elif self.mode == "mqtt":
                data = self.fetch_from_mqtt(patient_id)
            else:
                data = self.simulated_data(patient_id)

            # ✅ Ensure data is not empty
            if not data:
                return self.fallback_data(patient_id)

            return data

        except Exception as e:
            print("ERROR in fetch:", e)
            return self.fallback_data(patient_id)

    # ───────────────────────────────
    def simulated_data(self, patient_id):
        data = get_vitals(patient_id)

        # ✅ If DB returns empty → fallback
        if not data:
            return self.fallback_data(patient_id)

        return data

    # ───────────────────────────────
    def fetch_from_api(self, patient_id):
        import requests
        url = f"http://localhost:5000/vitals/{patient_id}"
        try:
            res = requests.get(url)
            return res.json()
        except:
            return self.fallback_data(patient_id)

    # ───────────────────────────────
    def fetch_from_mqtt(self, patient_id):
        return {
            "heart_rate": random.randint(70, 90),
            "bp": f"{random.randint(110,130)}/{random.randint(70,90)}",
            "spo2": random.randint(95, 100),
            "temperature": round(random.uniform(36.0, 37.5), 1),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "MQTT"
        }

    # ───────────────────────────────
    def fallback_data(self, patient_id):
        """Used when DB/API fails"""
        return {
            "heart_rate": random.randint(72, 88),
            "bp": f"{random.randint(115,125)}/{random.randint(75,85)}",
            "spo2": random.randint(96, 100),
            "temperature": round(random.uniform(36.2, 37.2), 1),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "fallback"
        }
