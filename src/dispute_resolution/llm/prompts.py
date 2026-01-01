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

# Prompt for regenerating the dispute summary after adding a new email
SUMMARY_PROMPT = """
You are an expert in supplier dispute management.

Summarize the entire dispute thread concisely in 3-5 sentences.

Include:
- The main issue
- Key claims from supplier and your company
- Current status
- Important dates or amounts if relevant

Thread (chronological):
{thread}

Summary:
"""