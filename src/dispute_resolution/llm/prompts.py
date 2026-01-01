# Prompt for deciding: attach to existing dispute or create new
DECISION_PROMPT = """
You are an expert procurement dispute classifier.

Analyze the new email and compare it to the list of existing open disputes for this supplier.

Existing open disputes (if any):
{context}

New email:
Subject: {subject}
Body: {body}

Instructions:
- If the new email clearly relates to or continues one of the existing open disputes, respond with ONLY the dispute ID (UUID).
- If it's about a new issue or doesn't match any existing dispute, respond exactly with "NEW".
- Do not explain. Do not add any extra text. Respond with a single line only.

Your response:
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