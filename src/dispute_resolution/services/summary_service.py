from dispute_resolution.llm.client import llm
from dispute_resolution.llm.prompts import SUMMARY_PROMPT
from dispute_resolution.utils.llm import normalize_llm_content

def generate_dispute_summary(subject: str, body: str) -> str:
    prompt = SUMMARY_PROMPT.format(subject=subject, body=body)
    response = llm.invoke(prompt)
    return normalize_llm_content(response.content).strip()