"""GST/business turnover alternative-data adapter."""

from __future__ import annotations

from app.models import AlternativeSourceType
from app.services.alternative_data.base import NormalizedAlternativeData
from app.services.alternative_data.normalization import (
    adverse_from_supportive,
    bounded_score,
    boolish,
    median_or_zero,
    number,
    parse_date,
    period_bounds,
    quality_from_records,
    require_records,
    trend,
    volatility,
)


class GstAdapter:
    source_type = AlternativeSourceType.GST

    def normalize(self, payload: dict) -> NormalizedAlternativeData:
        records = require_records(payload, "GST")
        turnovers: list[float] = []
        filing_dates = []
        late_or_zero = 0
        on_time = 0
        for record in records:
            observed = parse_date(record.get("month"), "month")
            filing_dates.append(observed)
            turnover = number(record.get("turnover"), "turnover", minimum=0)
            turnovers.append(turnover)
            filed_on_time = boolish(record.get("filed_on_time", True))
            if filed_on_time:
                on_time += 1
            if turnover == 0 or not filed_on_time:
                late_or_zero += 1
        start, end = period_bounds(filing_dates)
        months = len(records)
        filing_regularity = on_time / months
        late_or_zero_ratio = late_or_zero / months
        turnover_volatility = volatility(turnovers)
        features = {
            "active_filing_months": months,
            "filing_regularity": filing_regularity,
            "median_monthly_turnover": median_or_zero(turnovers),
            "turnover_trend": trend(turnovers),
            "turnover_volatility": turnover_volatility,
            "zero_late_filing_ratio": late_or_zero_ratio,
            "business_inflow_consistency": 1.0 - turnover_volatility,
            "factor_scores": {
                "filing_regularity": adverse_from_supportive(filing_regularity),
                "turnover_trend": bounded_score(50 - trend(turnovers) * 80),
                "turnover_volatility": bounded_score(turnover_volatility * 100),
                "late_or_zero_filing_ratio": bounded_score(late_or_zero_ratio * 100),
                "business_inflow_consistency": adverse_from_supportive(1.0 - turnover_volatility),
            },
        }
        return NormalizedAlternativeData(
            source_type=self.source_type,
            normalized_features=features,
            data_quality={"quality_score": quality_from_records(records, ["month", "turnover"])},
            period_start=start,
            period_end=end,
        )

    def mock_payload(self) -> dict:
        return {
            "records": [
                {"month": "2026-01-01", "turnover": 128000, "filed_on_time": True},
                {"month": "2026-02-01", "turnover": 134000, "filed_on_time": True},
                {"month": "2026-03-01", "turnover": 141000, "filed_on_time": True},
                {"month": "2026-04-01", "turnover": 136000, "filed_on_time": True},
                {"month": "2026-05-01", "turnover": 148000, "filed_on_time": False},
                {"month": "2026-06-01", "turnover": 153000, "filed_on_time": True},
            ]
        }
