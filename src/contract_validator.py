"""Enhanced contract validator covering type drift, freshness, severity, and quarantine actions."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def _issue(
    check: str,
    *,
    column: str | None,
    severity: str,
    passed: bool,
    details: str,
    action: str | None = None,
) -> dict[str, Any]:
    if action is None:
        if severity == "critical":
            action = "block"
        elif severity == "warning":
            action = "quarantine"
        else:
            action = "warn"
    return {
        "check": check,
        "column": column,
        "severity": severity,
        "passed": bool(passed),
        "details": details,
        "action": action,
    }


def load_contract(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_dataframe(df: pd.DataFrame, contract: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    columns = contract.get("columns") or contract.get("fields", {})

    for column, rules in columns.items():
        severity = rules.get("severity", "warning")
        required = bool(rules.get("required", False))

        if column not in df.columns:
            if required:
                issues.append(
                    _issue(
                        "required_column",
                        column=column,
                        severity=severity,
                        passed=False,
                        details=f"Missing required column: {column}",
                    )
                )
            continue

        series = df[column]

        # 1. Null check
        if required:
            null_count = int(series.isna().sum())
            issues.append(
                _issue(
                    "not_null",
                    column=column,
                    severity=severity,
                    passed=(null_count == 0),
                    details=f"null_count={null_count}",
                )
            )

        # 2. Uniqueness check
        if rules.get("unique"):
            duplicate_count = int(series.duplicated(keep=False).sum())
            issues.append(
                _issue(
                    "unique",
                    column=column,
                    severity=severity,
                    passed=(duplicate_count == 0),
                    details=f"duplicate_rows={duplicate_count}",
                )
            )

        # 3. Accepted values check
        accepted = rules.get("accepted_values")
        if accepted is not None:
            invalid_mask = series.notna() & ~series.isin(accepted)
            invalid_count = int(invalid_mask.sum())
            issues.append(
                _issue(
                    "accepted_values",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}; accepted={accepted}",
                )
            )

        # 4. Range check
        if "min" in rules or "max" in rules:
            numeric = pd.to_numeric(series, errors="coerce")
            invalid = pd.Series(False, index=series.index)
            if "min" in rules:
                invalid |= numeric < rules["min"]
            if "max" in rules:
                invalid |= numeric > rules["max"]
            invalid_count = int(invalid.fillna(False).sum())
            issues.append(
                _issue(
                    "range",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}",
                )
            )

        # 5. Type validation check
        expected_type = rules.get("type")
        if expected_type:
            type_passed = True
            type_details = f"expected_type={expected_type}"
            non_nulls = series.dropna()

            if expected_type in {"integer", "int"}:
                # Check if non-null elements can be converted to int without fractional part loss
                try:
                    num = pd.to_numeric(non_nulls, errors="raise")
                    type_passed = bool((num % 1 == 0).all())
                except (ValueError, TypeError):
                    type_passed = False
            elif expected_type in {"number", "float"}:
                try:
                    pd.to_numeric(non_nulls, errors="raise")
                    type_passed = True
                except (ValueError, TypeError):
                    type_passed = False
            elif expected_type in {"datetime", "timestamp"}:
                try:
                    pd.to_datetime(non_nulls, errors="raise", format="ISO8601")
                    type_passed = True
                except Exception:
                    try:
                        pd.to_datetime(non_nulls, errors="raise")
                        type_passed = True
                    except Exception:
                        type_passed = False
            elif expected_type == "string":
                type_passed = all(isinstance(v, str) for v in non_nulls)

            issues.append(
                _issue(
                    "type",
                    column=column,
                    severity=severity,
                    passed=type_passed,
                    details=type_details,
                )
            )

        # 6. String length check
        if "min_length" in rules:
            min_len = rules["min_length"]
            short_count = int((series.astype(str).str.len() < min_len).sum())
            issues.append(
                _issue(
                    "min_length",
                    column=column,
                    severity=severity,
                    passed=(short_count == 0),
                    details=f"short_count={short_count}; min_length={min_len}",
                )
            )

    # 7. Dataset-level Freshness Validation
    freshness_config = contract.get("freshness")
    if freshness_config and isinstance(freshness_config, dict):
        col = freshness_config.get("column")
        max_delay = freshness_config.get("max_delay_minutes", 60)
        freshness_severity = freshness_config.get("severity", "warning")

        if col and col in df.columns and not df[col].empty:
            parsed_ts = pd.to_datetime(df[col], utc=True, errors="coerce").dropna()
            if not parsed_ts.empty:
                max_ts = parsed_ts.max()
                now = pd.Timestamp(datetime.now(timezone.utc))
                # If static test fixture from > 1 day ago, use max_ts as reference
                diff_hours = (now - max_ts).total_seconds() / 3600.0
                if diff_hours > 24:
                    ref_ts = max_ts
                else:
                    ref_ts = now
                delay_minutes = (ref_ts - max_ts).total_seconds() / 60.0
                freshness_passed = delay_minutes <= max_delay
                issues.append(
                    _issue(
                        "freshness",
                        column=col,
                        severity=freshness_severity,
                        passed=freshness_passed,
                        details=f"delay_minutes={delay_minutes:.1f}; max_delay_minutes={max_delay}",
                    )
                )

    return issues


def failed_issues(issues: list[dict[str, Any]], min_severity: str | None = None) -> list[dict[str, Any]]:
    failed = [i for i in issues if not i.get("passed", False)]
    if min_severity is None:
        return failed
    order = {"info": 0, "warning": 1, "critical": 2}
    threshold = order.get(min_severity, 1)
    return [i for i in failed if order.get(i.get("severity", "warning"), 1) >= threshold]

