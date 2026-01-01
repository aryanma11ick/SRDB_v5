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
        logger.error("Intent classifier returned invalid JSON")
        logger.error(raw)
        return {
            "intent": "AMBIGUOUS",
            "confidence_score": 0.0,
            "reason": "Could not parse LLM response",
        }

    intent = result.get("intent")
    reason = result.get("reason", "")
    score = result.get("confidence_score")

    # ---- Basic validation ----
    if intent not in {"DISPUTE", "NOT_DISPUTE"}:
        logger.warning("Invalid intent returned, defaulting to AMBIGUOUS")
        return {
            "intent": "AMBIGUOUS",
            "confidence_score": 0.0,
            "reason": "Invalid intent value from LLM",
        }

    try:
        score = float(score)
    except (TypeError, ValueError):
        logger.warning("Invalid confidence_score, defaulting to AMBIGUOUS")
        return {
            "intent": "AMBIGUOUS",
            "confidence_score": 0.0,
            "reason": "Invalid confidence score from LLM",
        }

    # ---- Deterministic normalization ----
    if intent == "DISPUTE":
        if score >= CONFIDENCE_THRESHOLD:
            return {
                "intent": "DISPUTE",
                "confidence_score": score,
                "reason": reason,
            }
        else:
            return {
                "intent": "AMBIGUOUS",
                "confidence_score": score,
                "reason": reason,
            }

    # intent == NOT_DISPUTE
    return {
        "intent": "NOT_DISPUTE",
        "confidence_score": score,
        "reason": reason,
    }
