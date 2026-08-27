"""Financial stress simulation for borrower repayment capacity."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


POLICY_PATH = Path(__file__).resolve().parents[1] / "core" / "stress_scenarios.json"


@dataclass(frozen=True)
class StressScenario:
    name: str
    income_multiplier: float
    expense_shock: float
    cash_flow_quantile: str
    expense_shock_period: int | None = None


@dataclass(frozen=True)
class StressPolicy:
    survival_buffer_floor: float
    scenarios: list[StressScenario]


def load_stress_policy(path: Path = POLICY_PATH) -> StressPolicy:
    data = json.loads(path.read_text(encoding="utf-8"))
    scenarios = [
        StressScenario(
            name=str(item["name"]),
            income_multiplier=float(item["income_multiplier"]),
            expense_shock=float(item.get("expense_shock", 0.0)),
            expense_shock_period=(
                int(item["expense_shock_period"]) if item.get("expense_shock_period") is not None else None
            ),
            cash_flow_quantile=str(item["cash_flow_quantile"]),
        )
        for item in data["scenarios"]
    ]
    return StressPolicy(
        survival_buffer_floor=float(data["survival_buffer_floor"]),
        scenarios=scenarios,
    )


def safe_float(value: Any, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def forecast_for_quantile(row: pd.Series, quantile: str) -> float:
    column = {
        "p10": "cash_flow_forecast_p10",
        "p50": "cash_flow_forecast_p50",
        "p90": "cash_flow_forecast_p90",
    }[quantile]
    return safe_float(row.get(column), 0.0)


def simulate_scenario(
    row: pd.Series,
    scenario: StressScenario,
    survival_buffer_floor: float,
) -> dict[str, Any]:
    tenure = max(1, int(safe_float(row.get("duration_months"), 1.0)))
    emi = safe_float(row.get("scheduled_payment"), 0.0)
    latest_buffer = safe_float(row.get("pre_loan_latest_balance"), 0.0)
    forecast_cash_flow = forecast_for_quantile(row, scenario.cash_flow_quantile)
    income = safe_float(row.get("mean_monthly_inflow"), 0.0)
    income_loss = income * (1.0 - scenario.income_multiplier)
    scenario_monthly_cash_flow = forecast_cash_flow - income_loss

    projected_buffer = latest_buffer
    min_buffer = projected_buffer
    worst_period = 0
    failed_periods = 0
    for period in range(1, tenure + 1):
        expense_shock = (
            scenario.expense_shock
            if scenario.expense_shock_period is not None and period == scenario.expense_shock_period
            else 0.0
        )
        projected_buffer += scenario_monthly_cash_flow - emi - expense_shock
        if projected_buffer < min_buffer:
            min_buffer = projected_buffer
            worst_period = period
        if projected_buffer < survival_buffer_floor:
            failed_periods += 1

    survived = failed_periods == 0
    stress_probability = failed_periods / tenure
    return {
        "scenario": scenario.name,
        "survived": survived,
        "stress_probability": stress_probability,
        "minimum_remaining_cash_buffer": float(min_buffer),
        "worst_projected_period": int(worst_period),
        "monthly_cash_flow_after_stress": float(scenario_monthly_cash_flow),
    }


def simulate_borrower_stress(
    row: pd.Series,
    policy: StressPolicy,
) -> dict[str, Any]:
    scenario_results = [
        simulate_scenario(row, scenario, policy.survival_buffer_floor)
        for scenario in policy.scenarios
    ]
    worst = min(scenario_results, key=lambda item: item["minimum_remaining_cash_buffer"])
    stress_probability = max(item["stress_probability"] for item in scenario_results)
    return {
        "scenario_survival": {
            item["scenario"]: item["survived"] for item in scenario_results
        },
        "stress_probability": float(stress_probability),
        "minimum_remaining_cash_buffer": float(worst["minimum_remaining_cash_buffer"]),
        "worst_scenario": str(worst["scenario"]),
        "worst_projected_period": int(worst["worst_projected_period"]),
        "scenario_results": scenario_results,
    }
