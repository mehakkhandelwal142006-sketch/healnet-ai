from influx_plugin import get_vitals

class RealTimeEngine:
    def __init__(self, mode="simulated"):
        self.mode = mode

    def fetch(self, patient_id):
        if self.mode == "api":
            return self.fetch_from_api(patient_id)
        elif self.mode == "mqtt":
            return self.fetch_from_mqtt(patient_id)
        else:
            return self.simulated_data(patient_id)

    def simulated_data(self, patient_id):
        return get_vitals(patient_id)

    def fetch_from_api(self, patient_id):
        import requests
        url = f"http://localhost:5000/vitals/{patient_id}"
        return requests.get(url).json()

    def fetch_from_mqtt(self, patient_id):
        return {
            "data": {},
            "timestamp": "N/A",
            "source": "MQTT"
        }