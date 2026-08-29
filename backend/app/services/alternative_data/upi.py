"""UPI transaction trend adapter."""

from __future__ import annotations

from collections import Counter, defaultdict

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


class UpiAdapter:
    source_type = AlternativeSourceType.UPI

    def normalize(self, payload: dict) -> NormalizedAlternativeData:
        records = require_records(payload, "UPI")
        inflows = []
        outflows = []
        dates = []
        monthly_counts: dict[str, int] = defaultdict(int)
        failed = 0
        counterparties: Counter[str] = Counter()
        for record in records:
            observed = parse_date(record.get("date"), "date")
            dates.append(observed)
            amount = number(record.get("amount"), "amount", minimum=0)
            flow = str(record.get("type", "")).upper()
            status = str(record.get("status", "SUCCESS")).upper()
            monthly_counts[observed.strftime("%Y-%m")] += 1
            counterparties[str(record.get("counterparty", "unknown"))] += 1
            if status in {"FAILED", "REVERSED"}:
                failed += 1
            if flow == "INFLOW":
                inflows.append((observed, amount))
            elif flow == "OUTFLOW":
                outflows.append((observed, amount))
            else:
                raise ValueError("UPI type must be INFLOW or OUTFLOW")
        start, end = period_bounds(dates)
        monthly_inflow = monthly_totals(inflows)
        monthly_outflow = monthly_totals(outflows)
        months = max(1, len(monthly_counts))
        net = (sum(value for _, value in inflows) - sum(value for _, value in outflows)) / months
        concentration = max(counterparties.values()) / max(1, len(records))
        features = {
            "transactions_per_month": len(records) / months,
            "monthly_inflow": sum(value for _, value in inflows) / months,
            "monthly_outflow": sum(value for _, value in outflows) / months,
            "monthly_net_inflow": net,
            "inflow_stability": stability(monthly_inflow),
            "transaction_frequency_stability": stability([float(count) for count in monthly_counts.values()]),
            "failed_reversed_transaction_ratio": failed / len(records),
            "concentration": concentration,
            "recurring_income_indicators": sum(1 for _, count in counterparties.items() if count >= 3),
            "factor_scores": {
                "monthly_net_inflow": bounded_score(50 - (net / 2000)),
                "inflow_stability": adverse_from_supportive(stability(monthly_inflow)),
                "frequency_stability": adverse_from_supportive(stability([float(count) for count in monthly_counts.values()])),
                "failed_reversed_ratio": bounded_score((failed / len(records)) * 100),
                "concentration": bounded_score(concentration * 100),
            },
        }
        return NormalizedAlternativeData(
            source_type=self.source_type,
            normalized_features=features,
            data_quality={"quality_score": quality_from_records(records, ["date", "amount", "type", "status"])},
            period_start=start,
            period_end=end,
        )

    def mock_payload(self) -> dict:
        return {
            "records": [
                {"date": "2026-01-05", "type": "INFLOW", "amount": 42000, "status": "SUCCESS", "counterparty": "income"},
                {"date": "2026-01-12", "type": "OUTFLOW", "amount": 18000, "status": "SUCCESS", "counterparty": "household"},
                {"date": "2026-02-05", "type": "INFLOW", "amount": 43000, "status": "SUCCESS", "counterparty": "income"},
                {"date": "2026-02-12", "type": "OUTFLOW", "amount": 18500, "status": "SUCCESS", "counterparty": "household"},
                {"date": "2026-03-05", "type": "INFLOW", "amount": 42500, "status": "SUCCESS", "counterparty": "income"},
                {"date": "2026-03-20", "type": "OUTFLOW", "amount": 2100, "status": "REVERSED", "counterparty": "merchant"},
            ]
        }
