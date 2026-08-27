from pathlib import Path

import pandas as pd
import pytest

from scripts.add_loan_target import add_loan_target


def write_features(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "loan_id,mean_monthly_inflow\n"
        "1,1000.0\n"
        "2,900.0\n"
        "3,800.0\n"
        "4,700.0\n",
        encoding="utf-8",
    )


def write_loans(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "loan_id,account_id,loan_date,amount,duration,payments,status\n"
        "1,10,1993-01-01,1000,12,100.0,A\n"
        "2,11,1993-01-01,1000,12,100.0,B\n"
        "3,12,1993-01-01,1000,12,100.0,C\n"
        "4,13,1993-01-01,1000,12,100.0,D\n",
        encoding="utf-8",
    )


def test_add_loan_target_marks_known_outcomes_and_excludes_running(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    loans_path = tmp_path / "loans.csv"
    doc_path = tmp_path / "loan_target_definition.md"
    write_features(features_path)
    write_loans(loans_path)

    frame = add_loan_target(features_path, loans_path, features_path, doc_path)
    written = pd.read_csv(features_path)
    doc = doc_path.read_text(encoding="utf-8")

    assert len(frame) == 4
    assert written.loc[written["loan_id"] == 1, "repayment_default_target"].iloc[0] == 0
    assert written.loc[written["loan_id"] == 2, "repayment_default_target"].iloc[0] == 1
    assert written.loc[written["loan_id"] == 3, "repayment_outcome_known"].iloc[0] == False
    assert pd.isna(written.loc[written["loan_id"] == 4, "repayment_default_target"].iloc[0])
    assert "Included observations: 2" in doc
    assert "Excluded observations: 2" in doc


def test_add_loan_target_rejects_unknown_status(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    loans_path = tmp_path / "loans.csv"
    write_features(features_path)
    write_loans(loans_path)
    text = loans_path.read_text(encoding="utf-8").replace(",D\n", ",Z\n")
    loans_path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown loan status"):
        add_loan_target(features_path, loans_path, features_path, tmp_path / "doc.md")


def test_add_loan_target_can_be_rerun_on_targeted_features(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    loans_path = tmp_path / "loans.csv"
    doc_path = tmp_path / "loan_target_definition.md"
    write_features(features_path)
    write_loans(loans_path)

    add_loan_target(features_path, loans_path, features_path, doc_path)
    frame = add_loan_target(features_path, loans_path, features_path, doc_path)

    assert len(frame) == 4
    assert "loan_status_from_source" in frame.columns
    assert not any(column.endswith("_x") or column.endswith("_y") for column in frame.columns)
