import json
from typing import List, Dict, Any

from dispute_resolution.llm.client import llm
from dispute_resolution.llm.prompts import DECISION_PROMPT
from dispute_resolution.utils.logging import logger
from dispute_resolution.utils.llm import normalize_llm_content

def _format_disputes(disputes: List[Dict[str, Any]]) -> str:
    """
    disputes = [{"id": <uuid>, "summary": <text>}]
    """
    blocks = []
    for d in disputes:
        blocks.append(
            f"Dispute ID: {d['id']}\nSummary: {d['summary']}"
        )
    return "\n\n".join(blocks)

def _extract_json(text: str) -> str:
    """
    Removes markdown code fences if present.
    """
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        # remove first ```json / ``` line and last ```
        text = "\n".join(lines[1:-1]).strip()

    return text


def decide_dispute(
    *,
    subject: str,
    body: str,
    candidate_disputes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Returns:
    {
      "action": "MATCH" | "NEW",
      "dispute_id": "<uuid or null>",
      "reason": "<short explanation>"
    }
    """

    prompt = DECISION_PROMPT.format(
        disputes=_format_disputes(candidate_disputes),
        subject=subject,
        body=body,
    )

    logger.info("Calling LLM decision layer")

    response = llm.invoke(prompt)

    # LangChain returns an AIMessage
    raw = normalize_llm_content(response.content).strip()
    clean = _extract_json(raw)

    try:
        decision = json.loads(clean)
    except json.JSONDecodeError:
        logger.error("LLM returned non-JSON response")
        logger.error(clean)
        # Safe fallback
        return {
            "action": "NEW",
            "dispute_id": None,
            "reason": "LLM response could not be parsed",
        }

    # Minimal validation
    if decision.get("action") not in {"MATCH", "NEW"}:
        logger.warning("Invalid action from LLM, defaulting to NEW")
        return {
            "action": "NEW",
            "dispute_id": None,
            "reason": "Invalid action from LLM",
        }

    if decision["action"] == "MATCH" and not decision.get("dispute_id"):
        logger.warning("MATCH without dispute_id, defaulting to NEW")
        return {
            "action": "NEW",
            "dispute_id": None,
            "reason": "Missing dispute_id for MATCH",
        }

    return decision
