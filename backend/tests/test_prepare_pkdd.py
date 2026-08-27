import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.prepare_pkdd import prepare_pkdd


def write_core_raw_files(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True)
    (raw_dir / "account.asc").write_text(
        '"account_id";"district_id";"frequency";"date"\n'
        '1;10;"POPLATEK MESICNE";930101\n',
        encoding="ascii",
    )
    (raw_dir / "trans.asc").write_text(
        '"trans_id";"account_id";"date";"type";"operation";"amount";"balance";"k_symbol";"bank";"account"\n'
        '17;1;930102;"PRIJEM";"VKLAD";700.00;700.00;"";;\n',
        encoding="ascii",
    )
    (raw_dir / "loan.asc").write_text(
        '"loan_id";"account_id";"date";"amount";"duration";"payments";"status"\n'
        '11;1;930705;96396;12;8033.00;"B"\n',
        encoding="ascii",
    )
    (raw_dir / "client.asc").write_text(
        '"client_id";"birth_number";"district_id"\n3;"706213";10\n',
        encoding="ascii",
    )
    (raw_dir / "disp.asc").write_text(
        '"disp_id";"client_id";"account_id";"type"\n7;3;1;"OWNER"\n',
        encoding="ascii",
    )
    (raw_dir / "order.asc").write_text(
        '"order_id";"account_id";"bank_to";"account_to";"amount";"k_symbol"\n'
        '13;1;"YZ";"87144583";2452.00;"SIPO"\n',
        encoding="ascii",
    )


def test_prepare_pkdd_writes_clean_csvs_and_quality_report(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "pkdd"
    output_dir = tmp_path / "processed" / "pkdd"
    write_core_raw_files(raw_dir)

    prepared_tables = prepare_pkdd(raw_dir, output_dir)

    assert {table.output_path.name for table in prepared_tables} == {
        "accounts.csv",
        "transactions.csv",
        "loans.csv",
        "clients.csv",
        "dispositions.csv",
        "orders.csv",
    }

    accounts = pd.read_csv(output_dir / "accounts.csv")
    transactions = pd.read_csv(output_dir / "transactions.csv")
    loans = pd.read_csv(output_dir / "loans.csv")
    report = json.loads((output_dir / "quality_report.json").read_text(encoding="utf-8"))

    assert accounts.loc[0, "account_open_date"] == "1993-01-01"
    assert transactions.loc[0, "transaction_date"] == "1993-01-02"
    assert loans.loc[0, "loan_date"] == "1993-07-05"
    assert report["tables"]["trans"]["missing_values"]["bank"] == 1
    assert report["relationships"][0]["orphan_rows"] == 0


def test_prepare_pkdd_rejects_duplicate_primary_keys(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "pkdd"
    output_dir = tmp_path / "processed" / "pkdd"
    write_core_raw_files(raw_dir)
    (raw_dir / "account.asc").write_text(
        '"account_id";"district_id";"frequency";"date"\n'
        '1;10;"POPLATEK MESICNE";930101\n'
        '1;10;"POPLATEK MESICNE";930102\n',
        encoding="ascii",
    )

    with pytest.raises(ValueError, match="duplicate account_id"):
        prepare_pkdd(raw_dir, output_dir)


def test_prepare_pkdd_rejects_orphan_relationships(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "pkdd"
    output_dir = tmp_path / "processed" / "pkdd"
    write_core_raw_files(raw_dir)
    (raw_dir / "loan.asc").write_text(
        '"loan_id";"account_id";"date";"amount";"duration";"payments";"status"\n'
        '11;99;930705;96396;12;8033.00;"B"\n',
        encoding="ascii",
    )

    with pytest.raises(ValueError, match="loan.account_id"):
        prepare_pkdd(raw_dir, output_dir)
