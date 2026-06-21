import logging
from typing import List

from config import config

logger = logging.getLogger(__name__)


def get_slow_queries() -> List[dict]:
    """Return currently running slow queries."""
    if config.simulation_mode:
        from monitors.database import DatabaseMonitor

        return DatabaseMonitor().get_slow_queries()

    try:
        import psycopg2

        conn = psycopg2.connect(config.db_url)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT pid, now() - query_start AS duration, query, state
            FROM pg_stat_activity
            WHERE state != 'idle'
              AND query_start IS NOT NULL
              AND now() - query_start > interval '%s milliseconds'
            ORDER BY duration DESC
        """,
            (config.slow_query_threshold_ms,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            {
                "pid": r[0],
                "duration_ms": r[1].total_seconds() * 1000,
                "query": r[2],
                "state": r[3],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("get_slow_queries failed: %s", e)
        return []


def kill_slow_queries() -> str:
    """Kill all queries exceeding the slow query threshold."""
    queries = get_slow_queries()
    if not queries:
        return "No slow queries found to kill."

    if config.simulation_mode:
        pids = [q["pid"] for q in queries]
        logger.info("[SIMULATION] Would kill PIDs: %s", pids)
        return f"[SIMULATION] Killed {len(pids)} slow queries with PIDs: {pids}"

    try:
        import psycopg2

        conn = psycopg2.connect(config.db_url)
        cur = conn.cursor()
        killed = []
        for q in queries:
            cur.execute("SELECT pg_terminate_backend(%s)", (q["pid"],))
            killed.append(q["pid"])
        conn.commit()
        cur.close()
        conn.close()
        return f"Killed {len(killed)} slow queries: PIDs {killed}"
    except Exception as e:
        logger.error("kill_slow_queries failed: %s", e)
        return f"Failed to kill queries: {e}"


def explain_query(query: str) -> str:
    """Run EXPLAIN ANALYZE on a query (simulation returns mock output)."""
    if config.simulation_mode:
        return f"[SIMULATION] EXPLAIN for: {query[:80]}...\nSeq Scan on orders (cost=0.00..45231.00 rows=1000000 width=8)\nMissing index on user_id column."
    try:
        import psycopg2

        conn = psycopg2.connect(config.db_url)
        cur = conn.cursor()
        cur.execute(f"EXPLAIN ANALYZE {query}")
        plan = "\n".join(row[0] for row in cur.fetchall())
        cur.close()
        conn.close()
        return plan
    except Exception as e:
        return f"EXPLAIN failed: {e}"
