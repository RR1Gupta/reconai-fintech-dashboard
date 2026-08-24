"""
ai_investigator.py
Takes the deterministic exceptions found by reconciliation.py and asks
Claude to (a) explain each one in plain language for a finance-ops person,
and (b) suggest a bounded next action. The AI never re-decides WHAT is an
exception -- that's already been decided deterministically. It only adds
the human-readable reasoning layer on top, which is the "audit trail".

Requires ANTHROPIC_API_KEY to be set in the environment.
"""

import json
import os
import time
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a finance-ops assistant. You will be given a single \
reconciliation exception found by a deterministic matching engine (orders vs \
payments vs settlements, for an Indian merchant using Razorpay).

For the exception given, respond with ONLY a JSON object (no markdown fences, \
no preamble) with exactly these keys:
- "explanation": one or two plain-English sentences explaining what likely \
  happened and why it matters financially. Write for a non-technical ops person.
- "suggested_action": one concrete, bounded next step someone should take \
  (e.g. "Check settlement batch dated X" or "Contact customer to confirm refund \
  amount"). Do not suggest anything that moves money automatically -- \
  suggestions only, never an executed action.
- "confidence": "high", "medium", or "low" -- your confidence that this \
  explanation is the correct root cause given only the fields provided.
"""


def explain_exception(client, exception: dict) -> dict:
    user_content = (
        "Reconciliation exception (from deterministic matching engine):\n"
        + json.dumps(exception, indent=2)
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw_text = response.content[0].text.strip()
    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        parsed = {
            "explanation": "AI response could not be parsed as JSON.",
            "suggested_action": "Review manually.",
            "confidence": "low",
            "_raw_response": raw_text,
        }
    return parsed


def investigate_all(reconciliation_results_path="reconciliation_results.json",
                     output_path="reconciliation_results_annotated.json",
                     sleep_between_calls=0.0):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Export it before running: "
            "export ANTHROPIC_API_KEY=sk-ant-..."
        )
    client = Anthropic(api_key=api_key)

    with open(reconciliation_results_path) as f:
        results = json.load(f)

    annotated = []
    for exc in results["exceptions"]:
        ai_notes = explain_exception(client, exc)
        annotated.append({**exc, "ai_investigation": ai_notes})
        if sleep_between_calls:
            time.sleep(sleep_between_calls)

    results["exceptions"] = annotated
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Annotated {len(annotated)} exceptions -> {output_path}")
    return results


if __name__ == "__main__":
    investigate_all()
