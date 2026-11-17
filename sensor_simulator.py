"""Software-only BME680/ESP32 digital twin for Hygron.

This module generates SYNTHETIC sensor packets. Values are neither physical
measurements nor verified device accuracy characteristics. A virtual node emits
one packet per simulated 30-second tick, optionally with a sensor dropout.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator
import json
import math
import random


@dataclass
class VirtualESP32:
    room_id: str
    node_id: str
    base_temp: float = 27.0
    base_rh: float = 74.0
    base_gas_ohms: float = 45000.0
    seed: int = 42
    online: bool = True
    scenario: str = "normal"  # normal, humid_spike, prolonged_damp, condensation
    scenario_start: datetime | None = None
    scenario_duration_hours: float = 48.0

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        if not 0 <= self.base_rh <= 100:
            raise ValueError("base_rh must be between 0 and 100")

    def set_scenario(self, scenario: str, start: datetime | None = None,
                     duration_hours: float = 48.0) -> None:
        allowed = {"normal", "humid_spike", "prolonged_damp", "condensation"}
        if scenario not in allowed:
            raise ValueError(f"scenario must be one of {sorted(allowed)}")
        if duration_hours <= 0:
            raise ValueError("duration_hours must be positive")
        self.scenario = scenario
        self.scenario_start = start
        self.scenario_duration_hours = duration_hours

    def read(self, timestamp: datetime, dropout: bool = False) -> dict:
        """Return one JSON-serializable packet (readings every 30 simulated seconds)."""
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must include a timezone offset")
        hour = timestamp.hour + timestamp.minute / 60 + timestamp.second / 3600
        # Project-designed simulation, not calibrated physical hardware.
        temp = self.base_temp + 1.5 * math.sin((hour - 8) * math.pi / 12)
        rh = self.base_rh - 4.0 * math.sin((hour - 8) * math.pi / 12)
        elapsed_h = None
        if self.scenario_start is not None:
            elapsed_h = (timestamp - self.scenario_start).total_seconds() / 3600
        active = (elapsed_h is not None and 0 <= elapsed_h < self.scenario_duration_hours)
        if active and self.scenario == "humid_spike":
            rh += 18
        elif active and self.scenario == "prolonged_damp":
            rh += 12
        elif active and self.scenario == "condensation":
            rh += 16
            temp -= 2
        temp += self._rng.gauss(0, 0.07)
        rh = max(0.0, min(100.0, rh + self._rng.gauss(0, 0.3)))
        gas = max(5000.0, self.base_gas_ohms - (rh - self.base_rh) * 110
                  + self._rng.gauss(0, 450))
        online = self.online and not dropout
        return {
            "schema_version": "1.0",
            "node_id": self.node_id,
            "room_id": self.room_id,
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "sampling_interval_seconds": 30,
            "sensor_type": "virtual_BME680",
            "online": online,
            "wifi_rssi_dbm": self._rng.randint(-75, -45) if online else None,
            "temperature_c": round(temp, 3) if online else None,
            "relative_humidity_pct": round(rh, 3) if online else None,
            "gas_resistance_ohms": round(gas, 1) if online else None,
            "source": "synthetic_sil",
        }

    def stream(self, start: datetime, count: int,
               dropout_indices: set[int] | None = None) -> Iterator[dict]:
        if count < 0:
            raise ValueError("count must be >= 0")
        dropouts = dropout_indices or set()
        for i in range(count):
            yield self.read(start + timedelta(seconds=30 * i), dropout=i in dropouts)


def packet_json(packet: dict) -> str:
    return json.dumps(packet, separators=(",", ":"), allow_nan=False)
