"""Deterministic verifier (Layer 1) for consolidated BI reports.

For every finding and recommendation:
- Resolves each cited ``metric_key`` from the deterministic metrics engine.
- Compares every entry in ``stated_values`` against the ground-truth value from the database
  (tolerance: exact for counts, ±0.5% or ±0.05 rounding for money and rates).
- Scans narrative text for numeric literals not backed by a cited ``metric_key`` or standard
  domain constants (such as the dataset period year 2026 or the 90-day expiry window) and flags
  them as ``unsupported_claims``.
"""

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.metrics import METRIC_SPECS, UnknownMetricError, get_metric
from app.schemas.analysis import StrategyReportOutput

# Numbers that are part of fixed domain definitions (not metric claims).
_ALLOWED_CONTEXT_NUMBERS = {
    2026.0,
    90.0,
    60.0,
    1.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
    7.0,
    8.0,
    10.0,
    15.0,
    1.5,
    31.0,
}

# Matches standalone numbers like 2,500 or 22,256,456.76 or 49.92 or -19.30
_NUMBER_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(-?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)"
)


def _within_tolerance(unit: str, stated: float, actual: float) -> bool:
    if unit == "count":
        return round(stated) == round(actual)
    if actual == 0:
        return abs(stated) <= 0.05
    rel_err = abs(stated - actual) / abs(actual)
    abs_err = abs(stated - actual)
    return rel_err <= 0.005 or abs_err <= 0.05 or round(stated) == round(actual)


def _matches_any_known(num: float, known_values: list[float]) -> bool:
    if num in _ALLOWED_CONTEXT_NUMBERS:
        return True
    for kv in known_values:
        if abs(num - kv) <= 0.05 or round(num) == round(kv):
            return True
        if kv != 0 and abs(num - kv) / abs(kv) <= 0.005:
            return True
        # Also allow millions/lakhs/crores shorthand if backed by the exact metric
        for scale in (1e5, 1e6, 1e7):
            scaled = kv / scale
            if abs(scaled) >= 0.1 and abs(num - round(scaled, 2)) <= 0.02:
                return True
    return False


def verify_strategy_report(
    db: Session, dataset_id: uuid.UUID, report: StrategyReportOutput
) -> dict[str, Any]:
    """Run Layer-1 deterministic verification on a StrategyReportOutput."""
    checked = 0
    passed = 0
    failed: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    resolved_cache: dict[str, dict[str, Any]] = {}

    def _resolve(key: str) -> dict[str, Any] | None:
        if key in resolved_cache:
            return resolved_cache[key]
        try:
            m = get_metric(db, dataset_id, key)
            resolved_cache[key] = m
            return m
        except UnknownMetricError:
            return None

    # 1. Check every finding's metric_keys and stated_values
    for idx, finding in enumerate(report.findings):
        finding_known_vals: list[float] = []
        for mkey in finding.metric_keys:
            checked += 1
            m = _resolve(mkey)
            if m is None:
                failed.append(
                    {
                        "location": f"findings[{idx}]",
                        "metric_key": mkey,
                        "reason": "unknown_metric_key",
                    }
                )
                continue
            actual = float(m["value"])
            finding_known_vals.append(actual)
            if mkey in finding.stated_values:
                stated = float(finding.stated_values[mkey])
                if _within_tolerance(m["unit"], stated, actual):
                    passed += 1
                else:
                    failed.append(
                        {
                            "location": f"findings[{idx}]",
                            "metric_key": mkey,
                            "reason": "value_mismatch",
                            "stated": stated,
                            "actual": actual,
                            "unit": m["unit"],
                        }
                    )
            else:
                passed += 1

        # Scan the finding statement for numbers not backed by any cited metric_key
        for match in _NUMBER_TOKEN_RE.finditer(finding.statement):
            raw_token = match.group(1)
            try:
                val = float(raw_token.replace(",", ""))
            except ValueError:
                continue
            if not _matches_any_known(val, finding_known_vals):
                unsupported.append(
                    {
                        "location": f"findings[{idx}]",
                        "number": raw_token,
                        "statement": finding.statement,
                        "reason": "number_not_backed_by_cited_metric_key",
                    }
                )

    # 2. Check every recommendation's evidence_metric_keys
    for idx, rec in enumerate(report.recommendations):
        for mkey in rec.evidence_metric_keys:
            checked += 1
            if mkey not in METRIC_SPECS or _resolve(mkey) is None:
                failed.append(
                    {
                        "location": f"recommendations[{idx}]",
                        "metric_key": mkey,
                        "reason": "unknown_metric_key",
                    }
                )
            else:
                passed += 1

    return {
        "checked": checked,
        "passed": passed,
        "failed": failed,
        "unsupported": unsupported,
        "is_valid": len(failed) == 0 and len(unsupported) == 0,
    }
