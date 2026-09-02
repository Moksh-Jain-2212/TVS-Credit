from __future__ import annotations

from app.models import AlternativeSourceType, BorrowerSegment, LoanApplication
from app.services.alternative_data.registry import get_adapter
from app.services.alternative_data.synthetic_evidence_generator import generated_mock_payload


def application(segment: BorrowerSegment, application_id: int = 17) -> LoanApplication:
    return LoanApplication(id=application_id, borrower_segment=segment, declared_monthly_income=30_000)


def test_generated_gst_and_telecom_payloads_are_deterministic_and_normalizable() -> None:
    app = application(BorrowerSegment.SMALL_MERCHANT)
    for source in (AlternativeSourceType.GST, AlternativeSourceType.TELECOM):
        first = generated_mock_payload(app, source)
        second = generated_mock_payload(app, source)
        assert first == second
        assert first is not None
        payload, provenance = first
        normalized = get_adapter(source).normalize(payload)
        assert normalized.source_type == source
        assert len(payload["records"]) >= 12
        assert provenance["evidence_origin"] == "PARAMETERIZED_SYNTHETIC_DEMO"
        assert provenance["borrower_segment"] == BorrowerSegment.SMALL_MERCHANT.value


def test_generated_evidence_is_segment_conditioned() -> None:
    merchant_payload, _ = generated_mock_payload(application(BorrowerSegment.SMALL_MERCHANT), AlternativeSourceType.GST) or ({}, {})
    salaried_payload, _ = generated_mock_payload(application(BorrowerSegment.SALARIED), AlternativeSourceType.GST) or ({}, {})
    merchant_turnover = sum(record["turnover"] for record in merchant_payload["records"])
    salaried_turnover = sum(record["turnover"] for record in salaried_payload["records"])
    assert merchant_turnover > salaried_turnover
