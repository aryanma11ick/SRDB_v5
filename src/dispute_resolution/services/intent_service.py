import json
from dispute_resolution.llm.client import llm
from dispute_resolution.llm.prompts import INTENT_CLASSIFICATION_PROMPT
from dispute_resolution.utils.logging import logger
from dispute_resolution.utils.llm import normalize_llm_content

CONFIDENCE_THRESHOLD = 0.85


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    return text


def classify_intent(subject: str, body: str) -> dict:
    """
    Returns:
    {
      "intent": "DISPUTE" | "NOT_DISPUTE" | "AMBIGUOUS",
      "confidence_score": float,
      "reason": str
    }
    """

    prompt = INTENT_CLASSIFICATION_PROMPT.format(
        subject=subject,
        body=body,
    )

    logger.info("Calling LLM intent classification")

    response = llm.invoke(prompt)
    raw = normalize_llm_content(response.content).strip()
    clean = _extract_json(raw)

    try:
        result = json.loads(clean)
    except json.JSONDecodeError:
        return {
            "intent": "AMBIGUOUS",
            "confidence_score": 0.0,
            "reason": "Could not parse LLM response",
        }

    intent = result.get("intent")
    reason = result.get("reason", "")
    confidence = result.get("confidence_score", 0.0)

    if intent not in {"DISPUTE", "NOT_DISPUTE", "AMBIGUOUS"}:
        return {
            "intent": "AMBIGUOUS",
            "confidence_score": 0.0,
            "reason": "Invalid intent value from LLM",
        }

    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(0.0, min(1.0, confidence))

    if intent == "DISPUTE" and confidence < CONFIDENCE_THRESHOLD:
        return {
            "intent": "AMBIGUOUS",
            "confidence_score": confidence,
            "reason": reason,
        }

    return {
        "intent": intent,
        "confidence_score": confidence,
        "reason": reason,
    }