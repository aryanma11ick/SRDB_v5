# Prompt for deciding: attach to existing dispute or create new
INTENT_CLASSIFICATION_PROMPT = """
You are an accounts-payable analyst.

Classify the email into one of:
- DISPUTE: raises a billing, invoice, payment, or financial issue
- NOT_DISPUTE: informational, greetings, scheduling, acknowledgements
- AMBIGUOUS: unclear whether a dispute exists

Rules:
- If unsure, choose AMBIGUOUS
- Do not invent information

EMAIL:
Subject: {subject}
Body:
{body}

Respond ONLY in JSON:
{
  "intent": "DISPUTE | NOT_DISPUTE | AMBIGUOUS",
  "reason": "short explanation"
}
"""




CLARIFICATION_PROMPT = """
Write a polite clarification email asking the sender to confirm
whether their message relates to an invoice, payment, or billing issue.
Ask for invoice number if applicable.

Original Email:
Subject: {subject}
Body:
{body}
"""




DECISION_PROMPT = """
You are an expert accounts-payable dispute analyst.

Your task:
Decide whether the NEW EMAIL belongs to one of the EXISTING DISPUTES.

Rules:
- If the email is a continuation of the same issue (same invoice, same amounts, same problem), choose MATCH.
- If it is about a different invoice, a different issue, or a clearly new problem, choose NEW.
- If unsure, choose NEW.
- Do NOT invent facts.
- Base your decision only on the text provided.

EXISTING DISPUTES:
{disputes}

NEW EMAIL:
Subject: {subject}
Body:
{body}

Respond ONLY in valid JSON with this schema:
{{
  "action": "MATCH" or "NEW",
  "dispute_id": "<dispute_id or null>",
  "reason": "one short sentence"
}}
"""




SUMMARY_PROMPT = """
You are an accounts-payable analyst.

Write a concise dispute summary (2–4 sentences) based on the email below.
Focus on:
- the issue type
- invoice number (if present)
- amounts (if present)
- what action is requested

Do NOT invent information.

EMAIL:
Subject: {subject}
Body:
{body}
"""