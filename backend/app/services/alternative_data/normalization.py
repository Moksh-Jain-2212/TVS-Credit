"""Normalization helpers for alternative-data source adapters."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from statistics import mean, median, pstdev
from typing import Any

from fastapi import HTTPException, status


def parse_date(value: Any, field_name: str = "date") -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} must be YYYY-MM-DD")
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} must be YYYY-MM-DD") from exc


def require_records(payload: dict[str, Any], source: str) -> list[dict[str, Any]]:
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{source} records are required")
    if not all(isinstance(item, dict) for item in records):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{source} records must be objects")
    return records


def number(value: Any, field_name: str, *, minimum: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} must be numeric") from exc
    if minimum is not None and result < minimum:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} must be at least {minimum}")
    return result


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "on", "paid", "success", "on_time"}
    return bool(value)


def month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def trend(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    first = mean(values[: max(1, len(values) // 2)])
    second = mean(values[max(1, len(values) // 2):])
    return (second - first) / max(abs(first), 1.0)


def stability(values: list[float]) -> float:
    if len(values) < 2:
        return 0.5
    avg = mean(values)
    return max(0.0, min(1.0, 1.0 - (pstdev(values) / max(abs(avg), 1.0))))


def volatility(values: list[float]) -> float:
    return 1.0 - stability(values)


def quality_from_records(records: list[dict[str, Any]], required_fields: list[str]) -> float:
    if not records:
        return 0.0
    checks = 0
    present = 0
    for record in records:
        for field in required_fields:
            checks += 1
            if record.get(field) not in {None, ""}:
                present += 1
    return round(present / max(checks, 1), 3)


def period_bounds(dates: list[date]) -> tuple[datetime | None, datetime | None]:
    if not dates:
        return None, None
    return datetime.combine(min(dates), datetime.min.time()), datetime.combine(max(dates), datetime.min.time())


def monthly_totals(records: list[tuple[date, float]]) -> list[float]:
    buckets: dict[str, float] = defaultdict(float)
    for observed_date, amount in records:
        buckets[month_key(observed_date)] += amount
    return [buckets[key] for key in sorted(buckets)]


def bounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 3)


def adverse_from_supportive(supportive_ratio: float) -> float:
    return bounded_score((1.0 - max(0.0, min(1.0, supportive_ratio))) * 100.0)


def median_or_zero(values: list[float]) -> float:
    return float(median(values)) if values else 0.0
