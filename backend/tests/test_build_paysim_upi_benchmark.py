from __future__ import annotations

from pathlib import Path

from scripts.build_paysim_upi_benchmark import build_profiles


def test_build_profiles_uses_aggregate_fields_and_hides_source_identifiers(tmp_path: Path) -> None:
    csv_path = tmp_path / "paysim.csv"
    csv_path.write_text(
        "step,type,amount,nameOrig,oldbalanceOrg,newbalanceOrig,nameDest,oldbalanceDest,newbalanceDest,isFraud,isFlaggedFraud\n"
        "1,PAYMENT,100,C100,500,400,M200,0,0,0,0\n"
        "2,TRANSFER,200,C100,400,200,C300,0,200,0,0\n"
        "3,CASH_IN,300,C300,100,400,C100,200,500,0,0\n",
        encoding="utf-8",
    )

    frame = build_profiles(csv_path, sample_modulus=1, max_profiles=10, min_transactions=1, chunksize=2)

    assert not frame.empty
    assert "benchmark_profile_id" in frame
    assert "nameOrig" not in frame
    assert "nameDest" not in frame
    assert "isFraud" not in frame
    assert set(frame["benchmark_origin"]) == {"PAYSIM_SYNTHETIC_UPI_LIKE"}
    assert (frame["merchant_payment_ratio"] >= 0).all()
