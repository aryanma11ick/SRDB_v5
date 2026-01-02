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
EXTRACT_AND_CLARIFY_PROMPT = """
You are an automated accounts-payable system analyzing supplier emails.

Your job has TWO steps:
1) Extract structured facts from the email
2) Write ONE clarification reply ONLY if information is missing

==================================================
STEP 1: EXTRACT FACTS (STRICT)
==================================================

Extract ONLY what is explicitly present in the email.
DO NOT infer or assume missing details.

Extract:
- invoice_numbers: list of invoice numbers explicitly mentioned, or []
- amounts: list of monetary amounts explicitly mentioned, or []
- issue_type:
    OVERCHARGE | UNDERPAYMENT | MISSING_PAYMENT | INVOICE_ERROR | CONTRACT_DISPUTE | OTHER | UNCLEAR
- desired_action:
    CREDIT | EXPLANATION | PAYMENT | CORRECTION | UNCLEAR

==================================================
STEP 2: DETERMINE MISSING INFORMATION
==================================================

Rules:
- If invoice_numbers is NOT empty → DO NOT ask for invoice number
- If amounts is NOT empty → DO NOT ask for amounts
- If issue_type is NOT UNCLEAR → DO NOT ask what the issue is
- If desired_action is NOT UNCLEAR → DO NOT ask what action they want

==================================================
STEP 3: GENERATE CLARIFICATION EMAIL
==================================================

If missing_info is NOT empty:
- Write ONE concise clarification email body requesting ONLY the missing information
- MAXIMUM 3–4 sentences
- No greeting, subject, or signature

If missing_info IS empty:
- email_body MUST be an empty string ""

==================================================
OUTPUT FORMAT (STRICT JSON ONLY)
==================================================

{{
  "extracted_facts": {{
    "invoice_numbers": [],
    "amounts": [],
    "issue_type": "UNCLEAR",
    "desired_action": "UNCLEAR",
    "missing_info": []
  }},
  "email_body": ""
}}

==================================================
EMAIL TO ANALYZE
==================================================

Subject: {subject}
Body:
{body}
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



DISPUTE_CANONICAL_SUMMARY_PROMPT = """
You are maintaining a canonical dispute record.

Below are multiple emails exchanged regarding the SAME dispute.
Your task is to produce a single, concise, factual dispute summary.

Rules:
- Consolidate information across all emails
- Resolve partial information if clarified later
- Do NOT speculate
- Mention invoice numbers, PO numbers, amounts ONLY if explicitly stated
- Keep the summary suitable for internal accounting and audit teams

Emails:
{body}
"""