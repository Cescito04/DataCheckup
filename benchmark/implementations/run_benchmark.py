"""Run the 12-rule benchmark in Great Expectations, Soda Core, and PyDeequ."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import time
import traceback
from collections import Counter, defaultdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DATA_PATH = ROOT / "data" / "orders_50000.csv"
TRUTH_PATH = ROOT / "data" / "expected_violations.csv"
MANIFEST_PATH = ROOT / "data" / "anomaly_manifest.csv"
SODA_CONTRACT_PATH = ROOT / "contracts" / "soda_benchmark.yml"
RESULTS_DIR = ROOT / "results"
RULE_IDS = ("C1", "C2", "C3", "U1", "U2", "V1", "V2", "V3", "V4", "K1", "K2", "K3")
ALLOWED_CURRENCIES = {"EUR", "USD", "GBP"}
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled"}


def installed_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not installed"


def expected_counts() -> dict[str, dict[str, int]]:
    import pandas as pd

    truth = pd.read_csv(TRUTH_PATH, dtype=str)
    manifest = pd.read_csv(MANIFEST_PATH, dtype=str)
    affected = Counter(truth["rule_id"])
    groups = {
        rule_id: int(manifest.loc[manifest["rule_id"] == rule_id, "anomaly_group_id"].nunique())
        for rule_id in RULE_IDS
    }
    return {
        rule_id: {"affected_rows": int(affected.get(rule_id, 0)), "anomaly_groups": groups[rule_id]}
        for rule_id in RULE_IDS
    }


def physical_memory_bytes() -> int | None:
    try:
        return int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, OSError, ValueError):
        return None


def processor_description() -> str:
    reported = platform.processor()
    if not reported or reported.lower() in {"i386", "x86_64"}:
        return f"{platform.machine()} (model not reported)"
    return reported


def gx_helpers(df):
    """Add three pass/fail columns for rules requiring row-wise expressions."""
    from decimal import Decimal, ROUND_HALF_UP
    import pandas as pd

    def nonempty(value) -> bool:
        return not pd.isna(value) and str(value).strip() != ""

    def amount_ok(row) -> bool:
        if not all(nonempty(row.get(key)) for key in ("quantity", "unit_price", "total_amount")):
            return True  # K1 is not evaluated when an input is missing; completeness owns that case.
        expected = (Decimal(str(row["quantity"])) * Decimal(str(row["unit_price"]))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return abs(Decimal(str(row["total_amount"])) - expected) <= Decimal("0.01")

    def payment_ok(row) -> bool:
        status = str(row["status"])
        has_reference = nonempty(row.get("payment_reference"))
        if status in {"paid", "shipped"}:
            return has_reference
        if status in {"pending", "cancelled"}:
            return not has_reference
        return True  # V4 reports unrecognized statuses.

    def shipment_ok(row) -> bool:
        status = str(row["status"])
        has_date = nonempty(row.get("shipped_at"))
        if status == "shipped":
            if not has_date:
                return False
            return not nonempty(row.get("order_date")) or str(row["shipped_at"]) >= str(row["order_date"])
        if status in {"pending", "paid", "cancelled"}:
            return not has_date
        return True  # V4 reports unrecognized statuses.

    df["_rule_K1_pass"] = df.apply(amount_ok, axis=1)
    df["_rule_K2_pass"] = df.apply(payment_ok, axis=1)
    df["_rule_K3_pass"] = df.apply(shipment_ok, axis=1)
    return df


def run_great_expectations() -> dict:
    import pandas as pd
    import great_expectations as gx

    total_start = time.perf_counter()
    load_start = time.perf_counter()
    df = pd.read_csv(DATA_PATH, dtype=str, keep_default_na=True)
    load_seconds = time.perf_counter() - load_start
    setup_start = time.perf_counter()
    df = gx_helpers(df)

    context = gx.get_context(mode="ephemeral")
    source = context.data_sources.add_pandas(name="benchmark_orders_pandas")
    asset = source.add_dataframe_asset(name="orders_50000")
    batch_definition = asset.add_batch_definition_whole_dataframe("benchmark_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    checks = {
        "C1": gx.expectations.ExpectColumnValuesToNotBeNull(column="customer_id"),
        "C2": gx.expectations.ExpectColumnValuesToNotBeNull(column="order_date"),
        "C3": gx.expectations.ExpectColumnValuesToNotBeNull(column="total_amount"),
        "U1": gx.expectations.ExpectColumnValuesToBeUnique(column="order_id"),
        "U2": gx.expectations.ExpectColumnValuesToBeUnique(column="payment_reference"),
        "V1": gx.expectations.ExpectColumnValuesToMatchRegex(column="quantity", regex=r"^[1-9][0-9]*$"),
        "V2": gx.expectations.ExpectColumnValuesToMatchRegex(
            column="unit_price", regex=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$"
        ),
        "V3": gx.expectations.ExpectColumnValuesToBeInSet(column="currency", value_set=sorted(ALLOWED_CURRENCIES)),
        "V4": gx.expectations.ExpectColumnValuesToBeInSet(column="status", value_set=sorted(ALLOWED_STATUSES)),
        "K1": gx.expectations.ExpectColumnValuesToBeInSet(column="_rule_K1_pass", value_set=[True]),
        "K2": gx.expectations.ExpectColumnValuesToBeInSet(column="_rule_K2_pass", value_set=[True]),
        "K3": gx.expectations.ExpectColumnValuesToBeInSet(column="_rule_K3_pass", value_set=[True]),
    }
    payment_subset = df[df["payment_reference"].notna() & (df["payment_reference"].str.strip() != "")]
    payment_asset = source.add_dataframe_asset(name="orders_with_payment_reference")
    payment_batch_def = payment_asset.add_batch_definition_whole_dataframe("payment_reference_batch")
    payment_batch = payment_batch_def.get_batch(batch_parameters={"dataframe": payment_subset})
    setup_seconds = time.perf_counter() - setup_start

    validation_start = time.perf_counter()
    output_checks = []
    for rule_id in RULE_IDS:
        result = (payment_batch if rule_id == "U2" else batch).validate(checks[rule_id]).to_json_dict()
        details = result.get("result", {})
        output_checks.append(
            {
                "rule_id": rule_id,
                "status": "PASS" if result.get("success") else "FAIL",
                "reported_violations": details.get("unexpected_count"),
                "result_format": "GX unexpected row count",
            }
        )
    validation_seconds = time.perf_counter() - validation_start
    return {
        "version": gx.__version__,
        "load_seconds": load_seconds,
        "setup_seconds": setup_seconds,
        "validation_seconds": validation_seconds,
        "total_seconds": time.perf_counter() - total_start,
        "checks": output_checks,
    }


def soda_rule_id(check) -> str | None:
    internal = check.check
    candidates = [
        getattr(internal, "name", None),
        getattr(internal, "relative_path", None),
        str(internal),
    ]
    for candidate in candidates:
        if candidate:
            match = re.search(r"\b(C[1-3]|U[1-2]|V[1-4]|K[1-3])\b", str(candidate))
            if match:
                return match.group(1)
    return None


def run_soda() -> dict:
    import duckdb
    import pandas as pd
    from soda_core.contracts import verify_contract_locally
    from soda_duckdb import DuckDBDataSource

    total_start = time.perf_counter()
    load_start = time.perf_counter()
    df = pd.read_csv(DATA_PATH)
    connection = duckdb.connect(database=":memory:")
    connection.register("orders_input", df)
    connection.execute("CREATE TABLE orders AS SELECT * FROM orders_input")
    data_source = DuckDBDataSource.from_existing_cursor(connection.cursor(), name="benchmark")
    load_seconds = time.perf_counter() - load_start

    validation_start = time.perf_counter()
    result = verify_contract_locally(
        data_sources=[data_source],
        contract_file_path=str(SODA_CONTRACT_PATH),
    )
    validation_seconds = time.perf_counter() - validation_start
    contract_result = result.results[0]
    diagnostics = [record.getMessage() for record in getattr(contract_result, "log_records", [])]
    if contract_result.status.value == "ERROR":
        connection.close()
        raise RuntimeError("Soda contract error: " + " | ".join(diagnostics))
    raw_checks = []
    for check in contract_result.check_results:
        metrics = check.diagnostic_metric_values or {}
        raw_checks.append(
            {
                "rule_id": soda_rule_id(check),
                "name": getattr(check.check, "name", None),
                "path": check.check.relative_path,
                "type": check.check.type,
                "status": check.outcome.value,
                "metrics": metrics,
            }
        )

    # Soda's duplicate metric counts repeated occurrences beyond the first.
    # The ground truth uses pairs, so multiplying by two gives affected rows.
    by_rule: dict[str, list[dict]] = defaultdict(list)
    for check in raw_checks:
        if check["rule_id"]:
            by_rule[check["rule_id"]].append(check)
    checks = []
    for rule_id in RULE_IDS:
        items = by_rule.get(rule_id, [])
        reported = 0
        normalized = 0
        units = []
        for item in items:
            metrics = item["metrics"]
            count = next(
                (
                    int(value)
                    for key, value in metrics.items()
                    if key.endswith("_count") and key not in {"check_rows_tested", "dataset_rows_tested"}
                ),
                0,
            )
            if item["type"] == "duplicate":
                reported += count
                normalized += count * 2
                units.append("duplicate occurrences beyond first; normalized to 2-row groups")
            else:
                reported += count
                normalized += count
                units.append("failed or missing rows")
        checks.append(
            {
                "rule_id": rule_id,
                "status": "FAIL" if any(item["status"] == "FAILED" for item in items) else "PASS",
                "reported_violations": reported,
                "normalized_affected_rows": normalized,
                "count_unit": "; ".join(units),
                "subchecks": items,
            }
        )

    connection.close()
    return {
        "version": installed_version("soda-core"),
        "duckdb_version": installed_version("duckdb"),
        "contract_status": contract_result.status.value,
        "diagnostics": diagnostics,
        "load_seconds": load_seconds,
        "validation_seconds": validation_seconds,
        "total_seconds": time.perf_counter() - total_start,
        "checks": checks,
        "raw_checks": raw_checks,
    }


def run_deequ() -> dict:
    os.environ["SPARK_VERSION"] = "4.1"
    from pydeequ.checks import Check, CheckLevel
    from pydeequ.verification import VerificationResult, VerificationSuite
    from pyspark.sql import SparkSession, Window, functions as F

    total_start = time.perf_counter()
    ivy_dir = Path("/private/tmp/datacheckup-pilot-ivy")
    ivy_dir.mkdir(parents=True, exist_ok=True)
    load_start = time.perf_counter()
    spark = (
        SparkSession.builder.master("local[1]")
        .appName("DataCheckup-50000-row-benchmark")
        .config("spark.ui.enabled", "false")
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.18-spark-4.1")
        .config("spark.jars.ivy", str(ivy_dir))
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    gateway = spark.sparkContext._gateway
    try:
        df = (
            spark.read.option("header", "true")
            .option("inferSchema", "false")
            .option("nullValue", "")
            .option("emptyValue", "")
            .csv(str(DATA_PATH))
        )
        row_count = df.count()  # Force the CSV scan so load time is measured consistently.

        payment_counts = (
            df.where(F.col("payment_reference").isNotNull() & (F.trim("payment_reference") != ""))
            .groupBy("payment_reference")
            .count()
            .withColumnRenamed("count", "_u2_count")
        )
        df = df.join(payment_counts, on="payment_reference", how="left").withColumn(
            "_u2_valid",
            F.when(
                F.col("payment_reference").isNull() | (F.trim("payment_reference") == ""),
                F.lit(True),
            ).otherwise(F.col("_u2_count") == 1),
        ).drop("_u2_count")
        load_seconds = time.perf_counter() - load_start

        custom_rules = {
            "V1": "COALESCE(quantity RLIKE '^[1-9][0-9]*$', false)",
            "V2": "COALESCE(unit_price RLIKE '^(0|[1-9][0-9]*)(\\.[0-9]{1,2})?$', false)",
            "U2": "COALESCE(_u2_valid, false)",
            "V3": "COALESCE(currency IN ('EUR', 'USD', 'GBP'), false)",
            "V4": "COALESCE(status IN ('pending', 'paid', 'shipped', 'cancelled'), false)",
            "K1": "COALESCE(quantity IS NULL OR unit_price IS NULL OR total_amount IS NULL OR ABS(CAST(total_amount AS DECIMAL(20,2)) - ROUND(CAST(quantity AS DECIMAL(20,3)) * CAST(unit_price AS DECIMAL(20,3)), 2)) <= 0.01, false)",
            "K2": "COALESCE((status IN ('paid', 'shipped') AND payment_reference IS NOT NULL AND TRIM(payment_reference) <> '') OR (status IN ('pending', 'cancelled') AND (payment_reference IS NULL OR TRIM(payment_reference) = '')) OR status NOT IN ('pending', 'paid', 'shipped', 'cancelled'), false)",
            "K3": "COALESCE(CASE WHEN status = 'shipped' THEN shipped_at IS NOT NULL AND (order_date IS NULL OR shipped_at >= order_date) WHEN status IN ('pending', 'paid', 'cancelled') THEN shipped_at IS NULL ELSE true END, false)",
        }
        checks_by_rule = {}
        for rule_id in RULE_IDS:
            check = Check(spark, CheckLevel.Error, rule_id)
            if rule_id == "C1":
                check.isComplete("customer_id")
            elif rule_id == "C2":
                check.isComplete("order_date")
            elif rule_id == "C3":
                check.isComplete("total_amount")
            elif rule_id == "U1":
                check.isUnique("order_id")
            else:
                check.satisfies(custom_rules[rule_id], rule_id, assertion=lambda value: value == 1.0)
            checks_by_rule[rule_id] = check

        validation_start = time.perf_counter()
        suite = VerificationSuite(spark).onData(df)
        for rule_id in RULE_IDS:
            suite = suite.addCheck(checks_by_rule[rule_id])
        verification = suite.run()
        validation_seconds = time.perf_counter() - validation_start

        raw_results = verification.checkResults
        checks = []
        for rule_id in RULE_IDS:
            matches = [result for result in raw_results if result.get("check") == rule_id]
            if not matches:
                checks.append({"rule_id": rule_id, "status": "NO_RESULT", "reported_violations": None})
                continue
            result = matches[0]
            metric_match = re.search(r"Value:\s*([0-9]+(?:\.[0-9]+)?)", str(result.get("constraint_message", "")))
            compliance = float(metric_match.group(1)) if metric_match else None
            reported = round((1.0 - compliance) * row_count) if compliance is not None else None
            checks.append(
                {
                    "rule_id": rule_id,
                    "status": "FAIL" if result.get("constraint_status") == "Failure" else "PASS",
                    "reported_violations": reported,
                    "reported_fraction_passed": compliance,
                    "constraint": result.get("constraint"),
                    "constraint_message": result.get("constraint_message"),
                }
            )
        return {
            "version": installed_version("pydeequ"),
            "spark_version": spark.version,
            "row_count": row_count,
            "verification_status": verification.status,
            "load_seconds": load_seconds,
            "validation_seconds": validation_seconds,
            "total_seconds": time.perf_counter() - total_start,
            "checks": checks,
            "raw_checks": raw_results,
        }
    finally:
        spark.stop()


RUNNERS = {
    "great_expectations": run_great_expectations,
    "soda_core": run_soda,
    "pydeequ": run_deequ,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", choices=["all", *RUNNERS], default="all")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "full_benchmark.json")
    parser.add_argument("--quiet", action="store_true", help="Print only a compact run summary")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if not DATA_PATH.exists():
        parser.error(f"Dataset not found: {DATA_PATH}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    selected = list(RUNNERS) if args.tool == "all" else [args.tool]
    output = {
        "dataset": str(DATA_PATH.relative_to(PROJECT_ROOT)),
        "rows": 50_000,
        "environment": {
            "python_version": platform.python_version(),
            "operating_system": platform.platform(),
            "architecture": platform.machine(),
            "processor": processor_description(),
            "logical_cpu_count": os.cpu_count(),
            "physical_memory_bytes": physical_memory_bytes(),
        },
        "expected_counts": expected_counts(),
        "method": {
            "repeats": args.repeats,
            "timing": "load time and validation time are recorded separately; validation failures are expected data results, not runtime errors",
            "uniqueness_normalization": "Soda counts duplicate occurrences beyond the first; for this dataset every duplicate group has size two, so normalized affected rows = 2 x duplicate_count",
        },
        "tools": {},
    }
    for tool_name in selected:
        tool_results = []
        for run_number in range(1, args.repeats + 1):
            print(f"Running {tool_name} ({run_number}/{args.repeats})", flush=True)
            try:
                run = RUNNERS[tool_name]()
                run["run_number"] = run_number
                run["ok"] = True
                for check in run.get("checks", []):
                    rule_id = check.get("rule_id")
                    expected = output["expected_counts"].get(rule_id, {}).get("affected_rows")
                    observed = check.get("normalized_affected_rows", check.get("reported_violations"))
                    check["expected_affected_rows"] = expected
                    check["matches_ground_truth"] = observed == expected
                run["all_counts_match_ground_truth"] = (
                    len(run.get("checks", [])) == len(RULE_IDS)
                    and all(check.get("matches_ground_truth") for check in run.get("checks", []))
                )
                tool_results.append(run)
            except Exception as error:
                tool_results.append(
                    {
                        "run_number": run_number,
                        "ok": False,
                        "error": f"{type(error).__name__}: {error}",
                        "traceback": traceback.format_exc(),
                    }
                )
        successful_runs = [run for run in tool_results if run["ok"]]
        timing_summary = {}
        for field in ("load_seconds", "setup_seconds", "validation_seconds", "total_seconds"):
            samples = [run[field] for run in successful_runs if field in run]
            if samples:
                samples.sort()
                middle = len(samples) // 2
                median = samples[middle] if len(samples) % 2 else (samples[middle - 1] + samples[middle]) / 2
                timing_summary[field] = round(median, 6)
        output["tools"][tool_name] = {
            "ok": all(run["ok"] for run in tool_results),
            "all_counts_match_ground_truth": bool(successful_runs)
            and all(run.get("all_counts_match_ground_truth") for run in successful_runs),
            "median_timings_seconds": timing_summary,
            "runs": tool_results,
        }

    if "pydeequ" in selected:
        # Keep the Py4J gateway alive between repeated Spark sessions, then close it once.
        try:
            from pyspark import SparkContext

            gateway = SparkContext._gateway
            if gateway is not None:
                gateway.shutdown_callback_server()
                gateway.shutdown()
        except Exception:
            pass

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    summary_path = args.output.with_name("comparison_summary.md")
    write_summary_markdown(output, summary_path)
    if args.quiet:
        print(f"Saved: {args.output}")
        print(f"Summary: {summary_path}")
        for tool_name, result in output["tools"].items():
            print(
                f"{tool_name}: runtime_ok={result['ok']}, "
                f"counts_match={result['all_counts_match_ground_truth']}, "
                f"median={result['median_timings_seconds']}"
            )
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    return 0 if all(tool.get("ok") for tool in output["tools"].values()) else 1


def write_summary_markdown(output: dict, path: Path) -> None:
    labels = {
        "great_expectations": "Great Expectations",
        "soda_core": "Soda Core",
        "pydeequ": "PyDeequ / Deequ",
    }
    tool_runs = {
        name: [run for run in details.get("runs", []) if run.get("ok")]
        for name, details in output["tools"].items()
    }
    lines = [
        "# Résultats du benchmark",
        "",
        f"Jeu mesuré : {output['dataset']} ({output['rows']:,} lignes). Répétitions : {output['method']['repeats']}",
        f"Environnement : Python {output['environment']['python_version']}, {output['environment']['operating_system']}, "
        f"{output['environment']['architecture']}, {output['environment']['logical_cpu_count']} processeurs logiques, "
        f"{(output['environment']['physical_memory_bytes'] or 0) / (1024 ** 3):.0f} Gio de mémoire.",
        "",
        "Les anomalies sont intentionnelles : un statut FAIL indique que l’outil a détecté la règle violée. "
        "La concordance compare les nombres de lignes aux injections connues.",
        "",
        "## Temps médians",
        "",
        "| Outil | Version | Chargement (s) | Préparation (s) | Contrôles (s) | Total (s) | Comptes conformes |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, details in output["tools"].items():
        runs = tool_runs[name]
        first = runs[0] if runs else {}
        version_string = first.get("version", "-")
        if first.get("spark_version"):
            version_string += f" / Spark {first['spark_version']}"
        timings = details.get("median_timings_seconds", {})
        lines.append(
            "| {tool} | {version} | {load} | {setup} | {validation} | {total} | {matches} |".format(
                tool=labels.get(name, name),
                version=version_string,
                load=timings.get("load_seconds", "—"),
                setup=timings.get("setup_seconds", "—"),
                validation=timings.get("validation_seconds", "—"),
                total=timings.get("total_seconds", "—"),
                matches="oui" if details.get("all_counts_match_ground_truth") else "non",
            )
        )

    lines.extend(
        [
            "",
            "## Détections par règle",
            "",
            "| Règle | Lignes attendues | Great Expectations | Soda Core* | PyDeequ / Deequ |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for rule_id in RULE_IDS:
        expected = output["expected_counts"][rule_id]["affected_rows"]
        values = []
        for name in ("great_expectations", "soda_core", "pydeequ"):
            runs = tool_runs.get(name, [])
            if not runs:
                values.append("—")
                continue
            result = next((item for item in runs[0].get("checks", []) if item.get("rule_id") == rule_id), {})
            count = result.get("normalized_affected_rows", result.get("reported_violations"))
            values.append(str(count) if count is not None else "—")
        lines.append(f"| {rule_id} | {expected} | {values[0]} | {values[1]} | {values[2]} |")

    lines.extend(
        [
            "",
            "* Soda compte les occurrences en doublon au-delà de la première. Chaque groupe injecté contient deux lignes; le tableau convertit ce compte en lignes affectées en le multipliant par deux.",
            "",
            "Les temps incluent l’initialisation propre à chaque outil. Pour PyDeequ, Spark est arrêté entre les répétitions; le processus Java passerelle est conservé pendant la série.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
