"""Generacion de variables y targets para modelos de stock."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


class FeatureBuilder:
    """Construye features temporales, de estacionalidad y de inventario.

    Args:
        date_column: Columna temporal usada para ordenar y extraer calendario.
        group_columns: Claves que separan series de producto y almacen.
    """

    def __init__(
        self,
        date_column: str = "date",
        group_columns: tuple[str, ...] = ("product_id", "warehouse_id"),
    ) -> None:
        self.date_column = date_column
        self.group_columns = group_columns

    def _ordered(self, df: pd.DataFrame) -> pd.DataFrame:
        """Devuelve una copia ordenada sin modificar el DataFrame original."""
        result = df.copy()
        if self.date_column in result.columns:
            result[self.date_column] = pd.to_datetime(result[self.date_column], errors="coerce")
            sort_columns = [column for column in (*self.group_columns, self.date_column) if column in result.columns]
            if sort_columns:
                result = result.sort_values(sort_columns).reset_index(drop=True)
        return result

    def _grouped_shift(self, df: pd.DataFrame, col: str, periods: int) -> pd.Series:
        """Calcula un lag por serie, o globalmente cuando no hay claves."""
        if col not in df.columns:
            raise KeyError(f"La columna requerida no existe: {col}")
        groups = [column for column in self.group_columns if column in df.columns]
        if groups:
            return df.groupby(groups, dropna=False)[col].shift(periods)
        return df[col].shift(periods)

    def create_lag_features(
        self,
        df: pd.DataFrame,
        col: str,
        lags: Iterable[int] = (7, 14, 30),
    ) -> pd.DataFrame:
        """Crea retardos temporales por producto y almacen.

        Args:
            df: Datos ya cargados.
            col: Columna numerica a retardar.
            lags: Numero de observaciones de retardo.

        Returns:
            Copia con columnas ``{col}_lag_{lag}``.
        """
        result = self._ordered(df)
        for lag in lags:
            if lag < 1:
                raise ValueError("Los lags deben ser enteros positivos")
            result[f"{col}_lag_{lag}"] = self._grouped_shift(result, col, lag)
        return result

    def create_rolling_features(
        self,
        df: pd.DataFrame,
        col: str,
        windows: Iterable[int] = (7, 30),
    ) -> pd.DataFrame:
        """Crea medias moviles por producto y almacen."""
        result = self._ordered(df)
        for window in windows:
            if window < 1:
                raise ValueError("Las ventanas deben ser enteros positivos")
            groups = [column for column in self.group_columns if column in result.columns]
            if groups:
                result[f"{col}_rolling_mean_{window}"] = (
                    result.groupby(groups, dropna=False)[col]
                    .transform(lambda values: values.rolling(window, min_periods=1).mean())
                )
            else:
                result[f"{col}_rolling_mean_{window}"] = result[col].rolling(window, min_periods=1).mean()
        return result

    def create_seasonality_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Crea mes, trimestre, dia de semana y flag de festivos.

        El flag usa festivos proporcionados en ``holiday_dates`` cuando existe;
        no introduce un calendario externo que pueda cambiar entre ejecuciones.
        """
        result = self._ordered(df)
        if self.date_column not in result.columns:
            raise KeyError(f"Falta la columna temporal: {self.date_column}")
        dates = pd.to_datetime(result[self.date_column], errors="coerce")
        result["month_feature"] = dates.dt.month
        result["quarter_feature"] = dates.dt.quarter
        result["day_of_week"] = dates.dt.dayofweek
        if "holiday_dates" in result.columns:
            result["is_holiday"] = result["holiday_dates"].fillna(False).astype(int)
        elif "is_holiday" not in result.columns:
            result["is_holiday"] = 0
        return result

    def create_ratio_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Crea ratios de rotacion, cobertura y dias restantes.

        Las divisiones por cero se convierten en cero y no se generan columnas
        basadas en campos que no existan en la fuente.
        """
        result = df.copy()
        if "inventory_turnover" in result.columns:
            result["inventory_turnover_ratio"] = pd.to_numeric(result["inventory_turnover"], errors="coerce")
        if {"current_stock", "daily_demand"}.issubset(result.columns):
            demand = pd.to_numeric(result["daily_demand"], errors="coerce").replace(0, np.nan)
            result["stock_coverage_days"] = pd.to_numeric(result["current_stock"], errors="coerce").div(demand)
        if {"current_stock", "reorder_level"}.issubset(result.columns):
            result["remaining_inventory_days"] = (
                pd.to_numeric(result["current_stock"], errors="coerce")
                - pd.to_numeric(result["reorder_level"], errors="coerce")
            )
        return result

    def create_target(self, df: pd.DataFrame, target_type: str = "stockout") -> pd.DataFrame:
        """Añade el target de clasificación de stockout o regresion de reorder.

        Args:
            df: Dataset con columnas de inventario/ventas.
            target_type: ``stockout`` o ``reorder``.

        Returns:
            Copia con una columna ``target``.
        """
        result = df.copy()
        if target_type not in {"stockout", "reorder"}:
            raise ValueError("target_type debe ser 'stockout' o 'reorder'")
        if target_type == "stockout":
            if "stockout_risk" in result.columns:
                risk = pd.to_numeric(result["stockout_risk"], errors="coerce")
                result["target"] = (risk >= 50).astype(int)
            elif {"current_stock", "reorder_level"}.issubset(result.columns):
                result["target"] = (
                    pd.to_numeric(result["current_stock"], errors="coerce")
                    <= pd.to_numeric(result["reorder_level"], errors="coerce")
                ).astype(int)
            else:
                raise KeyError("stockout necesita stockout_risk o current_stock y reorder_level")
        elif "predicted_reorder_quantity" in result.columns:
            result["target"] = pd.to_numeric(result["predicted_reorder_quantity"], errors="coerce")
        elif {"reorder_level", "current_stock"}.issubset(result.columns):
            result["target"] = (
                pd.to_numeric(result["reorder_level"], errors="coerce")
                - pd.to_numeric(result["current_stock"], errors="coerce")
            ).clip(lower=0)
        else:
            raise KeyError("reorder necesita predicted_reorder_quantity o inventario suficiente")
        return result

    def build_full_dataset(
        self,
        df: pd.DataFrame,
        target_type: str = "stockout",
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Ejecuta la transformacion completa y devuelve ``X`` e ``y``.

        Las columnas identificadoras, fechas y target se excluyen de ``X``;
        categoricas se codifican con one-hot y los nulos numericos se imputan
        con la mediana de cada columna.
        """
        result = self._ordered(df)
        numeric_source = "daily_demand" if "daily_demand" in result.columns else "units_sold"
        if numeric_source not in result.columns:
            raise KeyError("Se necesita daily_demand o units_sold para construir features")
        result = self.create_lag_features(result, numeric_source)
        result = self.create_rolling_features(result, numeric_source)
        result = self.create_seasonality_features(result)
        result = self.create_ratio_features(result)
        result = self.create_target(result, target_type)

        excluded = {"target", self.date_column, *self.group_columns, "holiday_dates"}
        feature_columns = [column for column in result.columns if column not in excluded]
        features = result[feature_columns].copy()
        features = pd.get_dummies(features, columns=features.select_dtypes(include=["object", "category"]).columns.tolist(), dtype=float)
        for column in features.columns:
            if not pd.api.types.is_numeric_dtype(features[column]):
                features[column] = pd.to_numeric(features[column], errors="coerce")
        features = features.replace([np.inf, -np.inf], np.nan)
        features = features.fillna(features.median(numeric_only=True)).fillna(0.0)
        target = pd.to_numeric(result["target"], errors="coerce").fillna(0)
        return features.astype(float), target
