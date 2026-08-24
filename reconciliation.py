"""
reconciliation.py
Deterministic (non-AI) matching engine. Links orders -> payments -> settlements,
verifies amounts (accounting for Razorpay's fee), and produces a list of
exceptions for anything that doesn't cleanly reconcile.

This file intentionally contains NO AI calls -- matching should be exact,
not probabilistic. The AI layer (ai_investigator.py) only explains WHY an
exception happened, in plain language, after this engine has already
found it deterministically.
"""

import csv
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

RAZORPAY_FEE_PCT = 0.02
AMOUNT_TOLERANCE = 0.5  # rupees of slack allowed for rounding


@dataclass
class Exception_:
    type: str
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    settlement_id: Optional[str] = None
    detail: str = ""
    expected_amount: Optional[float] = None
    actual_amount: Optional[float] = None


def load_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def reconcile(orders_path, payments_path, settlements_path):
    orders = {r["order_id"]: r for r in load_csv(orders_path)}
    payments = load_csv(payments_path)
    settlements = load_csv(settlements_path)

    settlements_by_payment = {}
    for s in settlements:
        settlements_by_payment.setdefault(s["payment_id"], []).append(s)

    payment_ids_seen = set()
    exceptions = []
    clean_count = 0

    # --- Walk every payment, check it links to an order and a settlement ---
    for p in payments:
        pid = p["payment_id"]
        order = orders.get(p["order_id"])
        matching_settlements = settlements_by_payment.get(pid, [])

        # Duplicate payment for same order_id
        if pid in payment_ids_seen:
            pass  # handled below by grouping
        payment_ids_seen.add(pid)

        if order is None:
            exceptions.append(Exception_(
                type="orphan_payment", payment_id=pid, order_id=p["order_id"],
                detail=f"Payment references order_id {p['order_id']} which does not exist."
            ))
            continue

        if not matching_settlements:
            exceptions.append(Exception_(
                type="missing_settlement", payment_id=pid, order_id=p["order_id"],
                detail="Payment captured but no settlement record found."
            ))
            continue

        settlement = matching_settlements[0]
        payment_amount = float(p["amount"])
        settled_amount = float(settlement["amount"])

        if p["status"] == "partially_refunded":
            exceptions.append(Exception_(
                type="refund_partial", payment_id=pid, order_id=p["order_id"],
                settlement_id=settlement["settlement_id"],
                detail="Payment marked partially refunded; settlement will not match original order amount.",
                expected_amount=payment_amount, actual_amount=settled_amount,
            ))
            continue

        expected_settled = round(payment_amount * (1 - RAZORPAY_FEE_PCT), 2)
        if abs(expected_settled - settled_amount) > AMOUNT_TOLERANCE:
            exceptions.append(Exception_(
                type="fee_mismatch", payment_id=pid, order_id=p["order_id"],
                settlement_id=settlement["settlement_id"],
                detail=f"Expected settled amount ~{expected_settled}, found {settled_amount}.",
                expected_amount=expected_settled, actual_amount=settled_amount,
            ))
            continue

        clean_count += 1

    # --- Duplicate payments: same order_id appearing more than once ---
    order_id_counts = {}
    for p in payments:
        order_id_counts.setdefault(p["order_id"], []).append(p["payment_id"])
    for order_id, pids in order_id_counts.items():
        if len(pids) > 1:
            for pid in pids[1:]:  # first one treated as the "real" one
                exceptions.append(Exception_(
                    type="duplicate_payment", payment_id=pid, order_id=order_id,
                    detail=f"Multiple payments found for order_id {order_id}: {pids}"
                ))
                clean_count -= 1 if clean_count > 0 else 0  # don't double count as clean

    # --- Orphan settlements: settlement with no matching payment at all ---
    all_payment_ids = {p["payment_id"] for p in payments}
    for s in settlements:
        if s["payment_id"] not in all_payment_ids:
            exceptions.append(Exception_(
                type="orphan_settlement", settlement_id=s["settlement_id"],
                payment_id=s["payment_id"],
                detail=f"Settlement {s['settlement_id']} references payment_id {s['payment_id']} which does not exist."
            ))

    total_payments = len(payments)
    match_rate = round(clean_count / total_payments * 100, 2) if total_payments else 0.0

    return {
        "total_payments": total_payments,
        "clean_matches": clean_count,
        "match_rate_pct": match_rate,
        "exception_count": len(exceptions),
        "exceptions": [asdict(e) for e in exceptions],
    }


if __name__ == "__main__":
    result = reconcile("data/orders.csv", "data/payments.csv", "data/settlements.csv")
    with open("reconciliation_results.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"Total payments: {result['total_payments']}")
    print(f"Clean matches: {result['clean_matches']} ({result['match_rate_pct']}%)")
    print(f"Exceptions found: {result['exception_count']}")
    for e in result["exceptions"]:
        print(f"  - [{e['type']}] {e['detail']}")
