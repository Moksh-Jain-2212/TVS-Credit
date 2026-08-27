from pathlib import Path

from sqlalchemy import func, select

from app.core.database import create_session_factory, create_sqlite_engine
from app.models import Account, Client, Disposition, Loan, StandingOrder, Transaction
from scripts.import_pkdd import import_pkdd, validate_import
from scripts.init_db import init_db


def write_processed_csvs(processed_dir: Path) -> None:
    processed_dir.mkdir(parents=True)
    (processed_dir / "accounts.csv").write_text(
        "account_id,district_id,frequency,account_open_date\n"
        "1,10,POPLATEK MESICNE,1993-01-01\n",
        encoding="utf-8",
    )
    (processed_dir / "clients.csv").write_text(
        "client_id,birth_number,district_id\n"
        "3,706213,10\n",
        encoding="utf-8",
    )
    (processed_dir / "dispositions.csv").write_text(
        "disp_id,client_id,account_id,type\n"
        "7,3,1,OWNER\n",
        encoding="utf-8",
    )
    (processed_dir / "loans.csv").write_text(
        "loan_id,account_id,loan_date,amount,duration,payments,status\n"
        "11,1,1993-07-05,96396,12,8033.0,B\n",
        encoding="utf-8",
    )
    (processed_dir / "orders.csv").write_text(
        "order_id,account_id,bank_to,account_to,amount,k_symbol\n"
        "13,1,YZ,87144583,2452.0,SIPO\n",
        encoding="utf-8",
    )
    (processed_dir / "transactions.csv").write_text(
        "trans_id,account_id,transaction_date,type,operation,amount,balance,k_symbol,bank,account\n"
        "17,1,1993-01-02,PRIJEM,VKLAD,700.0,700.0,,,\n",
        encoding="utf-8",
    )


def test_init_db_creates_pkdd_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "nadi.db"

    init_db(db_path)

    engine = create_sqlite_engine(db_path)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Account)) == 0


def test_import_pkdd_loads_cleaned_csvs_and_validates_joins(tmp_path: Path) -> None:
    processed_dir = tmp_path / "processed" / "pkdd"
    db_path = tmp_path / "nadi.db"
    write_processed_csvs(processed_dir)

    result = import_pkdd(processed_dir, db_path)

    assert result["imported_counts"]["accounts.csv"] == 1
    assert result["validation"]["joins"]["account_transaction_rows"] == 1
    assert result["validation"]["joins"]["account_loan_rows"] == 1
    assert result["validation"]["joins"]["client_disposition_account_rows"] == 1

    engine = create_sqlite_engine(db_path)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        assert session.get(Account, 1) is not None
        assert session.get(Client, 3) is not None
        assert session.get(Disposition, 7) is not None
        assert session.get(Loan, 11) is not None
        assert session.get(StandingOrder, 13) is not None
        assert session.get(Transaction, 17).counterparty_account is None
        assert validate_import(session, processed_dir)["foreign_keys"] == {
            "transactions_without_account": 0,
            "loans_without_account": 0,
            "orders_without_account": 0,
            "dispositions_without_account": 0,
            "dispositions_without_client": 0,
        }
