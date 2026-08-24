"""
test_reconciliation.py
Validates the reconciliation engine's output against data/answer_key.json --
the ground-truth list of exceptions we deliberately injected. This is what
lets us claim a real, checkable accuracy number instead of an unverifiable one.

Run: python -m pytest test_reconciliation.py -v
"""

import json
import subprocess
import sys
import pytest

import reconciliation


@pytest.fixture(scope="module")
def regenerate_data():
    subprocess.run([sys.executable, "generate_data.py", "--n", "60", "--seed", "42"], check=True)


@pytest.fixture(scope="module")
def result(regenerate_data):
    return reconciliation.reconcile("data/orders.csv", "data/payments.csv", "data/settlements.csv")


@pytest.fixture(scope="module")
def answer_key(regenerate_data):
    with open("data/answer_key.json") as f:
        return json.load(f)


def test_total_payments_positive(result):
    assert result["total_payments"] > 0


def test_match_rate_in_valid_range(result):
    assert 0 <= result["match_rate_pct"] <= 100


def test_finds_all_injected_exceptions(result, answer_key):
    """Every payment_id we deliberately broke must appear in the exceptions list."""
    found_payment_ids = {e.get("payment_id") for e in result["exceptions"]}
    for injected in answer_key:
        pid = injected.get("payment_id")
        assert pid in found_payment_ids, f"Engine missed injected exception: {injected}"


def test_finds_missing_settlement(result, answer_key):
    injected_types = {e["type"] for e in answer_key}
    found_types = {e["type"] for e in result["exceptions"]}
    if "missing_settlement" in injected_types:
        assert "missing_settlement" in found_types


def test_finds_fee_mismatch(result, answer_key):
    found_types = {e["type"] for e in result["exceptions"]}
    injected_types = {e["type"] for e in answer_key}
    if "fee_mismatch" in injected_types:
        assert "fee_mismatch" in found_types


def test_finds_duplicate_payment(result, answer_key):
    found_types = {e["type"] for e in result["exceptions"]}
    injected_types = {e["type"] for e in answer_key}
    if "duplicate_payment" in injected_types:
        assert "duplicate_payment" in found_types


def test_finds_orphan_settlement(result, answer_key):
    found_types = {e["type"] for e in result["exceptions"]}
    injected_types = {e["type"] for e in answer_key}
    if "orphan_settlement" in injected_types:
        assert "orphan_settlement" in found_types


def test_finds_partial_refund(result, answer_key):
    found_types = {e["type"] for e in result["exceptions"]}
    injected_types = {e["type"] for e in answer_key}
    if "refund_partial" in injected_types:
        assert "refund_partial" in found_types


def test_clean_matches_plus_exceptions_reasonable(result):
    # clean_matches should never exceed total payments
    assert result["clean_matches"] <= result["total_payments"]


def test_no_duplicate_exception_objects(result):
    # sanity: exceptions list shouldn't have exact duplicate entries
    seen = set()
    for e in result["exceptions"]:
        key = (e["type"], e.get("payment_id"), e.get("settlement_id"))
        assert key not in seen, f"Duplicate exception entry: {e}"
        seen.add(key)
