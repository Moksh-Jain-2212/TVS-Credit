from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from app.services.risk_model_service import RiskModelService


class ConstantModel:
    def predict_proba(self, frame):
        return np.array([[0.8, 0.2] for _ in range(len(frame))])


def test_risk_model_service_caches_metadata_and_validates_schema(tmp_path) -> None:
    model_path = tmp_path / "model.joblib"
    joblib.dump(
        {
            "model": ConstantModel(),
            "model_name": "constant",
            "model_version": "unit-risk-v1",
            "feature_schema_version": "unit-schema-v1",
            "feature_columns": ["income", "outflow"],
        },
        model_path,
    )
    service = RiskModelService(model_path)
    metadata = service.metadata()
    assert metadata.available is True
    assert metadata.model_version == "unit-risk-v1"
    prediction = service.predict(pd.Series({"income": 100, "outflow": 50}))
    assert prediction is not None
    assert prediction.probability == 0.2

    try:
        service.predict(pd.Series({"income": 100}))
    except ValueError as exc:
        assert "Missing risk model features" in str(exc)
    else:
        raise AssertionError("Missing model features should fail")
