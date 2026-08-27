"""Profile the raw PKDD `.asc` files and write a schema report."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


EXPECTED_FILES = (
    "account.asc",
    "card.asc",
    "client.asc",
    "disp.asc",
    "district.asc",
    "loan.asc",
    "order.asc",
    "trans.asc",
)

PRIMARY_KEYS = {
    "account": "account_id",
    "card": "card_id",
    "client": "client_id",
    "disp": "disp_id",
    "district": "A1",
    "loan": "loan_id",
    "order": "order_id",
    "trans": "trans_id",
}

FOREIGN_KEYS = (
    ("account", "district_id", "district", "A1"),
    ("client", "district_id", "district", "A1"),
    ("disp", "client_id", "client", "client_id"),
    ("disp", "account_id", "account", "account_id"),
    ("card", "disp_id", "disp", "disp_id"),
    ("loan", "account_id", "account", "account_id"),
    ("order", "account_id", "account", "account_id"),
    ("trans", "account_id", "account", "account_id"),
)

DATE_COLUMNS = {
    "account": ("date",),
    "card": ("issued",),
    "loan": ("date",),
    "trans": ("date",),
}


@dataclass(frozen=True)
class TableProfile:
    name: str
    path: Path
    encoding: str
    delimiter: str
    has_header: bool
    columns: list[str]
    row_count: int
    missing_values: dict[str, int]
    duplicate_primary_keys: int | None
    date_formats: dict[str, str]


def sniff_delimiter(path: Path, encoding: str) -> str:
    with path.open("r", encoding=encoding, newline="") as handle:
        sample = handle.read(4096)
    dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t")
    return dialect.delimiter


def detect_encoding(path: Path) -> str:
    for encoding in ("ascii", "utf-8", "cp1250", "latin-1"):
        try:
            path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        return encoding
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Could not decode {path}")


def table_name(file_name: str) -> str:
    return Path(file_name).stem


def read_table(path: Path, delimiter: str, encoding: str) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep=delimiter,
        quotechar='"',
        encoding=encoding,
        dtype=str,
        keep_default_na=False,
    )


def missing_counts(frame: pd.DataFrame) -> dict[str, int]:
    return {
        column: int(frame[column].astype(str).str.strip().eq("").sum())
        for column in frame.columns
    }


def infer_date_format(values: pd.Series) -> str:
    non_empty = values.astype(str).str.strip()
    non_empty = non_empty[non_empty != ""]
    if non_empty.empty:
        return "empty"

    sample = non_empty.head(100)
    if sample.str.fullmatch(r"\d{6}").all():
        parsed = pd.to_datetime(sample, format="%y%m%d", errors="coerce")
        return "YYMMDD" if parsed.notna().all() else "unparsed 6-digit values"
    if sample.str.fullmatch(r"\d{6} 00:00:00").all():
        parsed = pd.to_datetime(sample, format="%y%m%d %H:%M:%S", errors="coerce")
        return "YYMMDD HH:MM:SS" if parsed.notna().all() else "unparsed timestamp values"
    parsed = pd.to_datetime(sample, errors="coerce")
    return "mixed/unknown" if parsed.isna().any() else "pandas-parseable mixed format"


def profile_table(path: Path) -> tuple[TableProfile, pd.DataFrame]:
    encoding = detect_encoding(path)
    delimiter = sniff_delimiter(path, encoding)
    frame = read_table(path, delimiter, encoding)
    name = table_name(path.name)
    primary_key = PRIMARY_KEYS.get(name)
    duplicate_primary_keys = (
        int(frame[primary_key].duplicated().sum())
        if primary_key is not None and primary_key in frame.columns
        else None
    )
    date_formats = {
        column: infer_date_format(frame[column])
        for column in DATE_COLUMNS.get(name, ())
        if column in frame.columns
    }

    return (
        TableProfile(
            name=name,
            path=path,
            encoding=encoding,
            delimiter=delimiter,
            has_header=True,
            columns=list(frame.columns),
            row_count=len(frame),
            missing_values=missing_counts(frame),
            duplicate_primary_keys=duplicate_primary_keys,
            date_formats=date_formats,
        ),
        frame,
    )


def validate_relationships(tables: dict[str, pd.DataFrame]) -> list[dict[str, str | int]]:
    relationships: list[dict[str, str | int]] = []
    for child_table, child_column, parent_table, parent_column in FOREIGN_KEYS:
        if child_table not in tables or parent_table not in tables:
            continue
        child = tables[child_table]
        parent = tables[parent_table]
        if child_column not in child.columns or parent_column not in parent.columns:
            continue

        child_values = child[child_column].astype(str)
        parent_values = set(parent[parent_column].astype(str))
        non_empty = child_values[child_values.str.strip() != ""]
        orphan_count = int((~non_empty.isin(parent_values)).sum())
        relationships.append(
            {
                "relationship": f"{child_table}.{child_column} -> {parent_table}.{parent_column}",
                "child_rows_checked": int(len(non_empty)),
                "orphan_rows": orphan_count,
                "distinct_child_keys": int(non_empty.nunique()),
                "distinct_parent_keys": int(parent[parent_column].astype(str).nunique()),
            }
        )
    return relationships


def format_missing_values(missing_values: dict[str, int]) -> str:
    non_zero = {column: count for column, count in missing_values.items() if count > 0}
    if not non_zero:
        return "None detected"
    return ", ".join(f"{column}: {count}" for column, count in non_zero.items())


def markdown_table(headers: Iterable[str], rows: Iterable[Iterable[object]]) -> str:
    header_list = list(headers)
    lines = [
        "| " + " | ".join(header_list) + " |",
        "| " + " | ".join("---" for _ in header_list) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def build_markdown(profiles: list[TableProfile], relationships: list[dict[str, str | int]]) -> str:
    summary_rows = [
        (
            profile.name,
            profile.path.name,
            profile.row_count,
            repr(profile.delimiter),
            profile.encoding,
            "yes" if profile.has_header else "no",
            PRIMARY_KEYS.get(profile.name, "unknown"),
            profile.duplicate_primary_keys
            if profile.duplicate_primary_keys is not None
            else "not checked",
        )
        for profile in profiles
    ]

    lines = [
        "# PKDD Raw Dataset Schema",
        "",
        "Generated by `scripts/profile_pkdd.py` from files under `data/raw/pkdd/`.",
        "",
        "## File Summary",
        "",
        markdown_table(
            (
                "table",
                "file",
                "rows",
                "delimiter",
                "encoding",
                "header",
                "primary key",
                "duplicate primary keys",
            ),
            summary_rows,
        ),
        "",
        "## Table Details",
    ]

    for profile in profiles:
        lines.extend(
            [
                "",
                f"### {profile.name}",
                "",
                f"- Source file: `{profile.path.name}`",
                f"- Columns: {', '.join(f'`{column}`' for column in profile.columns)}",
                f"- Missing values: {format_missing_values(profile.missing_values)}",
            ]
        )
        if profile.date_formats:
            date_summary = ", ".join(
                f"`{column}`: {date_format}"
                for column, date_format in profile.date_formats.items()
            )
            lines.append(f"- Date formats: {date_summary}")
        else:
            lines.append("- Date formats: none detected in configured date columns")

    relationship_rows = [
        (
            item["relationship"],
            item["child_rows_checked"],
            item["distinct_child_keys"],
            item["distinct_parent_keys"],
            item["orphan_rows"],
        )
        for item in relationships
    ]
    lines.extend(
        [
            "",
            "## Relationship Checks",
            "",
            markdown_table(
                (
                    "relationship",
                    "child rows checked",
                    "distinct child keys",
                    "distinct parent keys",
                    "orphan rows",
                ),
                relationship_rows,
            ),
            "",
            "## Notes",
            "",
            "- Raw files are semicolon-delimited text with quoted string fields.",
            "- Empty quoted strings are reported as missing values.",
            "- `district.asc` uses `A1` as the district identifier.",
            "- Phase 1 profiles the source data only; no cleaning, feature engineering, or ML training is performed.",
        ]
    )
    return "\n".join(lines) + "\n"


def profile_pkdd(raw_dir: Path, output_doc: Path) -> list[TableProfile]:
    missing_files = [file_name for file_name in EXPECTED_FILES if not (raw_dir / file_name).exists()]
    if missing_files:
        missing = ", ".join(missing_files)
        raise FileNotFoundError(f"Missing expected PKDD files under {raw_dir}: {missing}")

    profiles: list[TableProfile] = []
    tables: dict[str, pd.DataFrame] = {}
    for file_name in EXPECTED_FILES:
        profile, frame = profile_table(raw_dir / file_name)
        profiles.append(profile)
        tables[profile.name] = frame

    relationships = validate_relationships(tables)
    output_doc.parent.mkdir(parents=True, exist_ok=True)
    output_doc.write_text(build_markdown(profiles, relationships), encoding="utf-8")
    return profiles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/pkdd"),
        help="Directory containing raw PKDD .asc files.",
    )
    parser.add_argument(
        "--output-doc",
        type=Path,
        default=Path("docs/pkdd_schema.md"),
        help="Markdown schema report to write.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profiles = profile_pkdd(args.raw_dir, args.output_doc)
    print(f"Profiled {len(profiles)} PKDD files.")
    print(f"Wrote {args.output_doc}.")


if __name__ == "__main__":
    main()
