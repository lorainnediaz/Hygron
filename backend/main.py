from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import shared_store
from inference import estimate_risk, load_models
from ml_bridge import HISTORY_ROWS, latest_features
from warm_history import ROOMS, seed_default_rooms


MANILA = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"
DEFAULT_ACK_RETENTION_DAYS = 90
CONFIDENCE_REASON = (
    "The model's scores haven't been checked against labeled data, "
    "so no percentage is shown."
)


def unavailable_reason(code: str, history_count: int = 0) -> str:
    """Plain-language explanation shown to staff when no risk estimate exists."""
    reasons = {
        "no_data": "No valid readings have been received for this room.",
        "model_unavailable": "The risk model files could not be loaded.",
        "insufficient_history": (
            f"The model needs 60 days of continuous readings; "
            f"{history_count:,} of {HISTORY_ROWS:,} have been received."
        ),
        "history_gaps": "The 60-day history has missing or duplicate readings, so the model cannot run.",
        "invalid_readings": "Some readings are outside the valid sensor range.",
        "model_error": "The model could not produce an estimate from the latest readings.",
    }
    return reasons[code]


def classify_feature_error(message: str) -> str:
    if message.startswith("Insufficient history"):
        return "insufficient_history"
    if "Missing or duplicate" in message or "Incomplete gateway" in message:
        return "history_gaps"
    if "Out-of-range" in message or "Nonfinite" in message:
        return "invalid_readings"
    return "model_error"


def ack_retention_days() -> int:
    raw = os.environ.get("HYGRON_ALERT_ACK_RETENTION_DAYS", str(DEFAULT_ACK_RETENTION_DAYS))
    try:
        days = int(raw)
    except ValueError:
        raise ValueError("HYGRON_ALERT_ACK_RETENTION_DAYS must be a whole number of days") from None
    if days < 1:
        raise ValueError("HYGRON_ALERT_ACK_RETENTION_DAYS must be at least 1")
    return days


def prune_alert_acknowledgments(retention_days: int, now: datetime | None = None) -> int:
    """Delete acknowledgments recorded more than retention_days ago. Returns rows deleted."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    with shared_store.connect() as db:
        rows = db.execute("SELECT alert_id, acknowledged_at FROM alert_acknowledgments").fetchall()
        expired = []
        for alert_id, acknowledged_at in rows:
            stamp = datetime.fromisoformat(acknowledged_at)
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=MANILA)
            if stamp < cutoff:
                expired.append((alert_id,))
        db.executemany("DELETE FROM alert_acknowledgments WHERE alert_id=?", expired)
    return len(expired)


def manila_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=MANILA)
    return timestamp.astimezone(MANILA).isoformat(timespec="seconds")


def create_app(db_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(
        title="Hygron API",
        description="API for the software-simulated Hygron HCI dashboard.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if db_path is not None:
        shared_store.DB_PATH = Path(db_path)

    app.state.cloud = shared_store.SQLiteCloud()
    seed_default_rooms(app.state.cloud)
    app.state.ack_retention_days = ack_retention_days()
    prune_alert_acknowledgments(app.state.ack_retention_days)

    try:
        app.state.models = load_models(str(MODEL_DIR))
        app.state.model_error = None
    except (FileNotFoundError, ImportError, KeyError, OSError, ValueError) as exc:
        app.state.models = None
        app.state.model_error = f"{type(exc).__name__}: {exc}"

    def valid_room(room_id: str) -> None:
        if room_id not in ROOMS:
            raise HTTPException(status_code=404, detail="Unknown room identifier")

    def room_status(room_id: str) -> dict:
        valid_room(room_id)
        rows = app.state.cloud.history(room_id, complete_only=True, limit=HISTORY_ROWS)
        latest = rows[-1] if rows else None
        result = {
            "room_id": room_id,
            "room_name": ROOMS[room_id][0],
            "current_risk": "Unavailable",
            "forecast_24h_risk": "Unavailable",
            "rh": latest["rh"] if latest else None,
            "temp": latest["temp"] if latest else None,
            "latest_timestamp": manila_timestamp(latest["timestamp"]) if latest else None,
            "history_count": len(rows),
            "required_history": HISTORY_ROWS,
            "sufficient_history": len(rows) >= HISTORY_ROWS,
            "is_simulated": True,
            "model_available": app.state.models is not None,
            "model_error": app.state.model_error,
        }
        def unavailable(code: str, error: str) -> dict:
            result["error"] = error
            result["unavailable_code"] = code
            result["unavailable_reason"] = unavailable_reason(code, len(rows))
            return result

        if latest is None:
            return unavailable("no_data", "No valid data")
        if app.state.models is None:
            return unavailable("model_unavailable", "ML model files unavailable")
        try:
            features = latest_features(rows)
            estimate = estimate_risk(features, app.state.models)
            result["current_risk"] = estimate["current_risk"]
            result["forecast_24h_risk"] = estimate["forecast_24h_risk"]
            result["risk_change_predicted"] = estimate["risk_change_predicted"]
            result["current_indicator"] = estimate["current_indicator"]
            result["forecast_indicator"] = estimate["forecast_indicator"]
        except (ValueError, KeyError, IndexError) as exc:
            return unavailable(classify_feature_error(str(exc)), str(exc))
        return result

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "display_timezone": "Asia/Manila", "simulation": True}

    @app.get("/api/rooms")
    def rooms() -> dict:
        statuses = [room_status(room_id) for room_id in ROOMS]
        rank = {"High": 0, "Medium": 1, "Low": 2, "Unavailable": 3}
        statuses.sort(key=lambda item: (rank[item["current_risk"]], item["room_id"]))
        counts = {
            risk: sum(item["current_risk"] == risk for item in statuses)
            for risk in ("High", "Medium", "Low", "Unavailable")
        }
        return {
            "rooms": statuses,
            "counts": counts,
            "display_timezone": "Asia/Manila",
            "is_simulated": True,
        }

    @app.get("/api/rooms/{room_id}/history")
    def room_history(
        room_id: str,
        hours: int = Query(24, ge=1, le=1440),
    ) -> dict:
        valid_room(room_id)
        rows = app.state.cloud.history(room_id, complete_only=True)
        if not rows:
            return {
                "room_id": room_id,
                "room_name": ROOMS[room_id][0],
                "hours": hours,
                "display_timezone": "Asia/Manila",
                "is_simulated": True,
                "readings": [],
                "message": "No valid cloud readings",
            }
        latest = datetime.fromisoformat(rows[-1]["timestamp"])
        cutoff = latest - timedelta(hours=hours)
        selected = [
            row for row in rows
            if datetime.fromisoformat(row["timestamp"]) >= cutoff
        ]
        return {
            "room_id": room_id,
            "room_name": ROOMS[room_id][0],
            "hours": hours,
            "display_timezone": "Asia/Manila",
            "is_simulated": True,
            "readings": [
                {
                    "timestamp": manila_timestamp(row["timestamp"]),
                    "simulated_timestamp": row["timestamp"],
                    "rh": row["rh"],
                    "temp": row["temp"],
                    "complete": bool(row["complete"]),
                }
                for row in selected
            ],
        }

    @app.get("/api/rooms/{room_id}/risk")
    def room_risk(room_id: str) -> dict:
        status = room_status(room_id)
        return {
            "room_id": room_id,
            "room_name": ROOMS[room_id][0],
            "current_risk": status["current_risk"],
            "indicator": status.get("current_indicator"),
            "latest_timestamp": status["latest_timestamp"],
            "sufficient_history": status["sufficient_history"],
            "history_count": status["history_count"],
            "required_history": status["required_history"],
            "model_available": status["model_available"],
            "error": status.get("error"),
            "unavailable_code": status.get("unavailable_code"),
            "unavailable_reason": status.get("unavailable_reason"),
            "is_simulated": True,
        }

    @app.get("/api/rooms/{room_id}/forecast")
    def room_forecast(room_id: str) -> dict:
        status = room_status(room_id)
        return {
            "room_id": room_id,
            "room_name": ROOMS[room_id][0],
            "horizon_hours": 24,
            "current_risk": status["current_risk"],
            "forecast_24h_risk": status["forecast_24h_risk"],
            "indicator": status.get("forecast_indicator"),
            "risk_change_predicted": status.get("risk_change_predicted"),
            "latest_timestamp": status["latest_timestamp"],
            "sufficient_history": status["sufficient_history"],
            "model_available": status["model_available"],
            "error": status.get("error"),
            "unavailable_code": status.get("unavailable_code"),
            "unavailable_reason": status.get("unavailable_reason"),
            "is_simulated": True,
            "confidence": "Unavailable",
            "confidence_reason": CONFIDENCE_REASON,
            "disclaimer": "Supplementary simulated risk category; not a guaranteed or hourly warning.",
        }

    @app.get("/api/alerts")
    def alerts() -> dict:
        items = []
        for room_id in ROOMS:
            status = room_status(room_id)
            if status["current_risk"] != "High" or not status["latest_timestamp"]:
                continue
            stamp = status["latest_timestamp"]
            alert_id = f"{room_id}_{stamp}"
            items.append({
                "id": alert_id,
                "room_id": room_id,
                "room_name": ROOMS[room_id][0],
                "type": "Current risk",
                "risk": "High",
                "rh": status["rh"],
                "temp": status["temp"],
                "timestamp": stamp,
                "status": "Acknowledged" if app.state.cloud.is_alert_acknowledged(alert_id) else "Action needed",
                "is_simulated": True,
            })
        return {"alerts": items, "acknowledgments_are_resolution": False}

    @app.post("/api/alerts/{alert_id}/acknowledge")
    def acknowledge_alert(alert_id: str) -> dict:
        app.state.cloud.acknowledge_alert(alert_id)
        return {
            "id": alert_id,
            "status": "Acknowledged",
            "message": "Acknowledged and stored in SQLite; this does not confirm risk resolution.",
        }

    @app.get("/api/system-status")
    def system_status() -> dict:
        storage = app.state.cloud.status()
        latest = app.state.cloud.latest_timestamp()
        return {
            "display_timezone": "Asia/Manila",
            "storage": "SQLite",
            "database": str(shared_store.DB_PATH),
            "stored_summaries": storage["stored_summaries"],
            "valid_for_history": storage["valid_for_history"],
            "incomplete": storage["incomplete"],
            "latest_timestamp": manila_timestamp(latest.isoformat()) if latest else None,
            "models": {
                "available": app.state.models is not None,
                "error": app.state.model_error,
                "model_dir": str(MODEL_DIR),
            },
            "alert_acknowledgment_retention_days": app.state.ack_retention_days,
            "is_simulated": True,
        }

    return app


app = create_app(os.environ.get("HYGRON_DB_PATH"))
