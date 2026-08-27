from pathlib import Path

import pytest

from scripts.profile_pkdd import profile_pkdd


def write_pkdd_file(raw_dir: Path, file_name: str, content: str) -> None:
    (raw_dir / file_name).write_text(content, encoding="utf-8")


def test_profile_pkdd_writes_schema_report(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "pkdd"
    raw_dir.mkdir(parents=True)
    output_doc = tmp_path / "docs" / "pkdd_schema.md"

    write_pkdd_file(
        raw_dir,
        "account.asc",
        '"account_id";"district_id";"frequency";"date"\n1;10;"POPLATEK MESICNE";930101\n',
    )
    write_pkdd_file(
        raw_dir,
        "card.asc",
        '"card_id";"disp_id";"type";"issued"\n5;7;"classic";931107 00:00:00\n',
    )
    write_pkdd_file(
        raw_dir,
        "client.asc",
        '"client_id";"birth_number";"district_id"\n3;"706213";10\n',
    )
    write_pkdd_file(
        raw_dir,
        "disp.asc",
        '"disp_id";"client_id";"account_id";"type"\n7;3;1;"OWNER"\n',
    )
    write_pkdd_file(
        raw_dir,
        "district.asc",
        "A1;A2;A3\n10;\"Prague\";\"Prague\"\n",
    )
    write_pkdd_file(
        raw_dir,
        "loan.asc",
        '"loan_id";"account_id";"date";"amount";"duration";"payments";"status"\n'
        '11;1;930705;96396;12;8033.00;"B"\n',
    )
    write_pkdd_file(
        raw_dir,
        "order.asc",
        '"order_id";"account_id";"bank_to";"account_to";"amount";"k_symbol"\n'
        '13;1;"YZ";"87144583";2452.00;"SIPO"\n',
    )
    write_pkdd_file(
        raw_dir,
        "trans.asc",
        '"trans_id";"account_id";"date";"type";"operation";"amount";"balance";"k_symbol";"bank";"account"\n'
        '17;1;930101;"PRIJEM";"VKLAD";700.00;700.00;"";;\n',
    )

    profiles = profile_pkdd(raw_dir, output_doc)

    report = output_doc.read_text(encoding="utf-8")
    assert len(profiles) == 8
    assert "account_id" in report
    assert "disp.account_id -> account.account_id" in report
    assert "YYMMDD" in report


def test_profile_pkdd_fails_when_expected_file_missing(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "pkdd"
    raw_dir.mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        profile_pkdd(raw_dir, tmp_path / "docs" / "pkdd_schema.md")
