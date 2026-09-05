"""Reusable denoising neural-network contributor for NADI risk ensembles."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPRegressor


class DenoisingAutoencoderRiskClassifier(BaseEstimator, ClassifierMixin):
    """Learns a denoised representation before fitting a risk classifier."""

    def __init__(self, hidden_units: int = 24, noise_std: float = 0.03, random_state: int = 42) -> None:
        self.hidden_units = hidden_units
        self.noise_std = noise_std
        self.random_state = random_state

    def fit(self, X: Any, y: Any) -> "DenoisingAutoencoderRiskClassifier":
        clean = np.asarray(X, dtype=float)
        rng = np.random.default_rng(self.random_state)
        noisy = clean + rng.normal(0.0, self.noise_std, size=clean.shape)
        self.autoencoder_ = MLPRegressor(
            hidden_layer_sizes=(self.hidden_units,), max_iter=400, early_stopping=False,
            random_state=self.random_state,
        ).fit(noisy, clean)
        encoded = self.autoencoder_.predict(clean)
        self.classifier_ = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=self.random_state)
        self.classifier_.fit(encoded, y)
        self.classes_ = self.classifier_.classes_
        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        return self.classifier_.predict_proba(self.autoencoder_.predict(np.asarray(X, dtype=float)))

    def predict(self, X: Any) -> np.ndarray:
        return self.classifier_.predict(self.autoencoder_.predict(np.asarray(X, dtype=float)))
