import os
import tempfile
import unittest
import sqlite3
from datetime import datetime, timedelta, timezone
from unittest import mock

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
        self.assertEqual(body["unavailable_code"], "model_unavailable")
        self.assertIn("model files", body["unavailable_reason"])

    def test_no_data_has_plain_language_reason(self):
        with sqlite3.connect(f"{self.tmp.name}/api.sqlite3") as db:
            db.execute("DELETE FROM summaries")
        body = self.client.get("/api/rooms/room_101/risk").json()
        self.assertEqual(body["unavailable_code"], "no_data")
        self.assertIn("No valid readings", body["unavailable_reason"])

    def test_history_gap_is_unavailable_with_reason(self):
        with sqlite3.connect(f"{self.tmp.name}/api.sqlite3") as db:
            db.execute(
                "DELETE FROM summaries WHERE room_id='room_101' AND timestamp IN "
                "(SELECT timestamp FROM summaries WHERE room_id='room_101' "
                "ORDER BY timestamp DESC LIMIT 1 OFFSET 100)"
            )
        body = self.client.get("/api/rooms").json()
        room = next(item for item in body["rooms"] if item["room_id"] == "room_101")
        self.assertEqual(room["current_risk"], "Unavailable")
        self.assertIn(room["unavailable_code"], {"insufficient_history", "history_gaps"})
        self.assertTrue(room["unavailable_reason"])

    def test_available_rooms_have_no_unavailable_reason(self):
        body = self.client.get("/api/rooms").json()
        for room in body["rooms"]:
            if room["current_risk"] != "Unavailable":
                self.assertNotIn("unavailable_reason", room)

    def test_forecast_confidence_reason(self):
        body = self.client.get("/api/rooms/room_101/forecast").json()
        self.assertEqual(body["confidence"], "Unavailable")
        self.assertIn("checked against labeled data", body["confidence_reason"])

    def test_old_acknowledgments_are_pruned_on_startup(self):
        db_path = f"{self.tmp.name}/api.sqlite3"
        old = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat(timespec="seconds")
        recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(timespec="seconds")
        with sqlite3.connect(db_path) as db:
            db.execute("INSERT INTO alert_acknowledgments VALUES ('old_alert', ?, 1)", (old,))
            db.execute("INSERT INTO alert_acknowledgments VALUES ('recent_alert', ?, 1)", (recent,))
        app = create_app(db_path)
        with sqlite3.connect(db_path) as db:
            ids = {row[0] for row in db.execute("SELECT alert_id FROM alert_acknowledgments")}
        self.assertEqual(ids, {"recent_alert"})
        self.assertEqual(app.state.ack_retention_days, 90)
        status = TestClient(app).get("/api/system-status").json()
        self.assertEqual(status["alert_acknowledgment_retention_days"], 90)

    def test_retention_days_must_be_valid(self):
        with mock.patch.dict(os.environ, {"HYGRON_ALERT_ACK_RETENTION_DAYS": "0"}):
            with self.assertRaises(ValueError):
                create_app(f"{self.tmp.name}/api.sqlite3")


if __name__ == "__main__":
    unittest.main()
