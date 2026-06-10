"""Layer 7 — Tamper-evident audit trail (mock-blockchain ready).

Each analyzed case is appended to a JSONL ledger where every entry embeds
the SHA-256 of the previous entry, so any retroactive edit breaks the
chain. Swapping this file for a real ledger/chain is a storage change only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parent.parent / "data" / "audit_ledger.jsonl"
_GENESIS = "0" * 64


def _last_hash() -> str:
    if not LEDGER_PATH.exists():
        return _GENESIS
    last = None
    with LEDGER_PATH.open() as fh:
        for line in fh:
            if line.strip():
                last = line
    return json.loads(last)["entry_hash"] if last else _GENESIS


def record(case_id: str, document_hashes: dict[str, str], fraud_score: int,
           risk_band: str) -> dict:
    entry = {
        "case_id": case_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "document_hashes": document_hashes,
        "fraud_score": fraud_score,
        "risk_band": risk_band,
        "prev_hash": _last_hash(),
    }
    entry["entry_hash"] = hashlib.sha256(
        json.dumps(entry, sort_keys=True).encode()
    ).hexdigest()

    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def verify_chain() -> tuple[bool, int]:
    """Re-walk the ledger; returns (intact, entry_count)."""
    if not LEDGER_PATH.exists():
        return True, 0
    prev = _GENESIS
    count = 0
    with LEDGER_PATH.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            entry = json.loads(line)
            claimed = entry.pop("entry_hash")
            if entry.get("prev_hash") != prev:
                return False, count
            if hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest() != claimed:
                return False, count
            prev = claimed
            count += 1
    return True, count
