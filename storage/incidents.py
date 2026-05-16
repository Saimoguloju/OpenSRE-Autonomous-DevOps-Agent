import sqlite3
import json
from datetime import datetime
from typing import Optional, List
from agent.state import IncidentState


class IncidentStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    metric_json TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    root_cause TEXT,
                    recommended_action TEXT,
                    action_taken TEXT,
                    status TEXT NOT NULL,
                    slack_message_ts TEXT,
                    human_approved INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def save(self, incident: IncidentState):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    root_cause=excluded.root_cause,
                    recommended_action=excluded.recommended_action,
                    action_taken=excluded.action_taken,
                    status=excluded.status,
                    slack_message_ts=excluded.slack_message_ts,
                    human_approved=excluded.human_approved,
                    updated_at=excluded.updated_at
            """, (
                incident["incident_id"],
                json.dumps(incident["metric"]),
                incident["severity"],
                incident.get("root_cause"),
                incident.get("recommended_action"),
                incident.get("action_taken"),
                incident["status"],
                incident.get("slack_message_ts"),
                int(incident["human_approved"]) if incident.get("human_approved") is not None else None,
                incident["created_at"],
                incident["updated_at"],
            ))
            conn.commit()

    def get(self, incident_id: str) -> Optional[IncidentState]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM incidents WHERE incident_id=?", (incident_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_state(row)

    def list_recent(self, limit: int = 20) -> List[IncidentState]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_state(r) for r in rows]

    def update_status(self, incident_id: str, status: str, **kwargs):
        incident = self.get(incident_id)
        if incident is None:
            return
        incident["status"] = status
        incident["updated_at"] = datetime.utcnow().isoformat()
        for k, v in kwargs.items():
            incident[k] = v
        self.save(incident)

    def _row_to_state(self, row) -> IncidentState:
        return IncidentState(
            incident_id=row["incident_id"],
            metric=json.loads(row["metric_json"]),
            severity=row["severity"],
            root_cause=row["root_cause"],
            recommended_action=row["recommended_action"],
            action_taken=row["action_taken"],
            status=row["status"],
            slack_message_ts=row["slack_message_ts"],
            human_approved=bool(row["human_approved"]) if row["human_approved"] is not None else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
