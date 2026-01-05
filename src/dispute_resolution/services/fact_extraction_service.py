import json
import re
from typing import Any, Dict, List

from dispute_resolution.llm.client import llm
from dispute_resolution.utils.llm import normalize_llm_content
from dispute_resolution.utils.logging import logger
from dispute_resolution.llm.prompts import FACT_EXTRACTION_PROMPT


# =================================================
# Canonical empty schema
# =================================================

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


# =================================================
# Helper: robust JSON extraction
# =================================================

def _safe_extract_json(text: str) -> Dict[str, Any] | None:
    """
    Extract the first valid JSON object from LLM output.
    Handles markdown, prose, and partial responses.
    """
    text = text.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Regex fallback (first JSON object)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    return None


# =================================================
# Helper: deterministic missing-field inference
# =================================================

def _infer_missing_fields(facts: Dict[str, Any]) -> List[str]:
    """
    Determine missing fields based on schema completeness.
    This is deterministic and does NOT rely on the LLM.
    """
    missing: List[str] = []

    ci = facts["commercial_identifiers"]
    fin = facts["financials"]
    issue = facts["issue"]
    action = facts["requested_action"]

    if not ci.get("invoice_numbers"):
        missing.append("commercial_identifiers.invoice_numbers")

    if not ci.get("purchase_order_numbers"):
        missing.append("commercial_identifiers.purchase_order_numbers")

    if fin.get("expected_amount") is None:
        missing.append("financials.expected_amount")

    if fin.get("paid_amount") is None:
        missing.append("financials.paid_amount")

    if issue.get("category") in (None, "UNKNOWN"):
        missing.append("issue.category")

    if action.get("type") in (None, "UNKNOWN"):
        missing.append("requested_action.type")

    return missing


# =================================================
# Enum validation
# =================================================

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


# =================================================
# Public API
# =================================================

def extract_facts(
    *,
    subject: str,
    body: str,
) -> Dict[str, Any]:
    """
    Extract structured dispute facts from an email.

    Guarantees:
    - never raises
    - never decides intent
    - never sends emails
    - always returns a complete canonical structure
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
    data = _safe_extract_json(raw)

    if not data:
        logger.error("Failed to parse fact extraction JSON")
        normalized = EMPTY_EXTRACTION.copy()
    else:
        normalized = EMPTY_EXTRACTION.copy()

        # Shallow, type-safe merge
        for key in normalized:
            if key in data and isinstance(data[key], type(normalized[key])):
                normalized[key] = data[key]

    # Enum validation
    _normalize_enums(normalized)

    # -------------------------------------------------
    # 🔑 CRITICAL FIX: deterministic missing fields
    # -------------------------------------------------
    inferred_missing = _infer_missing_fields(normalized["facts"])
    normalized["missing_fields"] = inferred_missing

    return normalized
