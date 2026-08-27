"""Prepare clean CSV copies of the core PKDD source files."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


CORE_TABLES = {
    "account": {
        "source_file": "account.asc",
        "output_file": "accounts.csv",
        "primary_key": "account_id",
        "columns": ("account_id", "district_id", "frequency", "date"),
        "int_columns": ("account_id", "district_id"),
        "float_columns": (),
        "date_columns": {"date": "account_open_date"},
    },
    "trans": {
        "source_file": "trans.asc",
        "output_file": "transactions.csv",
        "primary_key": "trans_id",
        "columns": (
            "trans_id",
            "account_id",
            "date",
            "type",
            "operation",
            "amount",
            "balance",
            "k_symbol",
            "bank",
            "account",
        ),
        "int_columns": ("trans_id", "account_id"),
        "float_columns": ("amount", "balance"),
        "date_columns": {"date": "transaction_date"},
    },
    "loan": {
        "source_file": "loan.asc",
        "output_file": "loans.csv",
        "primary_key": "loan_id",
        "columns": ("loan_id", "account_id", "date", "amount", "duration", "payments", "status"),
        "int_columns": ("loan_id", "account_id", "amount", "duration"),
        "float_columns": ("payments",),
        "date_columns": {"date": "loan_date"},
    },
    "client": {
        "source_file": "client.asc",
        "output_file": "clients.csv",
        "primary_key": "client_id",
        "columns": ("client_id", "birth_number", "district_id"),
        "int_columns": ("client_id", "district_id"),
        "float_columns": (),
        "date_columns": {},
    },
    "disp": {
        "source_file": "disp.asc",
        "output_file": "dispositions.csv",
        "primary_key": "disp_id",
        "columns": ("disp_id", "client_id", "account_id", "type"),
        "int_columns": ("disp_id", "client_id", "account_id"),
        "float_columns": (),
        "date_columns": {},
    },
    "order": {
        "source_file": "order.asc",
        "output_file": "orders.csv",
        "primary_key": "order_id",
        "columns": ("order_id", "account_id", "bank_to", "account_to", "amount", "k_symbol"),
        "int_columns": ("order_id", "account_id"),
        "float_columns": ("amount",),
        "date_columns": {},
    },
}

RELATIONSHIPS = (
    ("trans", "account_id", "account", "account_id"),
    ("loan", "account_id", "account", "account_id"),
    ("order", "account_id", "account", "account_id"),
    ("disp", "account_id", "account", "account_id"),
    ("disp", "client_id", "client", "client_id"),
)


@dataclass(frozen=True)
class PreparedTable:
    name: str
    output_path: Path
    row_count: int
    duplicate_primary_keys: int
    missing_values: dict[str, int]


def read_raw_table(raw_dir: Path, table_name: str) -> pd.DataFrame:
    config = CORE_TABLES[table_name]
    path = raw_dir / str(config["source_file"])
    if not path.exists():
        raise FileNotFoundError(f"Missing raw PKDD file: {path}")

    frame = pd.read_csv(
        path,
        sep=";",
        quotechar='"',
        encoding="ascii",
        dtype=str,
        keep_default_na=False,
    )
    expected_columns = list(config["columns"])
    if list(frame.columns) != expected_columns:
        raise ValueError(
            f"{path.name} columns do not match expected schema: {list(frame.columns)}"
        )
    return frame


def normalize_empty_strings(frame: pd.DataFrame) -> pd.DataFrame:
    cleaned = frame.copy()
    for column in cleaned.columns:
        cleaned[column] = cleaned[column].astype(str).str.strip()
        cleaned[column] = cleaned[column].replace("", pd.NA)
    return cleaned


def parse_yymmdd(values: pd.Series, column: str) -> pd.Series:
    parsed = pd.to_datetime(values, format="%y%m%d", errors="coerce")
    invalid_count = int(parsed.isna().sum())
    if invalid_count:
        raise ValueError(f"{column} contains {invalid_count} invalid YYMMDD date values")
    return parsed.dt.strftime("%Y-%m-%d")


def convert_numeric(frame: pd.DataFrame, columns: tuple[str, ...], kind: str) -> None:
    for column in columns:
        converted = pd.to_numeric(frame[column], errors="coerce")
        invalid_count = int(converted.isna().sum())
        if invalid_count:
            raise ValueError(f"{column} contains {invalid_count} invalid numeric values")
        if kind == "int":
            frame[column] = converted.astype("Int64")
        else:
            frame[column] = converted.astype(float)


def clean_table(raw_frame: pd.DataFrame, table_name: str) -> pd.DataFrame:
    config = CORE_TABLES[table_name]
    frame = normalize_empty_strings(raw_frame)

    for source_column, output_column in dict(config["date_columns"]).items():
        frame[output_column] = parse_yymmdd(frame[source_column], source_column)
        frame = frame.drop(columns=[source_column])

    convert_numeric(frame, tuple(config["int_columns"]), "int")
    convert_numeric(frame, tuple(config["float_columns"]), "float")

    output_columns = [
        dict(config["date_columns"]).get(column, column) for column in config["columns"]
    ]
    return frame[output_columns]


def missing_counts(frame: pd.DataFrame) -> dict[str, int]:
    return {column: int(frame[column].isna().sum()) for column in frame.columns}


def validate_table(frame: pd.DataFrame, table_name: str, raw_row_count: int) -> PreparedTable:
    config = CORE_TABLES[table_name]
    primary_key = str(config["primary_key"])
    if len(frame) != raw_row_count:
        raise ValueError(f"{table_name} row count changed during preparation")
    duplicate_primary_keys = int(frame[primary_key].duplicated().sum())
    if duplicate_primary_keys:
        raise ValueError(f"{table_name} has {duplicate_primary_keys} duplicate {primary_key} values")
    return PreparedTable(
        name=table_name,
        output_path=Path(str(config["output_file"])),
        row_count=len(frame),
        duplicate_primary_keys=duplicate_primary_keys,
        missing_values=missing_counts(frame),
    )


def validate_relationships(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for child_table, child_column, parent_table, parent_column in RELATIONSHIPS:
        child = tables[child_table]
        parent = tables[parent_table]
        child_values = child[child_column].dropna().astype("Int64")
        parent_values = set(parent[parent_column].dropna().astype("Int64"))
        orphan_rows = int((~child_values.isin(parent_values)).sum())
        if orphan_rows:
            raise ValueError(
                f"{child_table}.{child_column} has {orphan_rows} rows without "
                f"{parent_table}.{parent_column}"
            )
        results.append(
            {
                "relationship": f"{child_table}.{child_column} -> {parent_table}.{parent_column}",
                "child_rows_checked": int(len(child_values)),
                "orphan_rows": orphan_rows,
            }
        )
    return results


def write_quality_report(
    output_dir: Path,
    prepared_tables: list[PreparedTable],
    relationships: list[dict[str, Any]],
) -> Path:
    report = {
        "tables": {
            table.name: {
                "output_file": table.output_path.name,
                "row_count": table.row_count,
                "duplicate_primary_keys": table.duplicate_primary_keys,
                "missing_values": table.missing_values,
            }
            for table in prepared_tables
        },
        "relationships": relationships,
    }
    report_path = output_dir / "quality_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def prepare_pkdd(raw_dir: Path, output_dir: Path) -> list[PreparedTable]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned_tables: dict[str, pd.DataFrame] = {}
    prepared_tables: list[PreparedTable] = []

    for table_name in CORE_TABLES:
        raw_frame = read_raw_table(raw_dir, table_name)
        clean_frame = clean_table(raw_frame, table_name)
        prepared = validate_table(clean_frame, table_name, len(raw_frame))

        output_path = output_dir / prepared.output_path
        clean_frame.to_csv(output_path, index=False, encoding="utf-8")
        cleaned_tables[table_name] = clean_frame
        prepared_tables.append(
            PreparedTable(
                name=prepared.name,
                output_path=output_path,
                row_count=prepared.row_count,
                duplicate_primary_keys=prepared.duplicate_primary_keys,
                missing_values=prepared.missing_values,
            )
        )

    relationships = validate_relationships(cleaned_tables)
    write_quality_report(output_dir, prepared_tables, relationships)
    return prepared_tables


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/pkdd"),
        help="Directory containing raw PKDD .asc files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/pkdd"),
        help="Directory where cleaned CSV files will be written.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepared_tables = prepare_pkdd(args.raw_dir, args.output_dir)
    print(f"Prepared {len(prepared_tables)} PKDD tables in {args.output_dir}.")
    for table in prepared_tables:
        print(f"- {table.output_path.name}: {table.row_count} rows")
    print(f"- quality_report.json: validation summary")


if __name__ == "__main__":
    main()
