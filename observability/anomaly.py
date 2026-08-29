"""Anomaly detection module supporting Z-score, MAD, and context-aware auto detection."""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def zscore_detector(current: float, history: Iterable[float], threshold: float = 3.0) -> dict[str, Any]:
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "zscore", "reason": "insufficient_history"}
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0:
        score = float("inf") if float(current) != mean else 0.0
    else:
        score = abs(float(current) - mean) / std
    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "zscore",
        "reason": f"mean={mean:.3f}, std={std:.3f}, threshold={threshold}",
    }


def mad_detector(current: float, history: Iterable[float], threshold: float = 3.5) -> dict[str, Any]:
    """Robust Median Absolute Deviation (MAD) detector with zero-MAD edge case handling."""
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "mad", "reason": "insufficient_history"}
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad == 0:
        score = 0.0 if float(current) == median else float("inf")
    else:
        score = 0.6745 * abs(float(current) - median) / mad

    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "mad",
        "reason": f"median={median:.3f}, mad={mad:.3f}, threshold={threshold}",
    }


def detect_anomaly(
    current: float,
    history: Iterable[float],
    *,
    method: str = "auto",
    threshold: float = 3.0,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Context-aware anomaly detector.

    Supports 'zscore', 'mad', and 'auto'. In 'auto' mode, uses context information
    (e.g., same_segment_history, day_of_week) if provided, and selects MAD for
    robust estimation or Z-score as fallback.
    """
    if method == "mad":
        return mad_detector(current, history, threshold=threshold)

    if method == "zscore":
        return zscore_detector(current, history, threshold=threshold)

    if method == "auto":
        effective_history = list(history)
        selected_method = "auto:zscore"

        if context and isinstance(context, dict):
            if "same_segment_history" in context and context["same_segment_history"]:
                effective_history = list(context["same_segment_history"])
                selected_method = "auto:seasonality_mad"

        if len(effective_history) >= 5:
            res = mad_detector(current, effective_history, threshold=threshold)
            res["method"] = selected_method if selected_method.startswith("auto:") else "auto:mad"
            return res
        else:
            res = zscore_detector(current, effective_history, threshold=threshold)
            res["method"] = selected_method
            return res

    raise ValueError(f"Unsupported method: {method}")

