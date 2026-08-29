"""Cached serving layer for the historical repayment-risk model."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


MODEL_PATH = Path(__file__).resolve().parents[3] / "models" / "repayment_risk_model.joblib"
DEFAULT_MODEL_VERSION = "historical-risk-v1"


@dataclass(frozen=True)
class RiskModelMetadata:
    available: bool
    model_path: str
    model_name: str | None = None
    model_version: str | None = None
    feature_schema_version: str | None = None
    feature_columns: list[str] | None = None
    reason: str | None = None


@dataclass(frozen=True)
class RiskModelPrediction:
    probability: float
    model_version: str
    feature_schema_version: str
    model_name: str | None


class RiskModelService:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model_path = model_path

    @lru_cache(maxsize=1)
    def _artifact(self) -> dict[str, Any] | None:
        if not self.model_path.exists():
            return None
        artifact = joblib.load(self.model_path)
        if not isinstance(artifact, dict) or "model" not in artifact or "feature_columns" not in artifact:
            raise ValueError("Risk model artifact is incompatible")
        columns = artifact["feature_columns"]
        if not isinstance(columns, list) or not columns:
            raise ValueError("Risk model artifact has no feature schema")
        return artifact

    def metadata(self) -> RiskModelMetadata:
        try:
            artifact = self._artifact()
        except ValueError as exc:
            return RiskModelMetadata(available=False, model_path=str(self.model_path), reason=str(exc))
        if artifact is None:
            return RiskModelMetadata(available=False, model_path=str(self.model_path), reason="model artifact missing")
        return RiskModelMetadata(
            available=True,
            model_path=str(self.model_path),
            model_name=str(artifact.get("model_name")) if artifact.get("model_name") else None,
            model_version=str(artifact.get("model_version", DEFAULT_MODEL_VERSION)),
            feature_schema_version=str(artifact.get("feature_schema_version", "nadi-feature-schema-v1")),
            feature_columns=list(artifact["feature_columns"]),
        )

    def health(self) -> dict[str, Any]:
        metadata = self.metadata()
        return {
            "available": metadata.available,
            "model_version": metadata.model_version,
            "feature_schema_version": metadata.feature_schema_version,
            "reason": metadata.reason,
        }

    def predict(self, row: pd.Series) -> RiskModelPrediction | None:
        artifact = self._artifact()
        if artifact is None:
            return None
        columns = list(artifact["feature_columns"])
        missing = [column for column in columns if column not in row.index]
        if missing:
            raise ValueError(f"Missing risk model features: {missing[:8]}")
        frame = pd.DataFrame([{column: row.get(column) for column in columns}])
        probability = artifact["model"].predict_proba(frame)[:, 1][0]
        return RiskModelPrediction(
            probability=float(probability),
            model_version=str(artifact.get("model_version", DEFAULT_MODEL_VERSION)),
            feature_schema_version=str(artifact.get("feature_schema_version", "nadi-feature-schema-v1")),
            model_name=str(artifact.get("model_name")) if artifact.get("model_name") else None,
        )


risk_model_service = RiskModelService()

