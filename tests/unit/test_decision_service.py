from dispute_resolution.services.decision_service import decide_dispute

# Candidate dispute (from vector search)
candidate_disputes = [
    {
        "id": "1889bfed-2ec2-46f2-83e4-735a07144f7d",
        "summary": (
            "An overcharge was identified on Invoice INV-9123, "
            "where the invoiced amount of INR 18,750 exceeds the agreed "
            "purchase order value of INR 16,500."
        ),
    }
]

# ---- TEST 1: Follow-up email (should MATCH) ----
decision_1 = decide_dispute(
    subject="Follow-up on Invoice INV-9123 overcharge",
    body=(
        "Hi AP Team,\n\n"
        "Following up on the overcharge for Invoice INV-9123. "
        "Please let us know the status of the revised invoice.\n\n"
        "Regards,\nRohit"
    ),
    candidate_disputes=candidate_disputes,
)

print("TEST 1 RESULT:", decision_1)


# ---- TEST 2: Different invoice (should be NEW) ----
decision_2 = decide_dispute(
    subject="Overcharge identified on Invoice INV-9999",
    body=(
        "Hi AP Team,\n\n"
        "We noticed an overcharge on Invoice INV-9999. "
        "The amount billed does not match the PO.\n\n"
        "Regards,\nRohit"
    ),
    candidate_disputes=candidate_disputes,
)

print("TEST 2 RESULT:", decision_2)
