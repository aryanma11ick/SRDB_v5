import json
from typing import Any, Dict

from dispute_resolution.llm.client import llm
from dispute_resolution.utils.llm import normalize_llm_content
from dispute_resolution.utils.logging import logger
from dispute_resolution.llm.prompts import FACT_EXTRACTION_PROMPT


# -----------------------------
# Canonical empty schema
# -----------------------------

EMPTY_EXTRACTION: Dict[str, Any] = {
    "facts": {
        "commercial_identifiers": {
            "invoice_numbers": [],
            "purchase_order_numbers": [],
            "credit_note_numbers": [],
        },
        "financials": {
            "disputed_amount": {
                "value": None,
                "currency": None,
                "direction": "UNKNOWN",
            },
            "expected_amount": None,
            "paid_amount": None,
        },
        "issue": {
            "category": "UNKNOWN",
            "description": "",
        },
        "requested_action": {
            "type": "UNKNOWN",
        },
    },
    "confidence": {},
    "missing_fields": [],
    "evidence": {},
}

# -----------------------------
# Helper: safe JSON parse
# -----------------------------

def _safe_json_load(text: str) -> Dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# -----------------------------
# Public API
# -----------------------------

def extract_facts(
    *,
    subject: str,
    body: str,
) -> Dict[str, Any]:
    """
    Extract structured dispute facts from an email.

    Returns a canonical schema:
    {
        facts,
        confidence,
        missing_fields,
        evidence
    }

    This function:
    - never raises
    - never decides intent
    - never sends emails
    """

    prompt = FACT_EXTRACTION_PROMPT.format(
        schema=json.dumps(EMPTY_EXTRACTION, indent=2),
        subject=subject,
        body=body,
    )

    logger.info("Running LLM fact extraction")

    try:
        response = llm.invoke(prompt)
    except Exception:
        logger.exception("LLM call failed during fact extraction")
        return EMPTY_EXTRACTION.copy()

    raw = normalize_llm_content(response.content).strip()

    data = _safe_json_load(raw)
    if not data:
        logger.error("Failed to parse fact extraction JSON")
        return EMPTY_EXTRACTION.copy()

    # -----------------------------
    # Defensive normalization
    # -----------------------------

    normalized = EMPTY_EXTRACTION.copy()

    for key in normalized:
        if key in data and isinstance(data[key], type(normalized[key])):
            normalized[key] = data[key]

    # Ensure enums are valid
    _normalize_enums(normalized)

    # Ensure missing_fields is a list
    if not isinstance(normalized["missing_fields"], list):
        normalized["missing_fields"] = []

    return normalized


# -----------------------------
# Enum validation
# -----------------------------

def _normalize_enums(payload: Dict[str, Any]) -> None:
    issue_category = payload["facts"]["issue"].get("category")
    if issue_category not in {
        "OVERCHARGE",
        "SHORT_PAYMENT",
        "DUPLICATE",
        "TAX",
        "UNKNOWN",
    }:
        payload["facts"]["issue"]["category"] = "UNKNOWN"

    direction = payload["facts"]["financials"]["disputed_amount"].get("direction")
    if direction not in {"OVERCHARGE", "UNDERPAYMENT", "UNKNOWN"}:
        payload["facts"]["financials"]["disputed_amount"]["direction"] = "UNKNOWN"

    action = payload["facts"]["requested_action"].get("type")
    if action not in {
        "REVISED_INVOICE",
        "PAYMENT",
        "CREDIT_NOTE",
        "CLARIFICATION",
        "UNKNOWN",
    }:
        payload["facts"]["requested_action"]["type"] = "UNKNOWN"
