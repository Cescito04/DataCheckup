#!/usr/bin/env python3
"""Validate a CSV, quarantine invalid rows, and fail closed above a threshold.

This small standard-library implementation is an operational demonstration
separate from the GX, Soda, and Deequ benchmark runners. It retains row IDs and
rule IDs so results can be compared directly with the benchmark ground truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "orders_50000.csv"
DEFAULT_TRUTH = ROOT / "data" / "expected_violations.csv"
RESULTS_ROOT = ROOT / "results" / "quarantine_runs"
RULE_IDS = ("C1", "C2", "C3", "U1", "U2", "V1", "V2", "V3", "V4", "K1", "K2", "K3")
CURRENCIES = {"EUR", "USD", "GBP"}
STATUSES = {"pending", "paid", "shipped", "cancelled"}
QUANTITY_PATTERN = re.compile(r"^[1-9][0-9]*$")
PRICE_PATTERN = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$")


def is_present(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def rule_failures(row: dict[str, str]) -> list[str]:
    """Return the exact rule IDs failed by one input record."""
    failures: set[str] = set()

    # Completeness.
    if not is_present(row.get("customer_id")):
        failures.add("C1")
    if not is_present(row.get("order_date")):
        failures.add("C2")
    if not is_present(row.get("total_amount")):
        failures.add("C3")

    # Validity.
    quantity = row.get("quantity", "")
    if not QUANTITY_PATTERN.fullmatch(quantity):
        failures.add("V1")
    unit_price = row.get("unit_price", "")
    if not PRICE_PATTERN.fullmatch(unit_price):
        failures.add("V2")
    if row.get("currency") not in CURRENCIES:
        failures.add("V3")
    status = row.get("status", "")
    if status not in STATUSES:
        failures.add("V4")

    # Cross-column consistency. Missing inputs are owned by completeness.
    if all(is_present(row.get(key)) for key in ("quantity", "unit_price", "total_amount")):
        try:
            product = (Decimal(quantity) * Decimal(unit_price)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            total = Decimal(row["total_amount"])
            if abs(total - product) > Decimal("0.01"):
                failures.add("K1")
        except (InvalidOperation, ValueError):
            failures.add("K1")

    has_payment_reference = is_present(row.get("payment_reference"))
    if status in {"paid", "shipped"} and not has_payment_reference:
        failures.add("K2")
    elif status in {"pending", "cancelled"} and has_payment_reference:
        failures.add("K2")

    has_shipped_at = is_present(row.get("shipped_at"))
    if status == "shipped":
        if not has_shipped_at:
            failures.add("K3")
        elif is_present(row.get("order_date")) and row["shipped_at"] < row["order_date"]:
            failures.add("K3")
    elif status in {"pending", "paid", "cancelled"} and has_shipped_at:
        failures.add("K3")

    return [rule_id for rule_id in RULE_IDS if rule_id in failures]


def add_uniqueness_failures(rows: list[dict[str, str]], failures: list[set[str]]) -> None:
    """Mark every row in a duplicate group, matching the benchmark truth."""
    for rule_id, column, ignore_empty in (
        ("U1", "order_id", False),
        ("U2", "payment_reference", True),
    ):
        groups: dict[str, list[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            value = row.get(column, "")
            if ignore_empty and not is_present(value):
                continue
            if not ignore_empty and not is_present(value):
                failures[index].add(rule_id)
                continue
            groups[value].append(index)
        for indexes in groups.values():
            if len(indexes) > 1:
                for index in indexes:
                    failures[index].add(rule_id)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"CSV sans en-tête : {path}")
        if "record_id" not in reader.fieldnames:
            raise ValueError("La colonne record_id est obligatoire pour tracer les rejets.")
        rows = list(reader)
        if any(row.get("record_id", "").strip() == "" for row in rows):
            raise ValueError("Chaque ligne doit avoir un record_id non vide.")
        ids = [row["record_id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("record_id doit être unique afin de tracer les lignes rejetées.")
        return list(reader.fieldnames), rows


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def read_truth(path: Path | None) -> set[tuple[str, str]] | None:
    if path is None:
        return None
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"record_id", "rule_id"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("La vérité terrain doit contenir record_id et rule_id.")
        return {(row["record_id"], row["rule_id"]) for row in reader}


def run(input_path: Path, truth_path: Path | None, output_dir: Path, max_invalid_rows: int) -> dict:
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Le dossier de sortie n'est pas vide : {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc)
    fields, rows = read_csv(input_path)
    truth = read_truth(truth_path) if truth_path and truth_path.is_file() else None

    failures: list[set[str]] = [set(rule_failures(row)) for row in rows]
    add_uniqueness_failures(rows, failures)

    violations = [
        {"record_id": row["record_id"], "rule_id": rule_id}
        for row, rule_set in zip(rows, failures, strict=True)
        for rule_id in RULE_IDS
        if rule_id in rule_set
    ]
    invalid_indexes = [index for index, failed_rules in enumerate(failures) if failed_rules]
    valid_rows = [rows[index] for index, failed_rules in enumerate(failures) if not failed_rules]
    rule_counts = Counter(record["rule_id"] for record in violations)
    by_record: dict[str, list[str]] = defaultdict(list)
    for record in violations:
        by_record[record["record_id"]].append(record["rule_id"])

    quarantine_rows = []
    for index in invalid_indexes:
        enriched = dict(rows[index])
        ids = [rule_id for rule_id in RULE_IDS if rule_id in failures[index]]
        enriched["failed_rule_ids"] = "|".join(ids)
        enriched["failed_rule_count"] = str(len(ids))
        quarantine_rows.append(enriched)

    gate_passed = len(invalid_indexes) <= max_invalid_rows
    run_id = started.strftime("%Y%m%dT%H%M%SZ")
    violations_path = output_dir / "violations.csv"
    quarantine_path = output_dir / "quarantine.csv"
    candidate_path = output_dir / "valid_candidate.csv"
    published_path = output_dir / "published.csv"

    write_csv(violations_path, ["record_id", "rule_id"], violations)
    write_csv(quarantine_path, fields + ["failed_rule_ids", "failed_rule_count"], quarantine_rows)
    write_csv(candidate_path, fields, valid_rows)
    if gate_passed:
        write_csv(published_path, fields, valid_rows)

    detected = {(item["record_id"], item["rule_id"]) for item in violations}
    truth_result = None
    if truth is not None:
        truth_result = {
            "concordant": detected == truth,
            "expected_violation_pairs": len(truth),
            "detected_violation_pairs": len(detected),
            "false_positive_pairs": len(detected - truth),
            "false_negative_pairs": len(truth - detected),
        }

    ended = datetime.now(timezone.utc)
    summary = {
        "run_id": run_id,
        "generated_at_utc": ended.isoformat(),
        "input": str(input_path.resolve()),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "total_rows": len(rows),
        "invalid_rows": len(invalid_indexes),
        "valid_rows": len(valid_rows),
        "violation_pairs": len(violations),
        "violations_by_rule": {rule_id: rule_counts.get(rule_id, 0) for rule_id in RULE_IDS},
        "max_invalid_rows": max_invalid_rows,
        "gate_status": "PASS" if gate_passed else "BLOCKED",
        "published_rows": len(valid_rows) if gate_passed else 0,
        "outputs": {
            "violations": violations_path.name,
            "quarantine": quarantine_path.name,
            "valid_candidate": candidate_path.name,
            "published": published_path.name if gate_passed else None,
        },
        "truth_comparison": truth_result,
        "elapsed_seconds": round((ended - started).total_seconds(), 6),
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="CSV à contrôler.")
    parser.add_argument(
        "--truth", type=Path,
        help="Vérité terrain optionnelle; par défaut elle est associée au CSV défectueux du benchmark.",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        help="Dossier de sortie neuf ou vide; par défaut, un dossier horodaté dans benchmark/results.",
    )
    parser.add_argument(
        "--max-invalid-rows", type=int, default=0,
        help="Nombre maximal de lignes invalides tolérées avant blocage du lot (défaut : 0).",
    )
    args = parser.parse_args()
    if args.max_invalid_rows < 0:
        parser.error("--max-invalid-rows doit être positif ou nul.")
    output_dir = args.output_dir or RESULTS_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    truth_path = args.truth
    if truth_path is None and args.input.resolve() == DEFAULT_INPUT.resolve():
        truth_path = DEFAULT_TRUTH
    try:
        summary = run(args.input, truth_path, output_dir, args.max_invalid_rows)
    except (OSError, ValueError) as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1

    print(
        f"{summary['gate_status']} — {summary['invalid_rows']} ligne(s) invalide(s), "
        f"{summary['violation_pairs']} violation(s), {summary['published_rows']} ligne(s) publiée(s)."
    )
    if summary["truth_comparison"] is not None:
        print(f"Concordance avec la vérité terrain : {summary['truth_comparison']['concordant']}.")
    print(f"Résultats : {output_dir.resolve()}")
    return 0 if summary["gate_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
