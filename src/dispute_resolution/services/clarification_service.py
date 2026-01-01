from typing import Any
from dispute_resolution.llm.client import llm
from dispute_resolution.llm.prompts import CLARIFICATION_PROMPT


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
    prompt = CLARIFICATION_PROMPT.format(
        subject=subject,
        body=body,
    )

    response = llm.invoke(prompt)

    text = _normalize_llm_content(response.content)
    return text.strip()
