"""Hygron inference helper for the Python/Streamlit digital twin.

Input must be a one-row DataFrame of PRECOMPUTED historical features.
It does not calculate rolling windows or consume raw sensor readings.
Models use simulated VTT-derived labels, not observed mold.
"""
from pathlib import Path
import json
import joblib
import pandas as pd

RISK_DISPLAY = {
    "Low": {"label": "Low", "color": "green", "description": "Lower modeled mold-growth risk"},
    "Medium": {"label": "Medium", "color": "amber", "description": "Moderate modeled mold-growth risk"},
    "High": {"label": "High", "color": "red", "description": "Higher modeled mold-growth risk"},
}


def load_models(model_dir="models"):
    folder = Path(model_dir)
    with (folder / "model_metadata.json").open(encoding="utf-8") as handle:
        meta = json.load(handle)
    # Do not load model files from untrusted sources.
    now = joblib.load(folder / "current_risk_rf.joblib")
    future = joblib.load(folder / "forecast_24h_rf.joblib")
    return now, future, meta


def estimate_risk(latest_features: pd.DataFrame, models):
    """Return current and 24-hour-ahead risk for one room's latest feature row.

    Compute the rolling features for each room beforehand using at least 60 days
    of valid history. Reject incomplete features instead of fabricating a risk.
    """
    now, future, meta = models
    required = meta["selected_features"]
    if len(latest_features) != 1:
        raise ValueError("Pass exactly one latest feature row for one room")
    missing = [name for name in required if name not in latest_features.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")
    X = latest_features.loc[:, required]
    if not X.notna().all().all():
        raise ValueError("Incomplete history or invalid calculated features")

    classes = meta["label_classes_encoded_order"]
    current_class = classes[int(now.predict(X)[0])]
    future_class = classes[int(future.predict(X)[0])]
    return {
        "current_risk": current_class,
        "forecast_24h_risk": future_class,
        "current_indicator": RISK_DISPLAY[current_class],
        "forecast_indicator": RISK_DISPLAY[future_class],
        "risk_change_predicted": current_class != future_class,
        "is_simulated_model": True,
    }
