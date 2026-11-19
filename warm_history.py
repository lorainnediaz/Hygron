"""Synthetic warm-start history used by the Hygron dashboard and API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import random

from ml_bridge import HISTORY_ROWS


ROOMS = {
    "room_101": ("Room 101", 64),
    "room_102": ("Room 102", 73),
    "room_103": ("Room 103", 84),
    "room_104": ("Room 104", 91),
}


def warm_history(room_id: str, base_rh: float, end: datetime) -> list[dict]:
    """Generate one independent, explicitly synthetic 60-day warm start."""
    rng = random.Random(107 + int(room_id.split("_")[-1]))
    start = end - timedelta(minutes=5 * (HISTORY_ROWS - 1))
    values = []
    for n in range(HISTORY_ROWS):
        ts = start + timedelta(minutes=5 * n)
        hour = ts.hour + ts.minute / 60
        cycle = math.sin((hour - 8) * math.pi / 12)
        rh = max(2.0, min(99.9, base_rh - 4.5 * cycle + rng.gauss(0, 0.6)))
        temp = 27 + 1.5 * cycle + rng.gauss(0, 0.1)
        values.append({
            "room_id": room_id,
            "node_id": f"esp32_{room_id}",
            "timestamp": ts.isoformat(timespec="seconds"),
            "complete": True,
            "rh": round(rh, 3),
            "temp": round(temp, 3),
            "voc_resistance": round(
                max(5000, 47000 - rh * 85 + rng.gauss(0, 200)),
                1,
            ),
            "source": "synthetic_sil",
        })
    return values


def seed_default_rooms(cloud) -> None:
    """Seed each default room only when its shared SQLite history is empty."""
    end = datetime(2026, 8, 30, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    for room_id, (_, base_rh) in ROOMS.items():
        cloud.seed_room_if_empty(
            room_id,
            lambda room_id=room_id, base_rh=base_rh: warm_history(
                room_id,
                base_rh,
                end - timedelta(minutes=5),
            ),
        )
