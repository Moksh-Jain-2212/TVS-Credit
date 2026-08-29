"""E-commerce seller settlement adapter."""

from __future__ import annotations

from app.models import AlternativeSourceType
from app.services.alternative_data.base import NormalizedAlternativeData
from app.services.alternative_data.normalization import (
    adverse_from_supportive,
    bounded_score,
    median_or_zero,
    monthly_totals,
    number,
    parse_date,
    period_bounds,
    quality_from_records,
    require_records,
    stability,
    trend,
)


class EcommerceAdapter:
    source_type = AlternativeSourceType.ECOMMERCE

    def normalize(self, payload: dict) -> NormalizedAlternativeData:
        records = require_records(payload, "E-commerce")
        settlements = []
        refunds = 0.0
        reversals = 0.0
        dates = []
        for record in records:
            observed = parse_date(record.get("date"), "date")
            dates.append(observed)
            settlement = number(record.get("settlement_amount"), "settlement_amount", minimum=0)
            settlements.append((observed, settlement))
            refunds += number(record.get("refund_amount", 0), "refund_amount", minimum=0)
            reversals += number(record.get("reversal_amount", 0), "reversal_amount", minimum=0)
        totals = monthly_totals(settlements)
        gross = sum(value for _, value in settlements)
        refund_rate = (refunds + reversals) / max(gross, 1.0)
        features = {
            "median_monthly_settlement": median_or_zero(totals),
            "settlement_consistency": stability(totals),
            "settlement_trend": trend(totals),
            "refund_reversal_rate": refund_rate,
            "merchant_revenue_stability": stability(totals),
            "factor_scores": {
                "settlement_consistency": adverse_from_supportive(stability(totals)),
                "settlement_trend": bounded_score(50 - trend(totals) * 80),
                "refund_reversal_rate": bounded_score(refund_rate * 100),
                "merchant_revenue_stability": adverse_from_supportive(stability(totals)),
            },
        }
        start, end = period_bounds(dates)
        return NormalizedAlternativeData(
            source_type=self.source_type,
            normalized_features=features,
            data_quality={"quality_score": quality_from_records(records, ["date", "settlement_amount"])},
            period_start=start,
            period_end=end,
        )

    def mock_payload(self) -> dict:
        return {
            "records": [
                {"date": "2026-01-31", "settlement_amount": 72000, "refund_amount": 2000, "reversal_amount": 0},
                {"date": "2026-02-28", "settlement_amount": 76000, "refund_amount": 1600, "reversal_amount": 0},
                {"date": "2026-03-31", "settlement_amount": 73500, "refund_amount": 2100, "reversal_amount": 800},
                {"date": "2026-04-30", "settlement_amount": 79000, "refund_amount": 1700, "reversal_amount": 0},
            ]
        }
