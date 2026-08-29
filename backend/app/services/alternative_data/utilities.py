"""Utility bill payment adapter."""

from __future__ import annotations

from app.models import AlternativeSourceType
from app.services.alternative_data.base import NormalizedAlternativeData
from app.services.alternative_data.normalization import (
    adverse_from_supportive,
    bounded_score,
    boolish,
    number,
    parse_date,
    period_bounds,
    quality_from_records,
    require_records,
    stability,
    trend,
)


class UtilitiesAdapter:
    source_type = AlternativeSourceType.UTILITIES

    def normalize(self, payload: dict) -> NormalizedAlternativeData:
        records = require_records(payload, "Utility")
        dates = []
        amounts = []
        on_time = 0
        missed = 0
        late_or_missed = 0
        for record in records:
            bill_date = parse_date(record.get("bill_date"), "bill_date")
            due_date = parse_date(record.get("due_date"), "due_date")
            paid_date = parse_date(record.get("paid_date"), "paid_date") if record.get("paid_date") else None
            amount = number(record.get("amount"), "amount", minimum=0)
            status_text = str(record.get("status", "")).upper()
            dates.append(bill_date)
            amounts.append(amount)
            paid_on_time = boolish(record.get("paid_on_time", False)) or (paid_date is not None and paid_date <= due_date)
            if paid_on_time:
                on_time += 1
            if status_text == "MISSED" or paid_date is None:
                missed += 1
            if not paid_on_time:
                late_or_missed += 1
        observed = len(records)
        features = {
            "observed_bills": observed,
            "on_time_payment_ratio": on_time / observed,
            "late_payment_ratio": max(0, late_or_missed - missed) / observed,
            "missed_payment_ratio": missed / observed,
            "arrears_trend": trend([1.0 if record.get("status", "").upper() == "MISSED" else 0.0 for record in records]),
            "bill_amount_stability": stability(amounts),
            "payment_continuity": 1.0 - (missed / observed),
            "factor_scores": {
                "on_time_payment_ratio": adverse_from_supportive(on_time / observed),
                "late_or_missed_ratio": bounded_score((late_or_missed / observed) * 100),
                "arrears_trend": bounded_score(50 + trend([1.0 if record.get("status", "").upper() == "MISSED" else 0.0 for record in records]) * 80),
                "bill_amount_stability": adverse_from_supportive(stability(amounts)),
                "payment_continuity": adverse_from_supportive(1.0 - (missed / observed)),
            },
        }
        start, end = period_bounds(dates)
        return NormalizedAlternativeData(
            source_type=self.source_type,
            normalized_features=features,
            data_quality={"quality_score": quality_from_records(records, ["bill_date", "due_date", "amount", "status"])},
            period_start=start,
            period_end=end,
        )

    def mock_payload(self) -> dict:
        return {
            "records": [
                {"bill_date": "2026-01-01", "due_date": "2026-01-10", "paid_date": "2026-01-08", "amount": 1800, "status": "PAID"},
                {"bill_date": "2026-02-01", "due_date": "2026-02-10", "paid_date": "2026-02-09", "amount": 1760, "status": "PAID"},
                {"bill_date": "2026-03-01", "due_date": "2026-03-10", "paid_date": "2026-03-13", "amount": 1900, "status": "PAID"},
                {"bill_date": "2026-04-01", "due_date": "2026-04-10", "paid_date": "2026-04-09", "amount": 1840, "status": "PAID"},
            ]
        }
