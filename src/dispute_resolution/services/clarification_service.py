from typing import Dict, List, Any
import json

from dispute_resolution.llm.client import llm
from dispute_resolution.utils.llm import normalize_llm_content
from dispute_resolution.utils.logging import logger
from dispute_resolution.llm.prompts import CLARIFICATION_PROMPT
from dispute_resolution.models import Email

from datetime import datetime, timezone, timedelta

def build_clarification_email(
    *,
    known_facts: Dict[str, Any],
    missing_fields: List[str],
) -> str:
    """
    Generate an intelligent clarification email using LLM,
    constrained strictly by extracted facts and missing fields.
    """

    if not missing_fields:
        logger.warning("Clarification requested but no missing fields provided")
        return ""

    prompt = CLARIFICATION_PROMPT.format(
        known_facts=json.dumps(known_facts, indent=2),
        missing_fields=json.dumps(missing_fields, indent=2),
    )

    logger.info("Generating intelligent clarification email")

    response = llm.invoke(prompt)
    return normalize_llm_content(response.content).strip()


def is_ambiguous_expired(email: Email) -> bool:
    if not email.clarification_sent_at:
        return False

    return datetime.now(timezone.utc) > (
        email.clarification_sent_at + timedelta(hours=24)
    )