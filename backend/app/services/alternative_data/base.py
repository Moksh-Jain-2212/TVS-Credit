"""Common source-adapter interface for alternative data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.models import AlternativeSourceType


@dataclass(frozen=True)
class NormalizedAlternativeData:
    source_type: AlternativeSourceType
    normalized_features: dict[str, Any]
    data_quality: dict[str, Any]
    period_start: datetime | None
    period_end: datetime | None
    schema_version: str = "alt-data-v1"


class AlternativeDataAdapter(Protocol):
    source_type: AlternativeSourceType

    def normalize(self, payload: dict[str, Any]) -> NormalizedAlternativeData:
        ...

    def mock_payload(self) -> dict[str, Any]:
        ...


SOURCE_DESCRIPTIONS: dict[AlternativeSourceType, dict[str, str]] = {
    AlternativeSourceType.GST: {
        "label": "GST / Business",
        "requested": "Monthly filing and turnover aggregates.",
        "why": "Supports business income continuity and turnover stability.",
        "excluded": "No tax secrets, unrelated demographics, or protected traits.",
    },
    AlternativeSourceType.UPI: {
        "label": "UPI",
        "requested": "Aggregated payment trends, success/failure status, and inflow/outflow amounts.",
        "why": "Helps estimate cash-flow regularity and reversal-heavy activity.",
        "excluded": "No raw counterparties are exposed in underwriting views.",
    },
    AlternativeSourceType.TELECOM: {
        "label": "Telecom Recharge",
        "requested": "Recharge dates and amounts only.",
        "why": "Adds continuity evidence for thin-file borrowers.",
        "excluded": "No call logs, SMS content, contact lists, or communication graphs.",
    },
    AlternativeSourceType.UTILITIES: {
        "label": "Utility Bills",
        "requested": "Bill dates, due dates, paid dates, bill amounts, and payment status.",
        "why": "Shows payment continuity without using credit bureau history.",
        "excluded": "No protected demographic information.",
    },
    AlternativeSourceType.ECOMMERCE: {
        "label": "E-commerce",
        "requested": "Seller settlement totals, orders, refunds, and reversals.",
        "why": "Supports business revenue stability for merchants.",
        "excluded": "No shopping preferences or product-category socioeconomic inference.",
    },
    AlternativeSourceType.MOBILITY: {
        "label": "Mobility / Vehicle",
        "requested": "Aggregated trips, distance, fuel/toll spend, and maintenance-payment regularity.",
        "why": "Supports income-activity continuity for mobility-linked work.",
        "excluded": "No exact location traces or raw GPS history.",
    },
}
