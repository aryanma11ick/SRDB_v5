import json
from dispute_resolution.llm.client import llm
from dispute_resolution.llm.prompts import INTENT_CLASSIFICATION_PROMPT
from dispute_resolution.utils.logging import logger


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
      "reason": str
    }
    """

    prompt = INTENT_CLASSIFICATION_PROMPT.format(
        subject=subject,
        body=body,
    )

    logger.info("Calling LLM intent classification")

    response = llm.invoke(prompt)
    raw = response.content
    clean = _extract_json(raw)

    try:
        result = json.loads(clean)
    except json.JSONDecodeError:
        logger.error("Intent classifier returned invalid JSON")
        logger.error(raw)
        return {
            "intent": "AMBIGUOUS",
            "reason": "Could not parse LLM response",
        }

    intent = result.get("intent")
    reason = result.get("reason", "")

    if intent not in {"DISPUTE", "NOT_DISPUTE", "AMBIGUOUS"}:
        logger.warning("Invalid intent returned, defaulting to AMBIGUOUS")
        return {
            "intent": "AMBIGUOUS",
            "reason": "Invalid intent value from LLM",
        }

    return {
        "intent": intent,
        "reason": reason,
    }
