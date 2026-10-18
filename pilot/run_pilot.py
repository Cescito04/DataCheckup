"""Run representative checks on the 100-row sample with three tools."""

from __future__ import annotations

import json
import os
import sys
import traceback
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "data" / "orders_100.csv"
CONTRACT_PATH = ROOT / "contracts" / "soda_pilot.yml"
RESULTS_PATH = ROOT / "results" / "pilot_results.json"
RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)


def installed_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not installed"


def run_great_expectations() -> dict:
    import great_expectations as gx
    import pandas as pd

    df = pd.read_csv(CSV_PATH)
    context = gx.get_context(mode="ephemeral")
    source = context.data_sources.add_pandas(name="orders_pandas")
    asset = source.add_dataframe_asset(name="orders_100")
    batch_definition = asset.add_batch_definition_whole_dataframe("pilot_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    expectations = {
        "C1": gx.expectations.ExpectColumnValuesToNotBeNull(column="customer_id"),
        "U1": gx.expectations.ExpectColumnValuesToBeUnique(column="order_id"),
        "V2": gx.expectations.ExpectColumnValuesToBeBetween(column="unit_price", min_value=0),
        "V3": gx.expectations.ExpectColumnValuesToBeInSet(
            column="currency", value_set=["EUR", "USD", "GBP"]
        ),
    }
    rows = []
    for rule_id, expectation in expectations.items():
        result = batch.validate(expectation).to_json_dict()
        details = result.get("result", {})
        rows.append(
            {
                "rule_id": rule_id,
                "success": result.get("success"),
                "unexpected_count": details.get("unexpected_count"),
                "observed_value": details.get("observed_value"),
            }
        )
    return {"version": gx.__version__, "checks": rows}


def run_soda() -> dict:
    import duckdb
    import pandas as pd
    from soda_core.contracts import verify_contract_locally
    from soda_duckdb import DuckDBDataSource

    df = pd.read_csv(CSV_PATH)
    connection = duckdb.connect(database=":memory:")
    connection.register("orders_input", df)
    connection.execute("CREATE TABLE orders AS SELECT * FROM orders_input")
    data_source = DuckDBDataSource.from_existing_cursor(connection.cursor(), name="pilot")
    result = verify_contract_locally(
        data_sources=[data_source],
        contract_file_path=str(CONTRACT_PATH),
    )
    contract_result = result.results[0]
    return {
        "version": installed_version("soda-core"),
        "status": contract_result.status.value,
        "checks": [
            {
                "path": check.check.relative_path,
                "rule": check.check.type,
                "outcome": check.outcome.value,
                "metrics": check.diagnostic_metric_values,
            }
            for check in contract_result.check_results
        ],
    }


def run_deequ() -> dict:
    os.environ["SPARK_VERSION"] = "4.1"

    from pydeequ.checks import Check, CheckLevel
    from pydeequ.verification import VerificationSuite
    from pyspark.sql import SparkSession

    ivy_dir = Path("/private/tmp/datacheckup-pilot-ivy")
    ivy_dir.mkdir(parents=True, exist_ok=True)
    spark = (
        SparkSession.builder.master("local[1]")
        .appName("DataCheckup-100-row-pilot")
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
            .option("inferSchema", "true")
            .option("nullValue", "")
            .option("emptyValue", "")
            .csv(str(CSV_PATH))
        )
        check = Check(spark, CheckLevel.Error, "pilot representative checks")
        check.isComplete("customer_id")
        check.isUnique("order_id")
        check.isNonNegative("unit_price")
        check.isContainedIn("currency", ["EUR", "USD", "GBP"])
        verification = VerificationSuite(spark).onData(df).addCheck(check).run()
        return {
            "version": installed_version("pydeequ"),
            "spark_version": spark.version,
            "status": verification.status,
            "checks": verification.checkResults,
        }
    finally:
        spark.stop()
        gateway.shutdown_callback_server()
        gateway.shutdown()


def main() -> int:
    output = {
        "dataset": str(CSV_PATH.relative_to(ROOT)),
        "rows": 100,
        "pilot_scope": ["C1", "U1", "V2 (minimum only)", "V3"],
        "tools": {},
    }
    runners = {
        "great_expectations": run_great_expectations,
        "soda_core": run_soda,
        "pydeequ": run_deequ,
    }
    for tool_name, runner in runners.items():
        try:
            output["tools"][tool_name] = {"ok": True, **runner()}
        except Exception as error:  # Capture per-tool setup failures and continue the pilot.
            output["tools"][tool_name] = {
                "ok": False,
                "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(),
            }

    RESULTS_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    return 0 if all(tool.get("ok") for tool in output["tools"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
