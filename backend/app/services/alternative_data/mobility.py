"""Aggregated mobility/vehicle usage adapter."""

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


class MobilityAdapter:
    source_type = AlternativeSourceType.MOBILITY

    def normalize(self, payload: dict) -> NormalizedAlternativeData:
        records = require_records(payload, "Mobility")
        dates = []
        trips = []
        distances = []
        payment_regular = 0
        maintenance_regular = 0
        for record in records:
            observed = parse_date(record.get("month"), "month")
            dates.append(observed)
            trips.append(number(record.get("trips"), "trips", minimum=0))
            distances.append(number(record.get("distance_km"), "distance_km", minimum=0))
            if boolish(record.get("fuel_toll_paid_regularly", True)):
                payment_regular += 1
            if boolish(record.get("maintenance_paid_on_time", True)):
                maintenance_regular += 1
        months = len(records)
        active_ratio = sum(1 for value in trips if value > 0) / months
        usage_consistency = stability(distances)
        fuel_regular = payment_regular / months
        maintenance = maintenance_regular / months
        features = {
            "trips_per_month": sum(trips) / months,
            "distance_per_month": sum(distances) / months,
            "vehicle_active_month_ratio": active_ratio,
            "usage_consistency": usage_consistency,
            "distance_trend": trend(distances),
            "fuel_toll_payment_regularity": fuel_regular,
            "maintenance_payment_regularity": maintenance,
            "factor_scores": {
                "vehicle_active_month_ratio": adverse_from_supportive(active_ratio),
                "usage_consistency": adverse_from_supportive(usage_consistency),
                "distance_trend": bounded_score(50 - trend(distances) * 60),
                "fuel_toll_payment_regularity": adverse_from_supportive(fuel_regular),
                "maintenance_regularity": adverse_from_supportive(maintenance),
            },
        }
        start, end = period_bounds(dates)
        return NormalizedAlternativeData(
            source_type=self.source_type,
            normalized_features=features,
            data_quality={"quality_score": quality_from_records(records, ["month", "trips", "distance_km"])},
            period_start=start,
            period_end=end,
        )

    def mock_payload(self) -> dict:
        return {
            "records": [
                {"month": "2026-01-01", "trips": 84, "distance_km": 1160, "fuel_toll_paid_regularly": True, "maintenance_paid_on_time": True},
                {"month": "2026-02-01", "trips": 88, "distance_km": 1215, "fuel_toll_paid_regularly": True, "maintenance_paid_on_time": True},
                {"month": "2026-03-01", "trips": 81, "distance_km": 1100, "fuel_toll_paid_regularly": True, "maintenance_paid_on_time": True},
                {"month": "2026-04-01", "trips": 86, "distance_km": 1185, "fuel_toll_paid_regularly": True, "maintenance_paid_on_time": False},
            ]
        }
