"""Simulated ESP32 packet validation and fixed five-minute edge aggregation.

A 5-minute bin is emitted only when all 10 expected 30-second ticks are seen.
A summary can be flagged incomplete when sensor readings are missing or invalid.
For ML, the caller must reject incomplete bins or use an explicitly documented
imputation strategy. No fake readings are substituted here.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
import math


def _floor_five(ts: datetime) -> datetime:
    return ts.replace(minute=(ts.minute // 5) * 5, second=0, microsecond=0)


def validate_packet(packet: dict) -> dict:
    required = ("node_id", "room_id", "timestamp", "online", "source")
    if any(k not in packet for k in required):
        raise ValueError("Missing required packet metadata")
    if packet["source"] != "synthetic_sil":
        raise ValueError("Expected a synthetic SIL packet")
    ts = datetime.fromisoformat(packet["timestamp"])
    if ts.tzinfo is None:
        raise ValueError("Timestamp must have timezone information")
    online = packet["online"] is True
    readings = {}
    limits = {
        "temperature_c": (10, 45),
        "relative_humidity_pct": (0, 100),
        "gas_resistance_ohms": (0, float("inf")),
    }
    for key, (lo, hi) in limits.items():
        value = packet.get(key)
        good = (online and isinstance(value, (float, int)) and
                not isinstance(value, bool) and math.isfinite(value) and lo <= value <= hi)
        readings[key] = float(value) if good else None
    return {"node_id": str(packet["node_id"]), "room_id": str(packet["room_id"]),
            "timestamp": ts, "online": online, **readings}


class EdgeGateway:
    def __init__(self) -> None:
        self._bins: dict[tuple, dict[datetime, dict]] = defaultdict(dict)

    def receive(self, packet: dict) -> None:
        reading = validate_packet(packet)
        ts = reading["timestamp"]
        if ts.second not in (0, 30) or ts.microsecond != 0:
            raise ValueError("Packet not aligned to 30-second ticks")
        key = (reading["room_id"], reading["node_id"], _floor_five(ts))
        # Timestamp-keyed storage avoids counting the same packet twice.
        self._bins[key][ts] = reading

    def summaries(self) -> list[dict]:
        output = []
        for (room, node, bin_start), bucket in sorted(self._bins.items()):
            slots = [bin_start + timedelta(seconds=30 * i) for i in range(10)]
            present = [bucket[t] for t in slots if t in bucket]
            good = [r for r in present if r["online"] and all(
                r[k] is not None for k in
                ("temperature_c", "relative_humidity_pct", "gas_resistance_ohms"))]
            complete = len(good) == 10 and len(present) == 10
            # Do not output misleading means for incomplete intervals.
            output.append({
                "room_id": room,
                "node_id": node,
                "timestamp": bin_start.isoformat(timespec="seconds"),
                "expected_readings": 10,
                "received_readings": len(present),
                "valid_readings": len(good),
                "complete": complete,
                "temp": round(mean(r["temperature_c"] for r in good), 3) if complete else None,
                "rh": round(mean(r["relative_humidity_pct"] for r in good), 3) if complete else None,
                "voc_resistance": round(mean(r["gas_resistance_ohms"] for r in good), 1) if complete else None,
                "source": "synthetic_sil",
            })
        return output

    def clear(self) -> None:
        self._bins.clear()
