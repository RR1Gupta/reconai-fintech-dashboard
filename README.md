# ReconAI — Multi-Source Payment Reconciliation Agent

Built for the Razorpay AI Buildathon — Track 04: AI Finance Controller.

## The problem

Merchants have money moving across three places that should agree but often
don't: **order records**, **payment records** (Razorpay), and **bank
settlement records**. Someone usually cross-checks these by hand every day.
This agent automates the match and flags exactly what doesn't reconcile —
with a plain-language explanation for each exception.

## How it works

1. **`reconciliation.py`** — deterministic matching engine. Links
   orders → payments → settlements by ID, verifies settlement amounts
   against expected value (payment amount minus Razorpay's fee), and
   flags anything that doesn't fit into one of five known exception types:
   `missing_settlement`, `fee_mismatch`, `duplicate_payment`,
   `orphan_settlement`, `refund_partial`. **No AI is used for matching** —
   matching should be exact, not probabilistic.

2. **`ai_investigator.py`** — takes each exception the deterministic engine
   found and calls the Claude API to explain it in plain language and
   suggest a bounded next action (never an auto-executed money action).
   This is the audit trail.

3. **`app.py`** + **`static/index.html`** — a minimal Flask web app with a
   "Run Reconciliation" button that ties it all together.

## Honest metrics (not cherry-picked)

`generate_data.py` builds a synthetic dataset of clean, correctly-linked
records, then deliberately injects a known set of broken records and writes
them to `data/answer_key.json`. This means match rate and exception recall
are **provable**, not claimed:

- 60 orders, 61 payments (1 duplicate), 60 settlements + 1 orphan
- 5 deliberately injected exceptions across all 5 categories
- Engine result: **91.8% match rate (56/61)**, 6 exceptions found
  (5 injected + 1 correctly derived: the duplicate payment also lacks its
  own settlement, which the engine correctly flags separately)
- `test_reconciliation.py` — 10 tests, all passing, asserting the engine
  finds every injected exception by type

## What broke, and how I got out of it

Initial version was scaffolded on Replit via chat-driven prompting. The
reconciliation logic worked (11/11 tests passing there too), but the web
button never reached the backend — a wiring gap between the generated
frontend and backend that ran into Replit's agent usage limits mid-debug.
Rebuilt the backend/frontend connection from scratch outside Replit with a
minimal, explicit Flask route (`/api/run-reconciliation`) instead of relying
on generated glue code, and verified the full chain end-to-end with `curl`
before touching the UI.

## Running it

```bash
# Local
pip install -r requirements.txt
python generate_data.py --n 60 --seed 42
export ANTHROPIC_API_KEY=sk-ant-...   # optional, for AI explanations
python app.py
# open http://localhost:5000

# Tests
python -m pytest test_reconciliation.py -v

# Docker
docker build -t reconai .
docker run -p 5000:5000 -e ANTHROPIC_API_KEY=sk-ant-... reconai
```

## What's deliberately out of scope

- No automatic money movement — every AI suggestion is a recommendation for
  a human to act on, never an executed action (bounded and gated, per the
  track's bar).
- Matching logic is exact/deterministic by design; AI is used only for the
  explanation layer, not the decision of what counts as an exception.
