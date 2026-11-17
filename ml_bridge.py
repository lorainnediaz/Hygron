"""Bridge from virtual cloud five-minute summaries to nine RF features.

Do not use VTT labels or simulated mold index as predictors. This reproduces the
nine rolling-feature calculations used by the v6 training dataset, at a given
point in simulation time, only from historical valid five-minute measurements.
"""
from __future__ import annotations
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

FEATURES = ["rh", "temp", "dew_point", "dew_margin", "rh_mean_24h",
            "rh_mean_60D", "rh_std_24h", "rh_change_1h", "frac_above80_60D"]
HISTORY_ROWS = 60 * 24 * 12  # 17,280 5-min observations


def latest_features(records: list[dict]) -> pd.DataFrame:
    """Return the latest ML feature row. Reject gaps, duplicates, short history.

    Caller must pass cloud-received, complete five-minute summaries from one
    room, ordered or unordered. A 60D window includes the latest observation.
    The 1-hour change compares this time with the observation 12 rows earlier.
    """
    if len(records) < HISTORY_ROWS:
        raise ValueError(f"Insufficient history: {len(records):,}/{HISTORY_ROWS:,} complete five-minute readings")
    rows = sorted(records, key=lambda r: r['timestamp'])[-HISTORY_ROWS:]
    if any(not r.get('complete', False) for r in rows):
        raise ValueError('Incomplete gateway interval in 60-day history')
    if len({r['room_id'] for r in rows}) != 1:
        raise ValueError('History must belong to one room')
    d = pd.DataFrame(rows)
    d['timestamp'] = pd.to_datetime(d['timestamp'], utc=True)
    d = d.sort_values('timestamp').set_index('timestamp')
    if not (d.index.to_series().diff().iloc[1:] == pd.Timedelta('5min')).all():
        raise ValueError('Missing or duplicate five-minute timestamps in 60-day window')
    if d[['rh','temp']].isna().any().any() or not np.isfinite(d[['rh','temp']].to_numpy()).all():
        raise ValueError('Nonfinite environmental values')
    rh = d['rh'].astype(float)
    temp = d['temp'].astype(float)
    if not rh.between(0.00001, 100).all() or not temp.between(10, 45).all():
        raise ValueError('Out-of-range sensor readings')
    # Magnus constants and feature definitions match preprocessing.ipynb.
    gamma = np.log(rh.iloc[-1] / 100) + 17.62 * temp.iloc[-1] / (243.12 + temp.iloc[-1])
    dew_point = 243.12 * gamma / (17.62 - gamma)
    vals = {
        'rh': rh.iloc[-1], 'temp': temp.iloc[-1],
        'dew_point': dew_point, 'dew_margin': temp.iloc[-1] - dew_point,
        'rh_mean_24h': rh.tail(288).mean(), 'rh_mean_60D': rh.mean(),
        'rh_std_24h': rh.tail(288).std(),
        'rh_change_1h': rh.iloc[-1] - rh.iloc[-13],
        'frac_above80_60D': (rh >= 80).mean(),
    }
    return pd.DataFrame([vals], columns=FEATURES)


def read_room_history(csv_path: str, room_id: str, latest_rows: int = HISTORY_ROWS) -> list[dict]:
    """Read last N raw v6 rows of one room without loading whole CSV into memory.

    This loads synthetic historical measurements for a demonstration warm start;
    no future true labels or mold_index values enter cloud/ML input.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Historical CSV not found: {path}")
    needed = {'timestamp','room_id','rh','temp','voc_resistance'}
    result = deque(maxlen=latest_rows)
    for chunk in pd.read_csv(path, chunksize=50000, usecols=lambda c: c in needed):
        if not needed.issubset(chunk.columns):
            raise ValueError('Historical CSV lacks required columns: '+str(needed-set(chunk.columns)))
        matches = chunk[chunk['room_id'] == room_id]
        for _, r in matches.iterrows():
            stamp = pd.Timestamp(r['timestamp'])
            if stamp.tzinfo is None:
                stamp = stamp.tz_localize('Asia/Manila')
            else:
                stamp = stamp.tz_convert('Asia/Manila')
            result.append({
                'room_id': room_id, 'node_id': f'esp32_{room_id}',
                'timestamp': stamp.isoformat(timespec='seconds'), 'complete': True,
                'temp': float(r['temp']), 'rh': float(r['rh']),
                'voc_resistance': float(r['voc_resistance']),
                'source': 'synthetic_sil'
            })
    return list(result)


def seed_cloud(cloud, records: list[dict]) -> datetime:
    """Add historical summaries to virtual cloud and return next 5-min time."""
    if len(records) < HISTORY_ROWS:
        raise ValueError('The selected room has fewer than 60 days of history')
    # Check BEFORE altering the cloud.
    latest_features(records)
    for row in records:
        cloud.receive(row)
    return datetime.fromisoformat(records[-1]['timestamp']) + timedelta(minutes=5)
