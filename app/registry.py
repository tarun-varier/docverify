"""Layer 4 — Lightweight external correlation against mock registries.

Validates PAN structure, looks up CIN status and land survey numbers in
local mock registries (JSON under data/registries/). The lookup interface
is deliberately thin so the same calls can be re-pointed at CERSAI, ROC
and state land-record APIs in production.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Anomaly, DocType, DocumentReport, Severity

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "data" / "registries"

_PAN_STRUCTURE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
# 4th character encodes holder type; these are the valid codes.
_PAN_HOLDER_TYPES = set("PCFHATBLJG")


def _load(name: str) -> dict:
    path = REGISTRY_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def run(docs: list[DocumentReport]) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    land_registry = _load("land_records.json")
    cin_registry = _load("cin_registry.json")

    for doc in docs:
        f = doc.fields

        if f.pan:
            if not _PAN_STRUCTURE.match(f.pan) or f.pan[3] not in _PAN_HOLDER_TYPES:
                anomalies.append(Anomaly(
                    code="PAN_STRUCTURE_INVALID",
                    layer="registry",
                    severity=Severity.CRITICAL,
                    title="PAN fails structural validation",
                    detail=f"'{f.pan}' on {doc.filename} does not conform to the "
                           "Income Tax Department PAN format.",
                    documents=[doc.filename],
                    evidence={"pan": f.pan},
                ))

        if f.cin:
            record = cin_registry.get(f.cin)
            if record is None:
                anomalies.append(Anomaly(
                    code="CIN_NOT_FOUND",
                    layer="registry",
                    severity=Severity.HIGH,
                    title="CIN not found in company registry",
                    detail=f"CIN {f.cin} on {doc.filename} has no match in the ROC registry.",
                    documents=[doc.filename],
                    evidence={"cin": f.cin},
                ))
            elif record.get("status", "").lower() != "active":
                anomalies.append(Anomaly(
                    code="CIN_INACTIVE",
                    layer="registry",
                    severity=Severity.HIGH,
                    title="Employer company is not active",
                    detail=f"CIN {f.cin} ({record.get('name')}) has ROC status "
                           f"'{record.get('status')}'.",
                    documents=[doc.filename],
                    evidence={"cin": f.cin, "record": record},
                ))

        if doc.doc_type == DocType.LAND_RECORD and f.survey_number:
            record = land_registry.get(f.survey_number)
            if record is None:
                anomalies.append(Anomaly(
                    code="SURVEY_NOT_FOUND",
                    layer="registry",
                    severity=Severity.HIGH,
                    title="Survey number absent from land registry",
                    detail=f"Survey number {f.survey_number} on {doc.filename} has no "
                           "entry in the state land-record registry.",
                    documents=[doc.filename],
                    evidence={"survey_number": f.survey_number},
                ))
            else:
                owner = record.get("owner", "")
                claimed = f.applicant_name or ""
                if claimed and owner and owner.lower().strip() != claimed.lower().strip():
                    anomalies.append(Anomaly(
                        code="OWNERSHIP_CONFLICT",
                        layer="registry",
                        severity=Severity.CRITICAL,
                        title="Registry owner differs from document owner",
                        detail=(
                            f"Land registry lists survey no. {f.survey_number} under "
                            f"'{owner}', but {doc.filename} names '{claimed}'."
                        ),
                        documents=[doc.filename],
                        evidence={"registry_owner": owner, "document_owner": claimed},
                    ))
                reg_date = record.get("last_transfer_date")
                doc_reg = f.registration_date
                if reg_date and doc_reg and reg_date != doc_reg:
                    anomalies.append(Anomaly(
                        code="REGISTRATION_DATE_CONFLICT",
                        layer="registry",
                        severity=Severity.HIGH,
                        title="Registration date conflicts with registry",
                        detail=(
                            f"Document claims registration on {doc_reg} but the registry "
                            f"records the last transfer of survey no. {f.survey_number} "
                            f"on {reg_date}."
                        ),
                        documents=[doc.filename],
                        evidence={"document_date": doc_reg, "registry_date": reg_date},
                    ))

    return anomalies
