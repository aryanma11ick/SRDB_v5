from typing import Any


def normalize_llm_content(content: Any) -> str:
    """
    Normalize LangChain LLM content into a plain string.

    LangChain may return:
    - str
    - list[str]
    - list[dict]
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item))
        return "\n".join(parts)

    return str(content)
