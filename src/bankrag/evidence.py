"""Fail-closed validation for answer evidence chains."""

from __future__ import annotations

from urllib.parse import urlparse

OFFICIAL_DOMAINS = {"icbc.com.cn", "www.icbc.com.cn", "v.icbc.com.cn"}
VALID_STATUSES = {
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
    "stale_evidence",
}


def _official(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in OFFICIAL_DOMAINS or host.endswith(".icbc.com.cn")


def validate_answer(payload: dict) -> list[str]:
    """Return validation errors; an empty list means the answer may be shown."""
    errors: list[str] = []
    status = payload.get("status")
    if status not in VALID_STATUSES:
        errors.append("invalid status")

    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        return errors + ["at least one claim is required"]

    for claim_index, claim in enumerate(claims):
        prefix = f"claims[{claim_index}]"
        if not str(claim.get("claim", "")).strip():
            errors.append(f"{prefix}.claim is required")
        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{prefix}.evidence is required")
            continue
        for evidence_index, item in enumerate(evidence):
            ep = f"{prefix}.evidence[{evidence_index}]"
            for field in ("document_id", "chunk_id", "quote", "source_url", "retrieved_at"):
                if not str(item.get(field, "")).strip():
                    errors.append(f"{ep}.{field} is required")
            url = str(item.get("source_url", ""))
            if url and not _official(url):
                errors.append(f"{ep}.source_url is not an approved official domain")

    if status == "supported" and errors:
        errors.append("supported answers must have a complete evidence chain")
    return errors


def can_publish(payload: dict) -> bool:
    """Only fully supported and valid answers can be presented as factual."""
    return payload.get("status") == "supported" and not validate_answer(payload)
