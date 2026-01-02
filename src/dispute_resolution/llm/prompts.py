# Prompt for intent classification
INTENT_CLASSIFICATION_PROMPT = """
You are an accounts-payable analyst.

Classify the email.

Definitions:
- DISPUTE: clearly raises a billing, invoice, or payment issue
- NOT_DISPUTE: greetings, updates, acknowledgements, non-financial

Also provide a confidence score between 0 and 1.

Rules:
- If an invoice is mentioned but the issue is unclear, use confidence ≤ 0.6
- Be conservative; avoid false positives

EMAIL:
Subject: {subject}
Body:
{body}

Respond ONLY in JSON:
{{
  "intent": "DISPUTE | NOT_DISPUTE",
  "confidence_score": 0.0 to 1.0,
  "reason": "short explanation"
}}
"""




# Prompt for clarification email
CLARIFICATION_PROMPT = """
You are an automated accounts-payable system replying to a supplier.

Write ONE polite clarification email.

Rules:
- Write ONLY the email body
- Do NOT include explanations, options, or commentary
- Do NOT ask questions unrelated to invoice clarification
- Be concise and professional
- Assume the email is a reply in an existing thread

The goal:
Confirm whether the supplier's message relates to:
- an invoice issue
- a payment issue
- or a general billing issue

If applicable, ask them to confirm the invoice number.

Original email:
Subject: {subject}
Body:
{body}

Output ONLY the email body text.
"""



# Prompt for deciding: attach to existing dispute or create new
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



# Prompt for dispute summary generation
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
