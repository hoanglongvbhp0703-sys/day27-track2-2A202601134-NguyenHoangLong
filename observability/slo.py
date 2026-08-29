from __future__ import annotations

from typing import Any


def calculate_slo(target: float, bad_events: int, total_events: int) -> dict[str, Any]:
    if not 0 < target < 1:
        raise ValueError("target must be between 0 and 1 (exclusive)")
    if bad_events < 0 or total_events < 0 or bad_events > total_events:
        raise ValueError("invalid event counts")
    allowed_bad_rate = 1.0 - target
    if total_events == 0:
        return {
            "target": target,
            "actual_bad_rate": 0.0,
            "allowed_bad_rate": allowed_bad_rate,
            "burn_rate": 0.0,
            "remaining_error_budget_fraction": 1.0,
            "breached": False,
        }
    actual_bad_rate = bad_events / total_events
    burn_rate = actual_bad_rate / allowed_bad_rate
    consumed_fraction = min(1.0, actual_bad_rate / allowed_bad_rate)
    return {
        "target": target,
        "actual_bad_rate": actual_bad_rate,
        "allowed_bad_rate": allowed_bad_rate,
        "burn_rate": burn_rate,
        "remaining_error_budget_fraction": max(0.0, 1.0 - consumed_fraction),
        "breached": bool(actual_bad_rate > allowed_bad_rate),
    }


def evaluate_multiwindow_burn(
    *,
    short_window_burn: float,
    long_window_burn: float,
    policy: str = "sre_multiwindow",
) -> dict[str, Any]:
    """Evaluate multi-window multi-burn-rate alerting policy.

    Distinguishes sustained fast burn (requiring page) from short transient spikes (warn only).
    Standard SRE thresholds:
    - Fast sustained burn: short_window > 14.4 and long_window > 6.0 -> page=True, severity='critical'
    - Transient spike: short_window > 14.4 and long_window <= 6.0 -> page=False, severity='warning'
    - Medium burn: long_window > 3.0 or short_window > 3.0 -> page=False, severity='warning'
    - Normal: otherwise -> page=False, severity='info'
    """
    short_b = float(short_window_burn)
    long_b = float(long_window_burn)

    if short_b > 14.4 and long_b > 6.0:
        return {
            "page": True,
            "severity": "critical",
            "reason": f"Sustained fast burn rate detected: short={short_b:.1f}, long={long_b:.1f}",
            "short_window_burn": short_b,
            "long_window_burn": long_b,
        }
    elif short_b > 14.4 and long_b <= 6.0:
        return {
            "page": False,
            "severity": "warning",
            "reason": f"Transient spike detected (no page): short={short_b:.1f}, long={long_b:.1f}",
            "short_window_burn": short_b,
            "long_window_burn": long_b,
        }
    elif long_b > 3.0 or short_b > 3.0:
        return {
            "page": False,
            "severity": "warning",
            "reason": f"Elevated burn rate detected: short={short_b:.1f}, long={long_b:.1f}",
            "short_window_burn": short_b,
            "long_window_burn": long_b,
        }
    else:
        return {
            "page": False,
            "severity": "info",
            "reason": f"Burn rate within normal range: short={short_b:.1f}, long={long_b:.1f}",
            "short_window_burn": short_b,
            "long_window_burn": long_b,
        }

