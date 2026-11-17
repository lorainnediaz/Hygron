"""Local SQLite handoff: synthetic five-minute gateway summaries shared by two Streamlit apps.
Only run both apps on the same filesystem. No physical telemetry or cross-host sync.
"""
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(os.environ.get('HYGRON_DB_PATH', str(Path(__file__).resolve().parent / 'data' / 'hygron_demo.sqlite3')))


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=30)
    db.execute('PRAGMA busy_timeout=30000')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('''CREATE TABLE IF NOT EXISTS summaries (
        room_id TEXT NOT NULL, node_id TEXT NOT NULL, timestamp TEXT NOT NULL,
        complete INTEGER NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY(room_id,node_id,timestamp))''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_history ON summaries(room_id, timestamp)')
    return db


class SQLiteCloud:
    def receive(self, summary):
        self.receive_many([summary])

    def receive_many(self, summaries):
        values = []
        for summary in summaries:
            if summary.get('source') != 'synthetic_sil':
                raise ValueError('Only synthetic SIL summaries accepted')
            required = ('room_id','node_id','timestamp','complete','temp','rh','voc_resistance')
            if any(k not in summary for k in required):
                raise ValueError('Missing summary fields')
            if datetime.fromisoformat(summary['timestamp']).tzinfo is None:
                raise ValueError('A timezone-aware timestamp is required')
            values.append((str(summary['room_id']),str(summary['node_id']),summary['timestamp'],
                           int(bool(summary['complete'])),summary['source'],json.dumps(summary,allow_nan=False)))
        with connect() as db:
            db.executemany('INSERT OR REPLACE INTO summaries VALUES (?,?,?,?,?,?)',values)

    def history(self, room_id, complete_only=True, limit=None):
        query = 'SELECT payload FROM summaries WHERE room_id=?'
        if complete_only:
            query += ' AND complete=1'
        query += ' ORDER BY timestamp DESC'
        if limit is not None:
            query += ' LIMIT ?'
        with connect() as db:
            values=db.execute(query, (room_id, int(limit)) if limit is not None else (room_id,)).fetchall()
        return [json.loads(v[0]) for v in reversed(values)]

    def latest_timestamp(self, room_id=None):
        with connect() as db:
            if room_id:
                row=db.execute('SELECT MAX(timestamp) FROM summaries WHERE room_id=?',(room_id,)).fetchone()
            else:
                row=db.execute('SELECT MAX(timestamp) FROM summaries').fetchone()
        return datetime.fromisoformat(row[0]) if row[0] else None

    def status(self):
        with connect() as db:
            all_count, complete = db.execute('SELECT COUNT(*),COALESCE(SUM(complete),0) FROM summaries').fetchone()
        return {'stored_summaries':all_count,'valid_for_history':complete,'incomplete':all_count-complete}

    def has_room(self, room_id):
        with connect() as db:
            return bool(db.execute('SELECT 1 FROM summaries WHERE room_id=? LIMIT 1',(room_id,)).fetchone())

    def seed_room_if_empty(self, room_id, make_rows):
        """Seed once only, using a write lock to avoid two servers racing."""
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # A user may launch the simulator before the dashboard. In that case
            # keep generated readings and backfill only the missing warm-start history.
            oldest = db.execute('SELECT MIN(timestamp) FROM summaries WHERE room_id=?',(room_id,)).fetchone()[0]
            if oldest is not None and oldest < '2026-08-30':
                return False
            rows=make_rows()
            values=[(r['room_id'],r['node_id'],r['timestamp'],int(r['complete']),r['source'],json.dumps(r,allow_nan=False)) for r in rows]
            db.executemany('INSERT OR IGNORE INTO summaries VALUES (?,?,?,?,?,?)',values)
        return True
