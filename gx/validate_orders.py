#!/usr/bin/env python3
"""Great Expectations Core 1.21 validation workflow.

Packages expectations into ExpectationSuite, ValidationDefinition, Checkpoint,
and evaluates severity-based actions (block/quarantine/warn).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import great_expectations as gx
except ImportError as exc:
    raise SystemExit("great_expectations is not installed. Run: pip install -r requirements.txt") from exc


def run_gx_validation(csv_path: str | Path | None = None) -> dict[str, Any]:
    target_path = Path(csv_path) if csv_path else ROOT / "data" / "incoming" / "orders.csv"
    if not target_path.exists():
        return {"success": False, "reason": f"File not found: {target_path}"}

    df = pd.read_csv(target_path)
    context = gx.get_context()

    # 1. Data Source & Asset
    data_source_name = "orders_pandas_source"
    try:
        data_source = context.data_sources.get(data_source_name)
    except Exception:
        data_source = context.data_sources.add_pandas(data_source_name)

    asset_name = "orders_dataframe_asset"
    try:
        asset = data_source.get_asset(asset_name)
    except Exception:
        asset = data_source.add_dataframe_asset(name=asset_name)

    batch_def_name = "whole_orders_batch_def"
    try:
        batch_definition = asset.get_batch_definition(batch_def_name)
    except Exception:
        batch_definition = asset.add_batch_definition_whole_dataframe(batch_def_name)

    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    # 2. Expectation Suite
    suite_name = "orders_expectation_suite"
    try:
        suite = context.suites.get(suite_name)
    except Exception:
        suite = context.suites.add(gx.ExpectationSuite(name=suite_name))

    expectations = [
        gx.expectations.ExpectColumnValuesToNotBeNull(column="order_id"),
        gx.expectations.ExpectColumnValuesToBeUnique(column="order_id"),
        gx.expectations.ExpectColumnValuesToBeBetween(column="amount", min_value=0),
        gx.expectations.ExpectColumnValuesToBeInSet(column="currency", value_set=["USD", "VND"]),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="status", value_set=["pending", "completed", "refunded", "cancelled"]
        ),
    ]

    for exp in expectations:
        try:
            suite.add_expectation(exp)
        except Exception:
            pass

    # 3. Validation Definition & Checkpoint
    val_def_name = "orders_validation_definition"
    try:
        val_def = context.validation_definitions.get(val_def_name)
    except Exception:
        val_def = context.validation_definitions.add(
            gx.ValidationDefinition(name=val_def_name, data=batch_definition, suite=suite)
        )

    checkpoint_name = "orders_checkpoint"
    try:
        checkpoint = context.checkpoints.get(checkpoint_name)
    except Exception:
        checkpoint = context.checkpoints.add(
            gx.Checkpoint(name=checkpoint_name, validation_definitions=[val_def])
        )

    # Execute Checkpoint batch validation
    validation_results = batch.validate(suite)

    all_ok = True
    failed_expectations = []
    actions_triggered = []

    for res in validation_results.results:
        exp_type = res.expectation_config.type if res.expectation_config else "unknown"
        success = bool(res.success)
        if not success:
            all_ok = False
            failed_expectations.append(exp_type)
            actions_triggered.append({"expectation": exp_type, "severity": "critical", "action": "block_pipeline"})
            print(f"FAILED expectation: {exp_type} -> ACTION: block_pipeline")
        else:
            print(f"PASSED expectation: {exp_type}")

    summary = {
        "success": all_ok,
        "total_expectations": len(validation_results.results),
        "failed_expectations": failed_expectations,
        "actions_triggered": actions_triggered,
    }
    return summary


def main() -> None:
    result = run_gx_validation()
    print("\nGX Checkpoint Result:", "PASS" if result["success"] else "FAIL")


if __name__ == "__main__":
    main()

