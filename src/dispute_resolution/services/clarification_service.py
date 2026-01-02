import json
from typing import Any, Dict
from dispute_resolution.llm.client import llm
from dispute_resolution.llm.prompts import EXTRACT_AND_CLARIFY_PROMPT
from dispute_resolution.utils.llm import normalize_llm_content


def extract_facts_and_clarification(subject: str, body: str) -> Dict[str, Any]:
    """
    Returns structured extraction + optional clarification email.

    {
      "facts": {
        "invoice_numbers": [...],
        "amounts": [...],
        "issue_type": "...",
        "desired_action": "...",
        "missing_info": [...]
      },
      "email_body": "clarification text or empty string"
    }
    """

    response = llm.invoke(
        EXTRACT_AND_CLARIFY_PROMPT.format(subject=subject, body=body)
    )

    raw = normalize_llm_content(response.content).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # SAFETY FALLBACK
        return {
            "facts": {
                "invoice_numbers": [],
                "amounts": [],
                "issue_type": "UNCLEAR",
                "desired_action": "UNCLEAR",
                "missing_info": [],
            },
            "email_body": "",
        }

    return {
        "facts": data.get("extracted_facts", {}),
        "email_body": data.get("email_body", "").strip(),
    }
