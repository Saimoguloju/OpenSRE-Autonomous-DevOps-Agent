import sqlite3
import json
from datetime import datetime, UTC
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
            # Dynamic schema migrations
            cursor = conn.execute("PRAGMA table_info(incidents)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "confidence_score" not in columns:
                conn.execute("ALTER TABLE incidents ADD COLUMN confidence_score INTEGER")
            if "critique" not in columns:
                conn.execute("ALTER TABLE incidents ADD COLUMN critique TEXT")
            conn.commit()

    def save(self, incident: IncidentState):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO incidents (
                    incident_id, metric_json, severity, root_cause,
                    recommended_action, action_taken, status,
                    slack_message_ts, human_approved, created_at, updated_at,
                    confidence_score, critique
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    root_cause=excluded.root_cause,
                    recommended_action=excluded.recommended_action,
                    action_taken=excluded.action_taken,
                    status=excluded.status,
                    slack_message_ts=excluded.slack_message_ts,
                    human_approved=excluded.human_approved,
                    updated_at=excluded.updated_at,
                    confidence_score=excluded.confidence_score,
                    critique=excluded.critique
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
                incident.get("confidence_score"),
                incident.get("critique"),
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

    def get_similar_resolved(self, source: str, name: str, limit: int = 3) -> List[IncidentState]:
        """
        Retrieves past resolved incidents ranked using a custom NLP TF Cosine Similarity search
        to ensure semantic match over raw text.
        """
        import re
        import math
        from collections import Counter

        def tokenize(text: str) -> list:
            if not text:
                return []
            words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
            stop_words = {"the", "and", "for", "with", "this", "that", "from", "was", "were"}
            return [w for w in words if w not in stop_words]

        # Fetch all resolved incidents to perform search locally
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM incidents WHERE status='resolved'").fetchall()
        
        all_incidents = [self._row_to_state(r) for r in rows]
        if not all_incidents:
            return []

        # Current incident target query tokens
        query_text = f"{source} {name}"
        query_tokens = tokenize(query_text)
        if not query_tokens:
            return []

        c_query = Counter(query_tokens)
        sum_q = sum(val ** 2 for val in c_query.values())
        if sum_q == 0:
            return []

        scored_incidents = []
        for inc in all_incidents:
            # Build document representation
            doc_text = f"{inc['metric']['source']} {inc['metric']['name']} {inc.get('root_cause', '')}"
            doc_tokens = tokenize(doc_text)
            if not doc_tokens:
                continue

            c_doc = Counter(doc_tokens)
            intersection = set(c_query.keys()) & set(c_doc.keys())
            numerator = sum(c_query[x] * c_doc[x] for x in intersection)
            sum_d = sum(val ** 2 for val in c_doc.values())
            
            denominator = math.sqrt(sum_q) * math.sqrt(sum_d)
            similarity = numerator / denominator if denominator else 0.0

            if similarity > 0.05: # threshold
                scored_incidents.append((similarity, inc))

        # Rank by score descending, then return the top resolved
        scored_incidents.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_incidents[:limit]]

    def update_status(self, incident_id: str, status: str, **kwargs):
        incident = self.get(incident_id)
        if incident is None:
            return
        incident["status"] = status
        incident["updated_at"] = datetime.now(UTC).isoformat()
        for k, v in kwargs.items():
            incident[k] = v
        self.save(incident)

    def _row_to_state(self, row) -> IncidentState:
        # Graceful retrieval for migrated fields
        row_keys = row.keys()
        confidence = row["confidence_score"] if "confidence_score" in row_keys else None
        critique = row["critique"] if "critique" in row_keys else None

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
            confidence_score=confidence,
            critique=critique,
        )
