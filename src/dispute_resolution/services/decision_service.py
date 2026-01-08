import json
from typing import List, Dict, Any, Optional

from dispute_resolution.llm.client import llm
from dispute_resolution.llm.prompts import DECISION_PROMPT
from dispute_resolution.utils.logging import logger
from dispute_resolution.utils.llm import normalize_llm_content


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    return text


def _invoice_overlap(
    extracted_facts: Dict[str, Any],
    candidate: Dict[str, Any],
) -> bool:
    """
    Hard match if invoice number appears in candidate summary.
    """
    invoices = extracted_facts.get("commercial_identifiers", {}).get(
        "invoice_numbers", []
    )

    summary = candidate.get("summary", "").lower()

    return any(inv.lower() in summary for inv in invoices)


# --------------------------------------------------
# Public API
# --------------------------------------------------

def decide_dispute(
    *,
    subject: str,
    body: str,
    extracted_facts: Dict[str, Any],
    candidate_disputes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Decide whether the email matches an existing dispute or is a new one.

    Returns:
    {
      "action": "MATCH" | "NEW",
      "dispute_id": "<uuid or None>",
      "reason": "<explainable reason>"
    }
    """

    if not candidate_disputes:
        return {
            "action": "NEW",
            "dispute_id": None,
            "reason": "No candidate disputes available",
        }

    # =================================================
    # 1. HARD DETERMINISTIC MATCH (invoice number)
    # =================================================
    for d in candidate_disputes:
        if _invoice_overlap(extracted_facts, d):
            return {
                "action": "MATCH",
                "dispute_id": d["id"],
                "reason": "Invoice number matches existing dispute",
            }

    # =================================================
    # 2. FACT-BASED LLM TIE-BREAKER (SAFE)
    # =================================================
    safe_candidates = [
    {
        "id": str(d["id"]),
        "summary": d.get("summary", "")
    }
    for d in candidate_disputes
]
    
    prompt = DECISION_PROMPT.format(
    disputes=json.dumps(safe_candidates, indent=2),
    subject=subject,
    body=body
    )

    logger.info("Calling LLM decision tie-breaker")

    response = llm.invoke(prompt)
    raw = normalize_llm_content(response.content).strip()
    clean = _extract_json(raw)

    try:
        decision = json.loads(clean)
    except json.JSONDecodeError:
        logger.error("LLM decision JSON parse failed")
        return {
            "action": "NEW",
            "dispute_id": None,
            "reason": "LLM response could not be parsed",
        }

    # =================================================
    # 3. VALIDATION & SAFETY
    # =================================================
    if decision.get("action") == "MATCH":
        dispute_id = decision.get("dispute_id")

        if dispute_id and any(d["id"] == dispute_id for d in candidate_disputes):
            return {
                "action": "MATCH",
                "dispute_id": dispute_id,
                "reason": decision.get(
                    "reason", "LLM indicated high similarity based on facts"
                ),
            }

        logger.warning("Invalid MATCH from LLM, falling back to NEW")

    return {
        "action": "NEW",
        "dispute_id": None,
        "reason": "No strong factual match with existing disputes",
    }
