"""Pruebas unitarias de la construccion de features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml_factory.features import FeatureBuilder


def sample_data(rows: int = 40) -> pd.DataFrame:
    """Crea una serie sintetica con las columnas reales del modelo."""
    dates = pd.date_range("2025-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "product_id": ["P-1"] * rows,
            "warehouse_id": ["W-1"] * rows,
            "date": dates,
            "daily_demand": np.arange(1, rows + 1, dtype=float),
            "units_sold": np.arange(1, rows + 1, dtype=float),
            "current_stock": np.full(rows, 100.0),
            "reorder_level": np.full(rows, 20.0),
            "safety_stock": np.full(rows, 10.0),
            "inventory_turnover": np.full(rows, 2.0),
            "stockout_risk": np.zeros(rows),
            "overstock_risk": np.zeros(rows),
            "predicted_reorder_quantity": np.full(rows, 5.0),
            "product_category": ["category-a"] * rows,
            "brand": ["brand-a"] * rows,
        }
    )


def test_full_dataset_has_expected_features_without_nulls() -> None:
    """El dataset final debe ser numerico y no contener nulos."""
    builder = FeatureBuilder()
    features, target = builder.build_full_dataset(sample_data(), target_type="stockout")

    expected = {
        "daily_demand_lag_7",
        "daily_demand_lag_14",
        "daily_demand_lag_30",
        "daily_demand_rolling_mean_7",
        "daily_demand_rolling_mean_30",
        "month_feature",
        "quarter_feature",
        "day_of_week",
        "is_holiday",
        "inventory_turnover_ratio",
        "stock_coverage_days",
        "remaining_inventory_days",
    }
    assert expected.issubset(features.columns)
    assert features.select_dtypes(exclude="number").empty
    assert not features.isna().any().any()
    assert not target.isna().any()


def test_reorder_target_uses_existing_column() -> None:
    """El target reorder debe respetar predicted_reorder_quantity."""
    builder = FeatureBuilder()
    result = builder.create_target(sample_data(), target_type="reorder")

    assert result["target"].equals(result["predicted_reorder_quantity"])
