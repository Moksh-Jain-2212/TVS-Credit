"""Deterministic, segment-aware synthetic evidence for the local NADI demo.

These generators are deliberately not presented as live GST or telecom integrations.
They produce aggregate-only demo records that pass through the same normalization
contract as a future consented connector.
"""

from __future__ import annotations

from datetime import date
from hashlib import sha256
from random import Random
from typing import Any

from app.models import AlternativeSourceType, BorrowerSegment, LoanApplication


GENERATOR_VERSION = "segment-synthetic-v1"


def _segment(application: LoanApplication) -> str:
    value = application.borrower_segment
    value = value.value if hasattr(value, "value") else value
    return str(value or BorrowerSegment.SALARIED.value)


def _random_for(application: LoanApplication, source: AlternativeSourceType) -> Random:
    material = f"nadi|{GENERATOR_VERSION}|{application.id}|{_segment(application)}|{source.value}"
    return Random(int(sha256(material.encode("utf-8")).hexdigest()[:16], 16))


def _monthly_dates() -> list[date]:
    return [date(2025 + (month - 1) // 12, ((month - 1) % 12) + 1, 1) for month in range(7, 19)]


def gst_payload(application: LoanApplication) -> dict[str, Any]:
    """Create twelve aggregate filing records with coherent segment-specific behaviour."""
    segment = _segment(application)
    rng = _random_for(application, AlternativeSourceType.GST)
    declared_income = float(application.declared_monthly_income or 30_000)
    multiplier = {
        BorrowerSegment.SMALL_MERCHANT.value: 4.4,
        BorrowerSegment.GIG_WORKER.value: 1.55,
        BorrowerSegment.INFORMAL_WORKER.value: 1.25,
        BorrowerSegment.SALARIED.value: 1.1,
    }.get(segment, 1.1)
    base_turnover = max(18_000, declared_income * multiplier)
    records = []
    for index, month in enumerate(_monthly_dates()):
        festival_factor = 1.18 if month.month in {10, 11} and segment == BorrowerSegment.SMALL_MERCHANT.value else 1.0
        trend_factor = 1 + (index - 5.5) * (0.012 if segment == BorrowerSegment.SMALL_MERCHANT.value else 0.004)
        noise = rng.uniform(-0.09, 0.09 if segment != BorrowerSegment.GIG_WORKER.value else 0.15)
        turnover = round(max(0, base_turnover * festival_factor * trend_factor * (1 + noise)), 2)
        late_probability = 0.07 if segment == BorrowerSegment.SMALL_MERCHANT.value else 0.18
        records.append({"month": month.isoformat(), "turnover": turnover, "filed_on_time": rng.random() >= late_probability})
    return {"records": records}


def telecom_payload(application: LoanApplication) -> dict[str, Any]:
    """Create aggregate recharge events; no calls, contacts, SMS, or location data."""
    segment = _segment(application)
    rng = _random_for(application, AlternativeSourceType.TELECOM)
    plan_amount = {
        BorrowerSegment.SALARIED.value: 349,
        BorrowerSegment.GIG_WORKER.value: 299,
        BorrowerSegment.SMALL_MERCHANT.value: 399,
        BorrowerSegment.INFORMAL_WORKER.value: 249,
    }.get(segment, 299)
    records = []
    for index, month in enumerate(_monthly_dates()):
        day = 2 + rng.randrange(0, 6)
        if segment == BorrowerSegment.GIG_WORKER.value and index in {3, 8}:
            day += 12  # realistic but non-sensitive irregularity in a gig profile
        amount = plan_amount + rng.choice([0, 0, 0, 50, -25])
        records.append({"date": date(month.year, month.month, min(day, 26)).isoformat(), "amount": max(99, amount)})
        if segment == BorrowerSegment.SMALL_MERCHANT.value and index in {2, 7}:
            records.append({"date": date(month.year, month.month, min(day + 14, 27)).isoformat(), "amount": 99})
    return {"records": records}


def generated_mock_payload(application: LoanApplication, source: AlternativeSourceType) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if source == AlternativeSourceType.GST:
        payload = gst_payload(application)
    elif source == AlternativeSourceType.TELECOM:
        payload = telecom_payload(application)
    else:
        return None
    return payload, {
        "evidence_origin": "PARAMETERIZED_SYNTHETIC_DEMO",
        "generator_version": GENERATOR_VERSION,
        "borrower_segment": _segment(application),
        "deterministic_seed_basis": "application_id_and_borrower_segment",
        "privacy_note": "aggregate records only; no personal identifiers or communications content",
    }
