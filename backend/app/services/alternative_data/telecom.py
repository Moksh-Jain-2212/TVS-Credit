"""Telecom recharge pattern adapter."""

from __future__ import annotations

from app.models import AlternativeSourceType
from app.services.alternative_data.base import NormalizedAlternativeData
from app.services.alternative_data.normalization import (
    adverse_from_supportive,
    bounded_score,
    monthly_totals,
    number,
    parse_date,
    period_bounds,
    quality_from_records,
    require_records,
    stability,
)


class TelecomAdapter:
    source_type = AlternativeSourceType.TELECOM

    def normalize(self, payload: dict) -> NormalizedAlternativeData:
        records = require_records(payload, "Telecom")
        dated = sorted((parse_date(record.get("date"), "date"), number(record.get("amount"), "amount", minimum=0)) for record in records)
        dates = [item[0] for item in dated]
        amounts = [item[1] for item in dated]
        intervals = [(dates[index] - dates[index - 1]).days for index in range(1, len(dates))]
        long_gap_ratio = sum(1 for days in intervals if days > 45) / max(1, len(intervals))
        months = max(1, len(set(date.strftime("%Y-%m") for date in dates)))
        features = {
            "average_recharge_amount": sum(amounts) / len(amounts),
            "recharge_frequency": len(records) / months,
            "interval_regularity": stability([float(days) for days in intervals]) if intervals else 0.5,
            "long_gap_ratio": long_gap_ratio,
            "recharge_spend_stability": stability(monthly_totals(dated)),
            "observable_account_tenure_months": months,
            "factor_scores": {
                "recharge_frequency": bounded_score(60 - (len(records) / months) * 10),
                "interval_regularity": adverse_from_supportive(stability([float(days) for days in intervals]) if intervals else 0.5),
                "long_gap_ratio": bounded_score(long_gap_ratio * 100),
                "spend_stability": adverse_from_supportive(stability(monthly_totals(dated))),
            },
        }
        start, end = period_bounds(dates)
        return NormalizedAlternativeData(
            source_type=self.source_type,
            normalized_features=features,
            data_quality={"quality_score": quality_from_records(records, ["date", "amount"])},
            period_start=start,
            period_end=end,
        )

    def mock_payload(self) -> dict:
        return {
            "records": [
                {"date": "2026-01-03", "amount": 299},
                {"date": "2026-02-02", "amount": 299},
                {"date": "2026-03-04", "amount": 349},
                {"date": "2026-04-02", "amount": 299},
                {"date": "2026-05-03", "amount": 299},
                {"date": "2026-06-02", "amount": 349},
            ]
        }
