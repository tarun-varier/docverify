"""Postgres persistence for analyzed cases (Step 5).

The backend persists every ``CaseResult`` it produces so the frontend can reload
a report and the audit ledger has a durable companion.  Persistence is
**best-effort and non-fatal**: if ``DATABASE_URL`` is unset (local dev without a
DB) or Postgres is unreachable, analysis still returns a result — it just isn't
stored.  This keeps the service runnable outside docker-compose while making the
DB the source of truth whenever it is present.

Results are stored whole as JSONB (the ``CaseResult`` is a self-describing
document); a few hot columns are lifted out for cheap dashboard queries.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("docverify.db")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS case_results (
    case_id            TEXT PRIMARY KEY,
    fraud_score        INTEGER,
    risk_band          TEXT,
    recommended_action TEXT,
    analyzed_at        TIMESTAMPTZ,
    result             JSONB NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_UPSERT = """
INSERT INTO case_results
    (case_id, fraud_score, risk_band, recommended_action, analyzed_at, result, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, now())
ON CONFLICT (case_id) DO UPDATE SET
    fraud_score        = EXCLUDED.fraud_score,
    risk_band          = EXCLUDED.risk_band,
    recommended_action = EXCLUDED.recommended_action,
    analyzed_at        = EXCLUDED.analyzed_at,
    result             = EXCLUDED.result,
    updated_at         = now();
"""


def is_enabled() -> bool:
    return bool(DATABASE_URL)


def _connect():
    """Open a short-lived autocommit connection, or None if unavailable."""
    if not DATABASE_URL:
        return None
    try:
        import psycopg  # imported lazily so the backend runs without the driver
    except ImportError:
        logger.warning("psycopg not installed; case persistence disabled")
        return None
    try:
        return psycopg.connect(DATABASE_URL, autocommit=True, connect_timeout=5)
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("Postgres connection failed (%s); persistence degraded", exc)
        return None


def init_db() -> bool:
    """Create the schema if possible. Safe to call repeatedly. Never raises."""
    conn = _connect()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)
        logger.info("Case-results schema ready")
        return True
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("Schema init failed: %s", exc)
        return False
    finally:
        conn.close()


def save_case_result(result: dict[str, Any]) -> bool:
    """Persist a CaseResult dict. Returns True if stored, False on any degrade."""
    conn = _connect()
    if conn is None:
        return False
    try:
        from psycopg.types.json import Json

        with conn.cursor() as cur:
            cur.execute(
                _UPSERT,
                (
                    result.get("case_id"),
                    result.get("fraud_score"),
                    result.get("risk_band"),
                    result.get("recommended_action"),
                    result.get("analyzed_at"),
                    Json(result),
                ),
            )
        return True
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("Persisting case %s failed: %s", result.get("case_id"), exc)
        return False
    finally:
        conn.close()


def get_case_result(case_id: str) -> Optional[dict[str, Any]]:
    """Fetch a persisted CaseResult, or None if absent / DB unavailable."""
    conn = _connect()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT result FROM case_results WHERE case_id = %s", (case_id,))
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("Fetching case %s failed: %s", case_id, exc)
        return None
    finally:
        conn.close()
