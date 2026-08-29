"""Segment-aware financial interpretation for the shared NADI flow."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.models import AlternativeDataSnapshot, AlternativeSourceType, BorrowerSegment, LoanApplication


SEGMENT_LABELS = {
    BorrowerSegment.SALARIED.value: "Salaried Employee",
    BorrowerSegment.GIG_WORKER.value: "Gig / Platform Worker",
    BorrowerSegment.SMALL_MERCHANT.value: "Small Merchant",
    BorrowerSegment.INFORMAL_WORKER.value: "Informal Worker",
}

SEGMENT_RELEVANT_SOURCES = {
    BorrowerSegment.SALARIED.value: [AlternativeSourceType.UPI.value],
    BorrowerSegment.GIG_WORKER.value: [
        AlternativeSourceType.UPI.value,
        AlternativeSourceType.MOBILITY.value,
        AlternativeSourceType.ECOMMERCE.value,
    ],
    BorrowerSegment.SMALL_MERCHANT.value: [
        AlternativeSourceType.UPI.value,
        AlternativeSourceType.GST.value,
        AlternativeSourceType.ECOMMERCE.value,
    ],
    BorrowerSegment.INFORMAL_WORKER.value: [
        AlternativeSourceType.UPI.value,
        AlternativeSourceType.UTILITIES.value,
        AlternativeSourceType.TELECOM.value,
    ],
}

SEGMENT_INTERPRETATIONS = {
    BorrowerSegment.SALARIED.value: "Your assessment uses the stability of recurring salary credits.",
    BorrowerSegment.GIG_WORKER.value: "Your income varies, so NADI uses a conservative lower-income estimate for affordability.",
    BorrowerSegment.SMALL_MERCHANT.value: "NADI uses your business surplus after operating expenses rather than gross turnover.",
    BorrowerSegment.INFORMAL_WORKER.value: "NADI uses observed cash-flow and recurring credits instead of requiring formal payroll evidence.",
}

LEGACY_EMPLOYMENT_SEGMENTS = {
    "salaried": BorrowerSegment.SALARIED.value,
    "salary": BorrowerSegment.SALARIED.value,
    "employee": BorrowerSegment.SALARIED.value,
    "gig": BorrowerSegment.GIG_WORKER.value,
    "driver": BorrowerSegment.GIG_WORKER.value,
    "platform": BorrowerSegment.GIG_WORKER.value,
    "merchant": BorrowerSegment.SMALL_MERCHANT.value,
    "self-employed": BorrowerSegment.SMALL_MERCHANT.value,
    "self_employed": BorrowerSegment.SMALL_MERCHANT.value,
    "business": BorrowerSegment.SMALL_MERCHANT.value,
    "informal": BorrowerSegment.INFORMAL_WORKER.value,
}


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None or pd.isna(value):
        return default
    return float(value)


def round_money(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def conservative_value(mean_value: float, volatility: float, floor: float = 0.0) -> float:
    return max(floor, mean_value * (1.0 - min(0.75, max(0.0, volatility) * 1.28)))


def normalize_borrower_segment(application: LoanApplication) -> str:
    raw_segment = application.borrower_segment.value if hasattr(application.borrower_segment, "value") else application.borrower_segment
    if raw_segment in SEGMENT_LABELS:
        return str(raw_segment)
    employment = (application.employment_type or "").strip().lower()
    return LEGACY_EMPLOYMENT_SEGMENTS.get(employment, BorrowerSegment.SALARIED.value)


def source_features(snapshots: list[AlternativeDataSnapshot]) -> dict[str, dict[str, Any]]:
    return {snapshot.source_type.value: snapshot.normalized_features_json for snapshot in snapshots}


def build_common_features(application: LoanApplication, row: pd.Series) -> dict[str, Any]:
    inflow = safe_float(row.get("mean_monthly_inflow"), safe_float(application.declared_monthly_income))
    outflow = safe_float(row.get("mean_monthly_outflow"), safe_float(application.declared_monthly_expenses))
    net_cashflow = safe_float(row.get("mean_monthly_net_cash_flow"), inflow - outflow)
    volatility = safe_float(row.get("income_volatility"), 0.0)
    average_balance = safe_float(row.get("average_balance"), safe_float(row.get("pre_loan_latest_balance")))
    existing_debt = safe_float(application.existing_monthly_emi)
    return {
        "average_monthly_inflow": round_money(inflow),
        "median_monthly_inflow": round_money(safe_float(row.get("median_monthly_inflow"), inflow)),
        "p10_monthly_inflow": round_money(safe_float(row.get("p10_monthly_inflow"), conservative_value(inflow, volatility))),
        "average_monthly_outflow": round_money(outflow),
        "net_cashflow": round_money(net_cashflow),
        "income_volatility": round(volatility, 4),
        "average_balance": round_money(average_balance),
        "minimum_balance": round_money(safe_float(row.get("minimum_balance"), average_balance - outflow)),
        "positive_cashflow_ratio": round(safe_float(row.get("positive_cash_flow_month_ratio"), 1.0 if net_cashflow > 0 else 0.0), 4),
        "months_history": int(safe_float(row.get("months_of_history"), 0.0)),
        "existing_debt": round_money(existing_debt),
        "monthly_surplus": round_money(net_cashflow),
    }


def salaried_features(application: LoanApplication, common: dict[str, Any], features: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], float, float]:
    upi = features.get(AlternativeSourceType.UPI.value, {})
    monthly_income = safe_float(upi.get("monthly_inflow"), safe_float(common["average_monthly_inflow"]))
    declared_income = safe_float(application.declared_monthly_income)
    salary = monthly_income if safe_float(upi.get("recurring_income_indicators")) > 0 else declared_income or monthly_income
    volatility = safe_float(common["income_volatility"], 0.0)
    p10_salary = min(safe_float(common["p10_monthly_inflow"], salary), conservative_value(salary, volatility))
    expenses = safe_float(application.declared_monthly_expenses, safe_float(common["average_monthly_outflow"]))
    existing_emi = safe_float(application.existing_monthly_emi)
    average_salary = salary
    segment = {
        "salary_frequency": "monthly",
        "salary_regularity": round(safe_float(upi.get("inflow_stability"), 1.0 - volatility), 4),
        "average_salary": round_money(average_salary),
        "median_salary": round_money(safe_float(common["median_monthly_inflow"], average_salary)),
        "p10_salary": round_money(p10_salary),
        "salary_growth": round(safe_float(upi.get("income_trend"), safe_float(common.get("income_trend"))), 4),
        "income_volatility": round(volatility, 4),
        "monthly_expenses": round_money(expenses),
        "existing_emi": round_money(existing_emi),
        "emi_to_income_ratio": round(existing_emi / max(p10_salary, 1.0), 4),
        "average_balance": common["average_balance"],
        "minimum_balance": common["minimum_balance"],
        "monthly_surplus": round_money(p10_salary - expenses - existing_emi),
    }
    return segment, p10_salary, p10_salary - expenses - existing_emi


def gig_features(application: LoanApplication, common: dict[str, Any], features: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], float, float]:
    upi = features.get(AlternativeSourceType.UPI.value, {})
    mobility = features.get(AlternativeSourceType.MOBILITY.value, {})
    monthly_income = safe_float(upi.get("monthly_inflow"), safe_float(common["average_monthly_inflow"]))
    volatility = max(safe_float(common["income_volatility"], 0.0), 1.0 - safe_float(upi.get("inflow_stability"), 0.76))
    p10_monthly = safe_float(common["p10_monthly_inflow"], conservative_value(monthly_income, volatility))
    average_weekly = monthly_income / 4.33
    p10_weekly = p10_monthly / 4.33
    tx_per_month = safe_float(upi.get("transactions_per_month"), safe_float(common.get("transaction_density")))
    source_count = max(1, int(round(1.0 / max(safe_float(upi.get("concentration"), 1.0), 0.1))))
    expenses = safe_float(application.declared_monthly_expenses, safe_float(common["average_monthly_outflow"]))
    existing_emi = safe_float(application.existing_monthly_emi)
    segment = {
        "average_weekly_income": round_money(average_weekly),
        "median_weekly_income": round_money(average_weekly),
        "p10_weekly_income": round_money(p10_weekly),
        "average_monthly_income": round_money(monthly_income),
        "p10_monthly_income": round_money(p10_monthly),
        "active_income_days": int(max(1, min(31, round(tx_per_month)))),
        "platform_payout_frequency": "weekly_or_fortnightly" if tx_per_month >= 8 else "monthly_or_irregular",
        "number_of_income_sources": source_count,
        "weekly_income_volatility": round(volatility, 4),
        "monthly_income_volatility": round(volatility, 4),
        "income_trend": round(safe_float(upi.get("income_trend"), 0.0), 4),
        "low_income_week_ratio": round(clamp01(volatility), 4),
        "active_month_ratio": round(safe_float(mobility.get("vehicle_active_month_ratio"), safe_float(common["positive_cashflow_ratio"], 1.0)), 4),
        "expense_to_income_ratio": round(expenses / max(monthly_income, 1.0), 4),
        "monthly_surplus": round_money(p10_monthly - expenses - existing_emi),
    }
    for key in (
        "trips_per_month",
        "distance_per_month",
        "vehicle_active_month_ratio",
        "usage_consistency",
        "distance_trend",
        "fuel_toll_payment_regularity",
        "maintenance_payment_regularity",
    ):
        if key in mobility:
            segment[key] = round_money(safe_float(mobility[key])) if "per_month" in key else round(safe_float(mobility[key]), 4)
    return segment, p10_monthly, p10_monthly - expenses - existing_emi


def merchant_features(application: LoanApplication, common: dict[str, Any], features: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], float, float]:
    upi = features.get(AlternativeSourceType.UPI.value, {})
    gst = features.get(AlternativeSourceType.GST.value, {})
    ecommerce = features.get(AlternativeSourceType.ECOMMERCE.value, {})
    turnover = max(
        safe_float(gst.get("median_monthly_turnover")),
        safe_float(upi.get("monthly_inflow")),
        safe_float(common["average_monthly_inflow"]),
    )
    settlement = safe_float(ecommerce.get("median_monthly_settlement"))
    business_expenses = max(safe_float(upi.get("monthly_outflow")), safe_float(application.declared_monthly_expenses), turnover * 0.68)
    surplus_candidates = [
        safe_float(upi.get("monthly_net_inflow")),
        settlement * max(0.0, 1.0 - safe_float(ecommerce.get("refund_reversal_rate"), 0.0)),
        turnover - business_expenses,
    ]
    business_surplus = max(0.0, max(surplus_candidates))
    volatility = max(
        safe_float(gst.get("turnover_volatility"), 0.0),
        1.0 - safe_float(ecommerce.get("settlement_consistency"), 0.82),
        safe_float(common["income_volatility"], 0.0),
    )
    p10_surplus = conservative_value(business_surplus, volatility)
    existing_emi = safe_float(application.existing_monthly_emi)
    segment = {
        "monthly_turnover": round_money(turnover),
        "median_turnover": round_money(safe_float(gst.get("median_monthly_turnover"), turnover)),
        "p10_turnover": round_money(conservative_value(turnover, volatility)),
        "settlement_amount": round_money(settlement) if settlement else None,
        "settlement_frequency": "monthly" if settlement else None,
        "settlement_stability": round(safe_float(ecommerce.get("settlement_consistency"), 0.0), 4) if settlement else None,
        "business_expenses": round_money(business_expenses),
        "refund_ratio": round(safe_float(ecommerce.get("refund_reversal_rate"), 0.0), 4) if settlement else None,
        "reversal_ratio": round(safe_float(ecommerce.get("refund_reversal_rate"), 0.0), 4) if settlement else None,
        "revenue_growth": round(safe_float(gst.get("turnover_trend"), safe_float(ecommerce.get("settlement_trend"), 0.0)), 4),
        "revenue_volatility": round(volatility, 4),
        "net_business_cash_flow": round_money(business_surplus),
        "business_surplus": round_money(business_surplus),
        "p10_business_surplus": round_money(p10_surplus),
        "seasonality": "insufficient_history" if safe_float(common["months_history"]) < 12 else "observed",
        "GST_turnover_consistency": round(safe_float(gst.get("business_inflow_consistency"), 0.0), 4) if gst else None,
        "UPI_inflow_consistency": round(safe_float(upi.get("inflow_stability"), 0.0), 4) if upi else None,
    }
    return segment, p10_surplus, p10_surplus - existing_emi


def informal_features(application: LoanApplication, common: dict[str, Any], features: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], float, float]:
    upi = features.get(AlternativeSourceType.UPI.value, {})
    utilities = features.get(AlternativeSourceType.UTILITIES.value, {})
    monthly_inflow = safe_float(upi.get("monthly_inflow"), safe_float(common["average_monthly_inflow"]))
    volatility = max(safe_float(common["income_volatility"], 0.0), 1.0 - safe_float(upi.get("inflow_stability"), 0.7))
    p10_inflow = safe_float(common["p10_monthly_inflow"], conservative_value(monthly_inflow, volatility))
    expenses = safe_float(application.declared_monthly_expenses, safe_float(common["average_monthly_outflow"]))
    existing_emi = safe_float(application.existing_monthly_emi)
    tx_per_month = safe_float(upi.get("transactions_per_month"), 0.0)
    source_diversity = max(1, int(round(1.0 / max(safe_float(upi.get("concentration"), 1.0), 0.1))))
    segment = {
        "recurring_credit_patterns": int(safe_float(upi.get("recurring_income_indicators"), 0.0)),
        "recurring_credit_strength": round(safe_float(upi.get("inflow_stability"), 1.0 - volatility), 4),
        "total_monthly_inflow": round_money(monthly_inflow),
        "median_monthly_inflow": common["median_monthly_inflow"],
        "p10_monthly_inflow": round_money(p10_inflow),
        "credit_frequency": round(tx_per_month, 2),
        "active_income_days": int(max(1, min(31, round(tx_per_month)))),
        "income_source_diversity": source_diversity,
        "monthly_expenses": round_money(expenses),
        "monthly_surplus": round_money(p10_inflow - expenses - existing_emi),
        "positive_cashflow_month_ratio": common["positive_cashflow_ratio"],
        "balance_stability": round(1.0 - safe_float(common.get("income_volatility"), volatility), 4),
        "utility_payment_regularity": round(safe_float(utilities.get("on_time_payment_ratio"), 0.0), 4) if utilities else None,
        "UPI_activity_consistency": round(safe_float(upi.get("transaction_frequency_stability"), 0.0), 4) if upi else None,
        "income_volatility": round(volatility, 4),
        "history_length": common["months_history"],
    }
    return segment, p10_inflow, p10_inflow - expenses - existing_emi


def calculate_segment_analysis(
    application: LoanApplication,
    row: pd.Series,
    snapshots: list[AlternativeDataSnapshot],
) -> dict[str, Any]:
    segment = normalize_borrower_segment(application)
    common = build_common_features(application, row)
    features = source_features(snapshots)
    if segment == BorrowerSegment.GIG_WORKER.value:
        segment_features, conservative_income, surplus = gig_features(application, common, features)
    elif segment == BorrowerSegment.SMALL_MERCHANT.value:
        segment_features, conservative_income, surplus = merchant_features(application, common, features)
    elif segment == BorrowerSegment.INFORMAL_WORKER.value:
        segment_features, conservative_income, surplus = informal_features(application, common, features)
    else:
        segment_features, conservative_income, surplus = salaried_features(application, common, features)

    sustainable_surplus = max(0.0, surplus)
    return {
        "borrower_segment": segment,
        "borrower_segment_label": SEGMENT_LABELS[segment],
        "common_financial_features": {key: value for key, value in common.items() if value is not None},
        "segment_specific_features": {key: value for key, value in segment_features.items() if value is not None},
        "conservative_income": round_money(conservative_income),
        "sustainable_monthly_surplus": round_money(sustainable_surplus),
        "income_interpretation": SEGMENT_INTERPRETATIONS[segment],
        "relevant_evidence": SEGMENT_RELEVANT_SOURCES[segment],
        "connected_relevant_evidence": [
            snapshot.source_type.value for snapshot in snapshots if snapshot.source_type.value in SEGMENT_RELEVANT_SOURCES[segment]
        ],
    }


def apply_segment_analysis(row: pd.Series, analysis: dict[str, Any]) -> pd.Series:
    enriched = row.copy()
    sustainable_surplus = safe_float(analysis["sustainable_monthly_surplus"])
    expected_surplus = max(sustainable_surplus, safe_float(row.get("cash_flow_forecast_p50"), sustainable_surplus))
    optimistic_surplus = max(expected_surplus, safe_float(row.get("cash_flow_forecast_p90"), expected_surplus))
    enriched["borrower_segment"] = analysis["borrower_segment"]
    enriched["borrower_segment_label"] = analysis["borrower_segment_label"]
    enriched["segment_relevant_sources"] = analysis["relevant_evidence"]
    enriched["segment_connected_relevant_sources"] = analysis["connected_relevant_evidence"]
    enriched["common_financial_features"] = analysis["common_financial_features"]
    enriched["segment_specific_features"] = analysis["segment_specific_features"]
    enriched["conservative_income"] = analysis["conservative_income"]
    enriched["sustainable_monthly_surplus"] = analysis["sustainable_monthly_surplus"]
    enriched["income_interpretation"] = analysis["income_interpretation"]
    enriched["mean_monthly_net_cash_flow"] = sustainable_surplus
    enriched["cash_flow_forecast_p10"] = sustainable_surplus
    enriched["cash_flow_forecast_p50"] = expected_surplus
    enriched["cash_flow_forecast_p90"] = optimistic_surplus
    enriched["cash_flow_forecast_method"] = f"SEGMENT_AWARE_{analysis['borrower_segment']}_CAPACITY"
    return enriched
