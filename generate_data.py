"""
generate_data.py
Generates synthetic orders.csv, payments.csv, settlements.csv for the
reconciliation agent, PLUS an answer_key.json listing every record we
deliberately broke and why. This lets us report real precision/recall
instead of an unverifiable claim.

Usage: python generate_data.py --n 60 --seed 42
"""

import argparse
import csv
import json
import random
from datetime import datetime, timedelta

RAZORPAY_FEE_PCT = 0.02  # 2% flat fee assumption for this simulation

CUSTOMER_NAMES = [
    "Aarav Shah", "Priya Nair", "Rohan Mehta", "Sneha Iyer", "Karan Verma",
    "Isha Kapoor", "Vikram Rao", "Ananya Joshi", "Arjun Singh", "Meera Pillai",
    "Dev Patel", "Kavya Reddy", "Aditya Kumar", "Neha Gupta", "Sameer Khan",
]


def rand_date(base, max_offset_days=30):
    return base + timedelta(days=random.randint(0, max_offset_days),
                             hours=random.randint(0, 23),
                             minutes=random.randint(0, 59))


def make_clean_dataset(n, base_date):
    """Generate n fully-clean, correctly-linked order/payment/settlement triples."""
    orders, payments, settlements = [], [], []
    for i in range(1, n + 1):
        order_id = f"ORD{i:04d}"
        payment_id = f"PAY{i:04d}"
        settlement_id = f"SET{i:04d}"
        amount = round(random.uniform(299, 15000), 2)
        order_date = rand_date(base_date)
        payment_date = order_date + timedelta(minutes=random.randint(1, 30))
        settlement_date = payment_date + timedelta(days=random.randint(1, 3))
        fee = round(amount * RAZORPAY_FEE_PCT, 2)
        settled_amount = round(amount - fee, 2)

        orders.append({
            "order_id": order_id, "amount": amount,
            "customer": random.choice(CUSTOMER_NAMES),
            "date": order_date.isoformat(timespec="minutes"),
        })
        payments.append({
            "payment_id": payment_id, "order_id": order_id, "amount": amount,
            "status": "captured",
            "date": payment_date.isoformat(timespec="minutes"),
        })
        settlements.append({
            "settlement_id": settlement_id, "payment_id": payment_id,
            "amount": settled_amount,
            "settlement_date": settlement_date.isoformat(timespec="minutes"),
        })
    return orders, payments, settlements


def inject_exceptions(orders, payments, settlements, seed):
    """
    Deliberately corrupt a known subset of records and return an answer key
    describing exactly what was broken and why. Categories:
      - missing_settlement: payment captured, no settlement record yet
      - fee_mismatch: settlement amount doesn't match expected (amount - fee)
      - duplicate_payment: same order paid twice
      - orphan_settlement: settlement with no matching payment_id
      - refund_partial: payment marked partially refunded, amount reduced
    """
    rnd = random.Random(seed)
    answer_key = []

    # 1) missing_settlement — drop settlement for a payment
    idx = rnd.randrange(len(settlements))
    victim = settlements.pop(idx)
    answer_key.append({
        "type": "missing_settlement",
        "payment_id": victim["payment_id"],
        "detail": "Payment captured but no settlement record found.",
    })

    # 2) fee_mismatch — corrupt a settlement amount
    idx = rnd.randrange(len(settlements))
    settlements[idx]["amount"] = round(settlements[idx]["amount"] * 1.15, 2)
    answer_key.append({
        "type": "fee_mismatch",
        "payment_id": settlements[idx]["payment_id"],
        "detail": "Settlement amount does not match payment amount minus expected fee.",
    })

    # 3) duplicate_payment — clone a payment record with a new payment_id
    idx = rnd.randrange(len(payments))
    dup = dict(payments[idx])
    dup["payment_id"] = dup["payment_id"] + "_DUP"
    payments.append(dup)
    answer_key.append({
        "type": "duplicate_payment",
        "payment_id": dup["payment_id"],
        "order_id": dup["order_id"],
        "detail": "Duplicate payment found for the same order_id.",
    })

    # 4) orphan_settlement — settlement referencing a payment_id that doesn't exist
    orphan_id = "PAY9999"
    settlements.append({
        "settlement_id": "SET9999",
        "payment_id": orphan_id,
        "amount": round(rnd.uniform(500, 3000), 2),
        "settlement_date": datetime.now().isoformat(timespec="minutes"),
    })
    answer_key.append({
        "type": "orphan_settlement",
        "payment_id": orphan_id,
        "detail": "Settlement exists with no matching payment record.",
    })

    # 5) refund_partial — mark a payment partially refunded, reduce its amount
    idx = rnd.randrange(len(payments))
    while payments[idx]["status"] != "captured":
        idx = rnd.randrange(len(payments))
    original_amount = payments[idx]["amount"]
    payments[idx]["status"] = "partially_refunded"
    payments[idx]["amount"] = round(original_amount * 0.6, 2)
    answer_key.append({
        "type": "refund_partial",
        "payment_id": payments[idx]["payment_id"],
        "detail": "Payment partially refunded; settled amount will not match original order amount.",
    })

    return orders, payments, settlements, answer_key


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=60, help="number of clean records to start from")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--outdir", type=str, default="data")
    args = parser.parse_args()

    random.seed(args.seed)
    base_date = datetime(2026, 8, 1)

    orders, payments, settlements = make_clean_dataset(args.n, base_date)
    orders, payments, settlements, answer_key = inject_exceptions(
        orders, payments, settlements, args.seed
    )

    write_csv(f"{args.outdir}/orders.csv", orders, ["order_id", "amount", "customer", "date"])
    write_csv(f"{args.outdir}/payments.csv", payments, ["payment_id", "order_id", "amount", "status", "date"])
    write_csv(f"{args.outdir}/settlements.csv", settlements, ["settlement_id", "payment_id", "amount", "settlement_date"])

    with open(f"{args.outdir}/answer_key.json", "w") as f:
        json.dump(answer_key, f, indent=2)

    print(f"Generated {len(orders)} orders, {len(payments)} payments, {len(settlements)} settlements.")
    print(f"Injected {len(answer_key)} known exceptions -> {args.outdir}/answer_key.json")


if __name__ == "__main__":
    main()
