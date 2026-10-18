"""Generate the reproducible 50,000-row benchmark dataset and ground truth."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

SEED = 20261018
ROW_COUNT = 50_000
ANOMALIES_PER_RULE = 200
START_DATE = date(2025, 1, 1)
CURRENCIES = ("EUR", "USD", "GBP")
STATUSES = ("pending", "paid", "shipped", "cancelled")
FIELDS = (
    "record_id",
    "order_id",
    "customer_id",
    "order_date",
    "quantity",
    "unit_price",
    "total_amount",
    "currency",
    "status",
    "payment_reference",
    "shipped_at",
)
RULE_IDS = ("C1", "C2", "C3", "U1", "U2", "V1", "V2", "V3", "V4", "K1", "K2", "K3")


def money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def make_clean_row(index: int, rng: random.Random) -> dict[str, str]:
    order_day = START_DATE + timedelta(days=rng.randrange(365))
    quantity = rng.randint(1, 10)
    price_cents = rng.randint(250, 50_000)
    unit_price = Decimal(price_cents) / Decimal(100)
    status = rng.choice(STATUSES)
    shipped_at = ""
    if status == "shipped":
        shipped_at = (order_day + timedelta(days=rng.randrange(0, 15))).isoformat()

    return {
        "record_id": f"ROW-{index + 1:06d}",
        "order_id": f"ORD-{index + 1:06d}",
        "customer_id": f"CUS-{rng.randint(1, 15_000):05d}",
        "order_date": order_day.isoformat(),
        "quantity": str(quantity),
        "unit_price": money(unit_price),
        "total_amount": money(Decimal(quantity) * unit_price),
        "currency": rng.choice(CURRENCIES),
        "status": status,
        "payment_reference": f"PAY-{index + 1:06d}" if status in {"paid", "shipped"} else "",
        "shipped_at": shipped_at,
    }


def write_csv(path: Path, rows: list[dict[str, str]], fields: tuple[str, ...] | list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def allocate_targets(rows: list[dict[str, str]], rng: random.Random) -> dict[str, list[int]]:
    """Choose disjoint rows, with status constraints where an anomaly needs them."""
    free = set(range(len(rows)))
    targets: dict[str, list[int]] = {}

    def take(rule_id: str, candidates: list[int], count: int) -> list[int]:
        eligible = [index for index in candidates if index in free]
        if len(eligible) < count:
            raise RuntimeError(f"Not enough eligible rows for {rule_id}: {len(eligible)} < {count}")
        chosen = rng.sample(eligible, count)
        free.difference_update(chosen)
        targets[rule_id] = chosen
        return chosen

    payment_rows = [
        index
        for index, row in enumerate(rows)
        if row["status"] in {"paid", "shipped"}
    ]
    non_payment_rows = [
        index
        for index, row in enumerate(rows)
        if row["status"] in {"pending", "cancelled"}
    ]

    # U2 needs originally nonempty references so duplicate pairs stay isolated.
    take("U2", payment_rows, 2 * ANOMALIES_PER_RULE)
    # K2 is split evenly between a missing required reference and an unexpected one.
    take("K2_paid_or_shipped", payment_rows, ANOMALIES_PER_RULE // 2)
    take("K2_pending_or_cancelled", non_payment_rows, ANOMALIES_PER_RULE // 2)
    # K3 uses realistic status-specific cases: missing, unexpected, and too-early dates.
    take("K3_missing_shipment", [i for i in payment_rows if rows[i]["status"] == "shipped"], 70)
    take("K3_unexpected_shipment", non_payment_rows, 70)
    take("K3_early_shipment", [i for i in payment_rows if rows[i]["status"] == "shipped"], 60)
    take("U1", list(free), 2 * ANOMALIES_PER_RULE)

    for rule_id in ("C1", "C2", "C3", "V1", "V2", "V3", "V4", "K1"):
        take(rule_id, list(free), ANOMALIES_PER_RULE)

    if len(free) != ROW_COUNT - (10 * ANOMALIES_PER_RULE + 4 * ANOMALIES_PER_RULE):
        raise RuntimeError("Target allocation did not reserve the expected number of rows")
    return targets


def inject_anomalies(
    rows: list[dict[str, str]], targets: dict[str, list[int]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    violations: list[dict[str, str]] = []

    def mark(index: int, rule_id: str, group_id: str, mutation: str) -> None:
        violations.append(
            {
                "record_id": rows[index]["record_id"],
                "rule_id": rule_id,
                "anomaly_group_id": group_id,
                "mutation": mutation,
            }
        )

    for ordinal, index in enumerate(targets["C1"], 1):
        rows[index]["customer_id"] = ""
        mark(index, "C1", f"C1-{ordinal:04d}", "customer_id manquant")

    for ordinal, index in enumerate(targets["C2"], 1):
        rows[index]["order_date"] = ""
        mark(index, "C2", f"C2-{ordinal:04d}", "order_date manquant")

    for ordinal, index in enumerate(targets["C3"], 1):
        rows[index]["total_amount"] = ""
        mark(index, "C3", f"C3-{ordinal:04d}", "total_amount manquant")

    for ordinal, (left, right) in enumerate(zip(targets["U1"][::2], targets["U1"][1::2]), 1):
        duplicate = rows[left]["order_id"]
        rows[right]["order_id"] = duplicate
        group_id = f"U1-G{ordinal:04d}"
        mark(left, "U1", group_id, "première ligne d'un groupe de doublons")
        mark(right, "U1", group_id, "seconde ligne d'un groupe de doublons")

    for ordinal, (left, right) in enumerate(zip(targets["U2"][::2], targets["U2"][1::2]), 1):
        duplicate = rows[left]["payment_reference"]
        rows[right]["payment_reference"] = duplicate
        group_id = f"U2-G{ordinal:04d}"
        mark(left, "U2", group_id, "première ligne d'un groupe de doublons")
        mark(right, "U2", group_id, "seconde ligne d'un groupe de doublons")

    for ordinal, index in enumerate(targets["V1"], 1):
        quantity = "0" if ordinal <= ANOMALIES_PER_RULE // 2 else "1.5"
        rows[index]["quantity"] = quantity
        rows[index]["total_amount"] = money(Decimal(quantity) * Decimal(rows[index]["unit_price"]))
        mark(index, "V1", f"V1-{ordinal:04d}", "quantité nulle" if quantity == "0" else "quantité non entière")

    for ordinal, index in enumerate(targets["V2"], 1):
        price = "-12.34" if ordinal <= ANOMALIES_PER_RULE // 2 else "12.345"
        rows[index]["unit_price"] = price
        rows[index]["total_amount"] = money(Decimal(rows[index]["quantity"]) * Decimal(price))
        mark(index, "V2", f"V2-{ordinal:04d}", "prix négatif" if price.startswith("-") else "plus de deux décimales")

    for ordinal, index in enumerate(targets["V3"], 1):
        rows[index]["currency"] = "XOF"
        mark(index, "V3", f"V3-{ordinal:04d}", "devise hors liste autorisée")

    for ordinal, index in enumerate(targets["V4"], 1):
        rows[index]["status"] = "in_transit"
        rows[index]["shipped_at"] = ""
        mark(index, "V4", f"V4-{ordinal:04d}", "statut hors liste autorisée")

    for ordinal, index in enumerate(targets["K1"], 1):
        correct = Decimal(rows[index]["total_amount"])
        rows[index]["total_amount"] = money(correct + Decimal("1.00"))
        mark(index, "K1", f"K1-{ordinal:04d}", "montant total différent du produit attendu")

    for ordinal, index in enumerate(targets["K2_paid_or_shipped"], 1):
        rows[index]["payment_reference"] = ""
        mark(index, "K2", f"K2-M{ordinal:04d}", "référence absente pour paid/shipped")
    for ordinal, index in enumerate(targets["K2_pending_or_cancelled"], 1):
        rows[index]["payment_reference"] = f"PAY-K2-EXTRA-{ordinal:04d}"
        mark(index, "K2", f"K2-X{ordinal:04d}", "référence présente pour pending/cancelled")

    for ordinal, index in enumerate(targets["K3_missing_shipment"], 1):
        rows[index]["shipped_at"] = ""
        mark(index, "K3", f"K3-M{ordinal:04d}", "date absente pour une commande shipped")
    for ordinal, index in enumerate(targets["K3_unexpected_shipment"], 1):
        order_day = date.fromisoformat(rows[index]["order_date"])
        rows[index]["shipped_at"] = (order_day + timedelta(days=1)).isoformat()
        mark(index, "K3", f"K3-X{ordinal:04d}", "date présente pour un statut non shipped")
    for ordinal, index in enumerate(targets["K3_early_shipment"], 1):
        order_day = date.fromisoformat(rows[index]["order_date"])
        rows[index]["shipped_at"] = (order_day - timedelta(days=1)).isoformat()
        mark(index, "K3", f"K3-E{ordinal:04d}", "expédition antérieure à la commande")

    return rows, violations


def independently_detect(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    """Audit the generated CSV rows using the written business definitions."""
    found: dict[str, set[str]] = {rule_id: set() for rule_id in RULE_IDS}
    order_counts = Counter(row["order_id"] for row in rows)
    payment_counts = Counter(row["payment_reference"] for row in rows if row["payment_reference"])

    for row in rows:
        record_id = row["record_id"]
        if not row["customer_id"]:
            found["C1"].add(record_id)
        if not row["order_date"]:
            found["C2"].add(record_id)
        if not row["total_amount"]:
            found["C3"].add(record_id)
        if order_counts[row["order_id"]] > 1:
            found["U1"].add(record_id)
        if row["payment_reference"] and payment_counts[row["payment_reference"]] > 1:
            found["U2"].add(record_id)

        try:
            quantity = Decimal(row["quantity"])
            if quantity <= 0 or quantity != quantity.to_integral_value():
                found["V1"].add(record_id)
        except Exception:
            found["V1"].add(record_id)

        try:
            price = Decimal(row["unit_price"])
            if price < 0 or price.as_tuple().exponent < -2:
                found["V2"].add(record_id)
        except Exception:
            found["V2"].add(record_id)

        if row["currency"] not in CURRENCIES:
            found["V3"].add(record_id)
        if row["status"] not in STATUSES:
            found["V4"].add(record_id)

        if row["quantity"] and row["unit_price"] and row["total_amount"]:
            expected = (Decimal(row["quantity"]) * Decimal(row["unit_price"])).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            actual = Decimal(row["total_amount"])
            if abs(actual - expected) > Decimal("0.01"):
                found["K1"].add(record_id)

        if row["status"] in {"paid", "shipped"} and not row["payment_reference"]:
            found["K2"].add(record_id)
        elif row["status"] in {"pending", "cancelled"} and row["payment_reference"]:
            found["K2"].add(record_id)

        if row["status"] == "shipped":
            if not row["shipped_at"]:
                found["K3"].add(record_id)
            elif row["order_date"] and date.fromisoformat(row["shipped_at"]) < date.fromisoformat(row["order_date"]):
                found["K3"].add(record_id)
        elif row["status"] in {"pending", "paid", "cancelled"} and row["shipped_at"]:
            found["K3"].add(record_id)

    return found


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    rng = random.Random(SEED)
    rows = [make_clean_row(index, rng) for index in range(ROW_COUNT)]
    rng.shuffle(rows)
    clean_rows = deepcopy(rows)

    targets = allocate_targets(rows, rng)
    final_rows, violations = inject_anomalies(rows, targets)

    expected: dict[str, set[str]] = {rule_id: set() for rule_id in RULE_IDS}
    for item in violations:
        expected[item["rule_id"]].add(item["record_id"])
    actual = independently_detect(final_rows)
    if actual != expected:
        differences = {
            rule_id: {
                "missing_from_ground_truth": sorted(actual[rule_id] - expected[rule_id])[:10],
                "not_detected_by_audit": sorted(expected[rule_id] - actual[rule_id])[:10],
            }
            for rule_id in RULE_IDS
            if actual[rule_id] != expected[rule_id]
        }
        raise RuntimeError(f"Generated data does not match ground truth: {differences}")
    if any(independently_detect(clean_rows).values()):
        raise RuntimeError("The clean dataset unexpectedly violates one or more rules")

    clean_path = DATA_DIR / "orders_50000_clean.csv"
    final_path = DATA_DIR / "orders_50000.csv"
    truth_path = DATA_DIR / "expected_violations.csv"
    manifest_path = DATA_DIR / "anomaly_manifest.csv"
    write_csv(clean_path, clean_rows, FIELDS)
    write_csv(final_path, final_rows, FIELDS)
    truth_rows = [
        {"record_id": record_id, "rule_id": rule_id}
        for record_id, rule_id in sorted((item["record_id"], item["rule_id"]) for item in violations)
    ]
    write_csv(truth_path, truth_rows, ("record_id", "rule_id"))
    write_csv(
        manifest_path,
        sorted(violations, key=lambda item: (item["rule_id"], item["anomaly_group_id"], item["record_id"])),
        ("record_id", "rule_id", "anomaly_group_id", "mutation"),
    )

    row_counts = Counter(item["rule_id"] for item in violations)
    group_counts = {
        rule_id: len({item["anomaly_group_id"] for item in violations if item["rule_id"] == rule_id})
        for rule_id in RULE_IDS
    }
    summary = {
        "seed": SEED,
        "rows": ROW_COUNT,
        "anomalies_per_rule": ANOMALIES_PER_RULE,
        "affected_row_rule_pairs": len(violations),
        "rules": {
            rule_id: {
                "affected_rows": row_counts[rule_id],
                "anomaly_groups": group_counts[rule_id],
            }
            for rule_id in RULE_IDS
        },
        "validation": "PASS: clean dataset has zero violations; final dataset matches ground truth for all 12 rules",
        "files": {
            path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in (clean_path, final_path, truth_path, manifest_path)
        },
    }
    summary_path = RESULTS_DIR / "generation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Rows: {ROW_COUNT:,}")
    print(f"Known row-rule violations: {len(violations):,}")
    print("Validation: PASS (clean dataset valid; final dataset exactly matches ground truth)")
    print(f"Generated: {clean_path}")
    print(f"Generated: {final_path}")
    print(f"Ground truth: {truth_path}")
    print(f"Detailed manifest: {manifest_path}")
    print(f"Summary: {summary_path}")
    print("Affected rows per rule:", dict(sorted(row_counts.items())))
    print("Anomaly groups per rule:", dict(sorted(group_counts.items())))


if __name__ == "__main__":
    main()
