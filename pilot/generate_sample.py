"""Create a deterministic 100-row pilot dataset and its anomaly ground truth."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FIELDS = [
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
]


def amount(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def make_row(index: int) -> dict[str, str]:
    order_day = date(2026, 1, 1) + timedelta(days=index % 90)
    quantity = Decimal(1 + index % 8)
    unit_price = Decimal(10 + (index * 7) % 400) + Decimal("0.25")
    status = ["pending", "paid", "shipped", "cancelled"][index % 4]
    payment_reference = f"PAY-{index + 1:04d}" if status in {"paid", "shipped"} else ""
    shipped_at = (
        (order_day + timedelta(days=1 + index % 7)).isoformat()
        if status == "shipped"
        else ""
    )
    return {
        "record_id": f"ROW-{index + 1:03d}",
        "order_id": f"ORD-{index + 1:04d}",
        "customer_id": f"CUS-{index % 25 + 1:03d}",
        "order_date": order_day.isoformat(),
        "quantity": str(quantity),
        "unit_price": amount(unit_price),
        "total_amount": amount(quantity * unit_price),
        "currency": ["EUR", "USD", "GBP"][index % 3],
        "status": status,
        "payment_reference": payment_reference,
        "shipped_at": shipped_at,
    }


rows = [make_row(i) for i in range(100)]
violations: list[tuple[str, str]] = []


def set_value(row_number: int, field: str, value: str, rule_id: str) -> None:
    rows[row_number - 1][field] = value
    violations.append((rows[row_number - 1]["record_id"], rule_id))


# Completeness
for number in (1, 2):
    set_value(number, "customer_id", "", "C1")
for number in (3, 4):
    set_value(number, "order_date", "", "C2")
for number in (5, 6):
    set_value(number, "total_amount", "", "C3")

# Uniqueness: mark both rows participating in each duplicate group.
rows[7]["order_id"] = rows[6]["order_id"]
violations.extend(((rows[6]["record_id"], "U1"), (rows[7]["record_id"], "U1")))
rows[30]["payment_reference"] = rows[26]["payment_reference"]
violations.extend(((rows[26]["record_id"], "U2"), (rows[30]["record_id"], "U2")))

# Validity; keep dependent values coherent so each rule is isolated.
set_value(11, "quantity", "0", "V1")
rows[10]["total_amount"] = "0.00"
set_value(12, "quantity", "1.5", "V1")
rows[11]["total_amount"] = amount(Decimal("1.5") * Decimal(rows[11]["unit_price"]))
set_value(13, "unit_price", "-1.00", "V2")
rows[12]["total_amount"] = amount(Decimal(rows[12]["quantity"]) * Decimal("-1.00"))
set_value(14, "unit_price", "1.234", "V2")
rows[13]["total_amount"] = amount(Decimal(rows[13]["quantity"]) * Decimal("1.234"))
set_value(15, "currency", "XOF", "V3")
set_value(16, "status", "in_transit", "V4")

# Coherence
set_value(17, "total_amount", "999.99", "K1")
set_value(18, "payment_reference", "", "K2")
set_value(20, "status", "pending", "K2")
rows[19]["shipped_at"] = ""
set_value(23, "shipped_at", "", "K3")
set_value(24, "shipped_at", (date.fromisoformat(rows[23]["order_date"]) + timedelta(days=2)).isoformat(), "K3")
set_value(25, "shipped_at", (date.fromisoformat(rows[24]["order_date"]) - timedelta(days=1)).isoformat(), "K3")

with (DATA_DIR / "orders_100.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)

with (DATA_DIR / "expected_violations.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream)
    writer.writerow(("record_id", "rule_id"))
    writer.writerows(sorted(violations))

counts: dict[str, int] = {}
for _, rule_id in violations:
    counts[rule_id] = counts.get(rule_id, 0) + 1
print(f"Rows: {len(rows)}")
print(f"Known row-rule violations: {len(violations)}")
print("Violations by rule:", dict(sorted(counts.items())))
