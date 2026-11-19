import tempfile
import unittest
import sqlite3

from fastapi.testclient import TestClient

from backend.main import create_app
import shared_store


class HygronApiTests(unittest.TestCase):
    def setUp(self):
        self.old_db_path = shared_store.DB_PATH
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.app = create_app(f"{self.tmp.name}/api.sqlite3")
        self.client = TestClient(self.app)

    def tearDown(self):
        self.tmp.cleanup()
        shared_store.DB_PATH = self.old_db_path

    def test_health_and_rooms(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        response = self.client.get("/api/rooms")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["rooms"]), 4)
        self.assertEqual(body["display_timezone"], "Asia/Manila")
        self.assertTrue(body["is_simulated"])

    def test_history_and_risk_routes(self):
        history = self.client.get("/api/rooms/room_101/history?hours=24")
        self.assertEqual(history.status_code, 200)
        self.assertGreater(len(history.json()["readings"]), 0)
        risk = self.client.get("/api/rooms/room_101/risk")
        self.assertEqual(risk.status_code, 200)
        forecast = self.client.get("/api/rooms/room_101/forecast")
        self.assertEqual(forecast.status_code, 200)
        self.assertEqual(forecast.json()["horizon_hours"], 24)
        self.assertEqual(forecast.json()["confidence"], "Unavailable")

    def test_invalid_room(self):
        response = self.client.get("/api/rooms/room_999/risk")
        self.assertEqual(response.status_code, 404)

    def test_system_status(self):
        response = self.client.get("/api/system-status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["display_timezone"], "Asia/Manila")
        self.assertTrue(body["models"]["available"])

    def test_alerts(self):
        response = self.client.get("/api/alerts")
        self.assertEqual(response.status_code, 200)
        self.assertIn("alerts", response.json())

    def test_alert_acknowledgment_persists_in_sqlite(self):
        alerts = self.client.get("/api/alerts").json()["alerts"]
        if not alerts:
            self.skipTest("No active High-risk alerts")
        alert_id = alerts[0]["id"]
        acknowledged = self.client.post(f"/api/alerts/{alert_id}/acknowledge")
        self.assertEqual(acknowledged.status_code, 200)
        self.assertEqual(acknowledged.json()["status"], "Acknowledged")
        persisted = self.client.get("/api/alerts").json()["alerts"]
        matching = next((alert for alert in persisted if alert["id"] == alert_id), None)
        self.assertIsNotNone(matching)
        self.assertEqual(matching["status"], "Acknowledged")

    def test_insufficient_history_is_unavailable(self):
        with sqlite3.connect(f"{self.tmp.name}/api.sqlite3") as db:
            db.execute("DELETE FROM summaries")
        response = self.client.get("/api/rooms/room_101/risk")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["current_risk"], "Unavailable")
        self.assertFalse(body["sufficient_history"])
        self.assertIn("No valid data", body["error"])

    def test_unavailable_model_is_reported(self):
        self.app.state.models = None
        self.app.state.model_error = "Test model unavailable"
        response = self.client.get("/api/rooms/room_101/risk")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["current_risk"], "Unavailable")
        self.assertFalse(body["model_available"])


if __name__ == "__main__":
    unittest.main()
