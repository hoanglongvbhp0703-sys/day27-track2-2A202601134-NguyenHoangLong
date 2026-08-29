from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def detect_distribution_shift(
    current_values: Iterable[float],
    baseline_values: Iterable[float],
    *,
    ratio_threshold: float = 3.0,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Distribution drift detector using KS-test and mean ratio analysis."""
    cur = np.asarray(list(current_values), dtype=float)
    base = np.asarray(list(baseline_values), dtype=float)

    if cur.size == 0 or base.size == 0:
        return {"is_anomaly": False, "score": 0.0, "method": "ks_test_mean_ratio", "reason": "empty_input"}

    cur_mean = float(np.mean(cur))
    base_mean = float(np.mean(base))

    if base_mean == 0:
        ratio_score = float("inf") if cur_mean != 0 else 1.0
    else:
        ratio_score = max(abs(cur_mean / base_mean), abs(base_mean / cur_mean)) if cur_mean != 0 else float("inf")

    # Perform KS test for non-parametric distribution comparison
    try:
        from scipy.stats import ks_2samp
        stat, p_value = ks_2samp(cur, base)
        ks_anomaly = bool(p_value < alpha)
        ks_score = float(stat)
    except Exception:
        ks_anomaly = False
        ks_score = 0.0
        p_value = 1.0

    is_anomaly = bool(ratio_score >= ratio_threshold or ks_anomaly)
    score = max(ratio_score if ratio_score != float("inf") else 999.0, ks_score * 10)

    return {
        "is_anomaly": is_anomaly,
        "score": float(score),
        "method": "ks_test_mean_ratio",
        "reason": f"baseline_mean={base_mean:.3f}, current_mean={cur_mean:.3f}, mean_ratio={ratio_score:.2f}, ks_p_value={p_value:.4f}",
    }

