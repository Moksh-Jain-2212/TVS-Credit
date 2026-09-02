"""Reproducibly bootstrap local NADI demo artifacts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR_CANDIDATES = (
    REPO_ROOT / "data" / "raw" / "pkdd",
    REPO_ROOT / "data" / "raw",
)
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "nadi_features.csv"
METADATA_PATH = REPO_ROOT / "data" / "processed" / "artifact_metadata.json"


def run_step(args: list[str]) -> None:
    subprocess.run([sys.executable, *args], cwd=REPO_ROOT, check=True)


def raw_pkdd_dir() -> Path | None:
    required = {"account.asc", "client.asc", "disp.asc", "loan.asc", "order.asc", "trans.asc"}
    for raw_dir in RAW_DIR_CANDIDATES:
        if required.issubset({path.name for path in raw_dir.glob("*.asc")}):
            return raw_dir
    return None


def write_fallback_features() -> None:
    FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    # Keep the fallback dataset aligned with the documented demo cases and
    # integration flows. These IDs are not PKDD records; they are stable,
    # deterministic local-fixture identifiers.
    demo_loan_ids = {1: 6097, 4: 5161}
    for index in range(18):
        year = 1994 + (index // 5)
        target = index % 2
        income = 24000 + index * 1800
        outflow = 12000 + (index % 4) * 2500 + target * 4000
        net = income - outflow
        rows.append(
            {
                "loan_id": demo_loan_ids.get(index, 9000 + index),
                "account_id": 7000 + index,
                "primary_client_id": 5000 + index,
                "primary_client_birth_number": None,
                "loan_date": f"{min(year, 1997)}-0{(index % 9) + 1}-15",
                "account_open_date": f"{min(year, 1997) - 1}-01-01",
                "pre_loan_first_transaction_date": f"{min(year, 1997) - 1}-01-01",
                "pre_loan_last_transaction_date": f"{min(year, 1997)}-01-01",
                "loan_status_target": "B" if target else "A",
                "loan_status_from_source": "B" if target else "A",
                "loan_status_meaning": "defaulted" if target else "repaid",
                "repayment_outcome_known": True,
                "repayment_default_target": target,
                "target_exclusion_reason": None,
                "requested_amount": 30000 + index * 5000,
                "duration_months": 12 + (index % 3) * 6,
                "scheduled_payment": 3000 + index * 280,
                "months_of_history": 6 + (index % 10),
                "mean_monthly_inflow": income,
                "median_monthly_inflow": income * 0.98,
                "p10_monthly_inflow": income * 0.82,
                "mean_monthly_outflow": outflow,
                "mean_monthly_net_cash_flow": net,
                "average_monthly_surplus": net,
                "positive_cash_flow_month_ratio": 0.8 if net > 0 else 0.3,
                "income_volatility": 0.1 + target * 0.25,
                "balance_volatility": 0.12 + target * 0.2,
                "average_balance": max(5000, net * 2),
                "minimum_balance": min(8000, net),
                "transaction_density": 4 + (index % 6),
                "recurring_inflow_count": 1 + (index % 3),
                "recurring_outflow_count": 1 + (index % 2),
                "standing_order_count": index % 3,
                "standing_order_monthly_burden": 1200 * (index % 3),
                "income_trend": 400 - target * 800,
                "top_inflow_source_share": 0.45 + target * 0.15,
                "top_outflow_destination_share": 0.35 + target * 0.2,
                "stability_history_status": "sufficient_history",
                "income_stability_score": 0.78 - target * 0.2,
                "cash_flow_stability_score": 0.75 - target * 0.18,
                "seasonality_status": "insufficient_history",
                "cash_flow_forecast_status": "forecast_available",
                "cash_flow_forecast_method": "DETERMINISTIC_DEMO_FIXTURE",
                "cash_flow_forecast_history_months": 6 + (index % 10),
                "cash_flow_forecast_p10": net * 0.65,
                "cash_flow_forecast_p50": net,
                "cash_flow_forecast_p90": net * 1.25,
            }
        )
    pd.DataFrame(rows).to_csv(FEATURES_PATH, index=False)


def write_metadata(mode: str) -> None:
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bootstrap_mode": mode,
        "dataset_version": "pkdd-local" if mode == "pkdd" else "deterministic-demo-fixture-v1",
        "model_version": "historical-risk-v1",
        "feature_schema_version": "nadi-feature-schema-v1",
        "policy_versions": {
            "decision": "decision-policy-v1",
            "evidence_confidence": "evidence-confidence-v1",
            "evidence_ladder": "evidence-ladder-v2",
            "stress": "stress-policy-v1",
            "repayment_envelope": "repayment-envelope-v1",
            "behavioral_risk": "behavioral-risk-v1",
        },
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def create_demo_admin() -> None:
    if os.getenv("BOOTSTRAP_CREATE_ADMIN", "true").lower() not in {"1", "true", "yes"}:
        return
    run_step(
        [
            "scripts/create_admin.py",
            "--name",
            os.getenv("BOOTSTRAP_ADMIN_NAME", "NADI Admin"),
            "--email",
            os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com"),
            "--password",
            os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin-pass-1"),
        ]
    )


def main() -> None:
    run_step(["scripts/init_app_db.py"])
    raw_dir = raw_pkdd_dir()
    if raw_dir is not None:
        mode = "pkdd"
        run_step(["scripts/prepare_pkdd.py", "--raw-dir", str(raw_dir)])
        run_step(["scripts/init_db.py"])
        run_step(["scripts/import_pkdd.py"])
        run_step(["scripts/build_nadi_base_features.py"])
        run_step(["scripts/build_nadi_features.py"])
        run_step(["scripts/add_loan_target.py"])
        run_step(["scripts/add_stability_seasonality.py"])
    else:
        mode = "fallback"
        write_fallback_features()
    run_step(["scripts/train_risk_model.py"])
    run_step(["scripts/add_evidence_confidence.py"])
    if mode == "pkdd":
        run_step(["scripts/add_cash_flow_forecast.py"])
    run_step(["scripts/add_stress_simulation.py"])
    run_step(["scripts/add_repayment_envelope.py"])
    run_step(["scripts/add_decisions.py"])
    run_step(["scripts/add_evidence_ladder.py"])
    run_step(["scripts/add_adaptive_credit_path.py"])
    run_step(["scripts/add_explanations.py"])
    run_step(["scripts/evaluate_policies.py"])
    write_metadata(mode)
    create_demo_admin()
    print(f"Bootstrap complete using {mode} data. Metadata: {METADATA_PATH}")


if __name__ == "__main__":
    main()
