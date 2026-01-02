from typing import Any
from dispute_resolution.llm.client import llm
from dispute_resolution.llm.prompts import CLARIFICATION_PROMPT
from dispute_resolution.utils.llm import normalize_llm_content


def _normalize_llm_content(content: Any) -> str:
    """
    LangChain may return str | list[str] | list[dict].
    Convert everything into a single string safely.
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item))
        return "\n".join(parts)

    return str(content)


def generate_clarification_email(subject: str, body: str) -> str:
    response = llm.invoke(
        CLARIFICATION_PROMPT.format(subject=subject, body=body)
    )

    text = normalize_llm_content(response.content).strip()

    # Safety guard: remove markdown or bullet options if hallucinated
    forbidden_markers = ["Option", "Explanation", "**", "Here are"]
    for marker in forbidden_markers:
        if marker in text:
            text = text.split(marker)[0].strip()

    return text
