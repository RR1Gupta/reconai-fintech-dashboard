"""
app.py
Minimal Flask backend. One route runs the reconciliation engine + (optionally)
the AI investigator, and returns JSON. The frontend is a single static HTML
page that calls this endpoint when you click "Run Reconciliation".

Run locally:
    export ANTHROPIC_API_KEY=sk-ant-...   # optional, only needed for AI notes
    python app.py
Then open http://localhost:5000
"""

import os
import json
from flask import Flask, jsonify, send_from_directory, request

import reconciliation

app = Flask(__name__, static_folder="static", static_url_path="")

DATA_DIR = "data"


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/run-reconciliation", methods=["POST"])
def run_reconciliation():
    use_ai = request.args.get("use_ai", "false").lower() == "true"

    try:
        result = reconciliation.reconcile(
            f"{DATA_DIR}/orders.csv",
            f"{DATA_DIR}/payments.csv",
            f"{DATA_DIR}/settlements.csv",
        )
    except FileNotFoundError as e:
        return jsonify({"error": f"Data file missing: {e}"}), 500

    with open("reconciliation_results.json", "w") as f:
        json.dump(result, f, indent=2)

    if use_ai:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return jsonify({"error": "ANTHROPIC_API_KEY not set on server."}), 500
        try:
            import ai_investigator
            result = ai_investigator.investigate_all()
        except Exception as e:
            # Never let an AI-layer failure crash into an HTML error page --
            # the base reconciliation result is still valid, so return it
            # with the error attached instead of losing everything.
            result["ai_error"] = f"{type(e).__name__}: {e}"

    return jsonify(result)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
