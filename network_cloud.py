"""Virtual Internet link and cloud receiver for the Hygron SIL demonstration.

No traffic leaves this Python process. The cloud accepts valid *complete* five-minute
summaries; incomplete summaries are recorded but not eligible for ML inference.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import json


@dataclass
class SimulatedInternet:
    online: bool = True
    latency_ms: int = 80  # DISPLAYED simulation setting, not wall-clock delay
    sent: int = 0
    failed: int = 0

    def transmit(self, payload: dict) -> dict | None:
        """Round-trip a JSON payload; return None when virtual Internet is offline."""
        if not self.online:
            self.failed += 1
            return None
        self.sent += 1
        return json.loads(json.dumps(payload, allow_nan=False))


@dataclass
class VirtualCloud:
    """In-memory storage keyed by (room, node, five-minute timestamp)."""
    records: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)

    def receive(self, summary: dict) -> None:
        if summary.get("source") != "synthetic_sil":
            raise ValueError("Only synthetic SIL summaries are accepted")
        required = ("room_id", "node_id", "timestamp", "complete", "temp", "rh", "voc_resistance")
        if any(key not in summary for key in required):
            raise ValueError("Missing required summary fields")
        stamp = datetime.fromisoformat(summary["timestamp"])
        if stamp.tzinfo is None:
            raise ValueError("Summary timestamp needs timezone")
        key = (str(summary["room_id"]), str(summary["node_id"]), summary["timestamp"])
        self.records[key] = dict(summary)

    def history(self, room_id: str, complete_only: bool = True) -> list[dict]:
        rows = [v for v in self.records.values() if v["room_id"] == room_id]
        if complete_only:
            rows = [v for v in rows if v["complete"]]
        return sorted(rows, key=lambda row: row["timestamp"])

    def status(self) -> dict:
        all_rows = list(self.records.values())
        return {"stored_summaries": len(all_rows),
                "valid_for_history": sum(bool(r["complete"]) for r in all_rows),
                "incomplete": sum(not r["complete"] for r in all_rows)}


@dataclass
class EdgeToCloudBridge:
    """Reliable demo transport with queueing during simulated Internet outages."""
    internet: SimulatedInternet
    cloud: VirtualCloud
    pending: list[dict] = field(default_factory=list)
    uploaded: int = 0

    def send(self, summary: dict) -> bool:
        # Queue even incomplete summaries: cloud retains quality flags.
        self.pending.append(dict(summary))
        self.flush()
        return len(self.pending) == 0

    def flush(self) -> int:
        delivered = 0
        while self.pending and self.internet.online:
            copy = self.internet.transmit(self.pending[0])
            if copy is None:
                break
            self.cloud.receive(copy)
            self.pending.pop(0)
            self.uploaded += 1
            delivered += 1
        return delivered

    def status(self) -> dict:
        return {"internet_online": self.internet.online,
                "simulated_latency_ms": self.internet.latency_ms,
                "queued_summaries": len(self.pending),
                "uploaded_summaries": self.uploaded,
                **self.cloud.status()}
