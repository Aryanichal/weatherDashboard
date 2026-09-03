"""Forecast annual climate indicators for the long-run city stations.

Forecasts the long-term climate-impact trend, not the weather in a
particular future year. Models are re-fit from source data on each
uncached run rather than loaded from saved binaries.
"""

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import streamlit as st
import torch
from torch import nn
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.data_loader import (
    DATA_DIR,
    LONG_RUN_CITY_STATIONS,
    get_station_data,
    get_hot_days_data,
)

FORECAST_START_YEAR = 1991
EVALUATION_START_YEAR = 2020
FORECAST_HORIZON_YEARS = 20
HOT_DAY_THRESHOLD = 30.0
RAINY_DAY_THRESHOLD = 1.0
PYTORCH_MODEL_NAME = "PyTorch NN (10 layers, 200 epochs)"
FORECAST_CSV_PATH = DATA_DIR / "global_warming_forecasts.csv"
# Include this in Streamlit's cache key. Bump it whenever the returned
# dataframe schema or forecasting target changes.
FORECAST_CACHE_VERSION = "hot-days-july-and-rainy-days-v2"
HOT_DAYS_INDICATOR = "Hot days above 30 °C"
JULY_TEMPERATURE_INDICATOR = "Average July temperature"
RAINY_DAYS_INDICATOR = "Rainy days above 1 mm"


class HotDayNeuralNetwork(nn.Module):
    """A ten-hidden-layer network for one-dimensional yearly input."""

    def __init__(self) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(1, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, 48),
            nn.Tanh(),
            nn.Linear(48, 48),
            nn.Tanh(),
            nn.Linear(48, 32),
            nn.Tanh(),
            nn.Linear(32, 32),
            nn.Tanh(),
            nn.Linear(32, 24),
            nn.Tanh(),
            nn.Linear(24, 16),
            nn.Tanh(),
            nn.Linear(16, 12),
            nn.Tanh(),
            nn.Linear(12, 8),
            nn.Tanh(),
            nn.Linear(8, 1),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.layers(values)


class PyTorchHotDayRegressor:
    """Scikit-learn-like wrapper around a deterministic 200-epoch PyTorch model."""

    epochs = 200

    def fit(self, years: pd.DataFrame, targets: pd.Series) -> "PyTorchHotDayRegressor":
        x_values = years["year"].to_numpy(dtype=np.float32).reshape(-1, 1)
        y_values = targets.to_numpy(dtype=np.float32).reshape(-1, 1)
        self.x_mean = float(x_values.mean())
        self.x_std = float(x_values.std()) or 1.0
        self.y_mean = float(y_values.mean())
        self.y_std = float(y_values.std()) or 1.0
        x_tensor = torch.tensor((x_values - self.x_mean) / self.x_std, dtype=torch.float32)
        y_tensor = torch.tensor((y_values - self.y_mean) / self.y_std, dtype=torch.float32)

        # Keep every run reproducible for a meaningful model comparison.
        torch.manual_seed(42)
        self.network = HotDayNeuralNetwork()
        optimiser = torch.optim.Adam(self.network.parameters(), lr=0.01)
        loss_function = nn.MSELoss()
        self.network.train()
        for _ in range(self.epochs):
            optimiser.zero_grad()
            loss = loss_function(self.network(x_tensor), y_tensor)
            loss.backward()
            optimiser.step()
        return self

    def predict(self, years: pd.DataFrame) -> np.ndarray:
        x_values = years["year"].to_numpy(dtype=np.float32).reshape(-1, 1)
        x_tensor = torch.tensor((x_values - self.x_mean) / self.x_std, dtype=torch.float32)
        self.network.eval()
        with torch.no_grad():
            scaled_prediction = self.network(x_tensor).cpu().numpy().reshape(-1)
        return scaled_prediction * self.y_std + self.y_mean


def _last_complete_year() -> int:
    """Return the last year safe to use in an annual forecast."""
    return datetime.now(UTC).year - 1


def prepare_hot_day_counts() -> pd.DataFrame:
    """Return one annual above-30 °C day count per city and complete year.

    Excludes the current calendar year, since it isn't complete yet.
    """
    last_complete_year = _last_complete_year()
    hot_days = get_hot_days_data(
        city_stations=LONG_RUN_CITY_STATIONS,
        start_year=FORECAST_START_YEAR,
        hot_day_threshold=HOT_DAY_THRESHOLD,
    )
    return (
        hot_days.loc[
            hot_days["year"].between(FORECAST_START_YEAR, last_complete_year),
            ["city", "year", "days_above_threshold"],
        ]
        .rename(columns={"days_above_threshold": "observed_hot_days"})
        .assign(
            indicator=HOT_DAYS_INDICATOR,
            unit="days",
            observed_value=lambda frame: frame["observed_hot_days"].astype(float),
        )
        .sort_values(["city", "year"])
        .reset_index(drop=True)
    )


def prepare_july_temperatures() -> pd.DataFrame:
    """Return one average July temperature per city and complete year."""
    last_complete_year = _last_complete_year()
    observations = get_station_data(
        station_ids=list(LONG_RUN_CITY_STATIONS.values()),
        start_date=f"{FORECAST_START_YEAR}-01-01",
        end_date=f"{datetime.now(UTC).year}-12-31",
        cache=True,
    )
    station_to_city = {station_id: city for city, station_id in LONG_RUN_CITY_STATIONS.items()}
    temperatures = observations.loc[
        observations["parameter"] == "temperature_air_mean_2m",
        ["station_id", "date", "value"],
    ].dropna()
    temperatures = temperatures.assign(date=pd.to_datetime(temperatures["date"], utc=True))
    temperatures["city"] = temperatures["station_id"].astype(str).map(station_to_city)
    temperatures["year"] = temperatures["date"].dt.year
    july = temperatures.loc[
        temperatures["city"].notna()
        & temperatures["year"].between(FORECAST_START_YEAR, last_complete_year)
        & (temperatures["date"].dt.month == 7)
    ]
    return (
        july.groupby(["city", "year"], as_index=False)["value"]
        .mean()
        .rename(columns={"value": "observed_july_temp"})
        .assign(
            indicator=JULY_TEMPERATURE_INDICATOR,
            unit="°C",
            observed_value=lambda frame: frame["observed_july_temp"],
        )
        .sort_values(["city", "year"])
        .reset_index(drop=True)
    )


def prepare_rainy_day_counts() -> pd.DataFrame:
    """Return annual counts of days with more than 1 mm precipitation per city."""
    last_complete_year = _last_complete_year()
    observations = get_station_data(
        station_ids=list(LONG_RUN_CITY_STATIONS.values()),
        start_date=f"{FORECAST_START_YEAR}-01-01",
        end_date=f"{datetime.now(UTC).year}-12-31",
        cache=True,
    )
    station_to_city = {station_id: city for city, station_id in LONG_RUN_CITY_STATIONS.items()}
    precipitation = observations.loc[
        observations["parameter"] == "precipitation_height",
        ["station_id", "date", "value"],
    ].dropna()
    precipitation = precipitation.assign(date=pd.to_datetime(precipitation["date"], utc=True))
    precipitation["city"] = precipitation["station_id"].astype(str).map(station_to_city)
    precipitation["year"] = precipitation["date"].dt.year
    precipitation = precipitation.loc[
        precipitation["city"].notna()
        & precipitation["year"].between(FORECAST_START_YEAR, last_complete_year)
    ]
    city_years = pd.MultiIndex.from_product(
        [LONG_RUN_CITY_STATIONS, range(FORECAST_START_YEAR, last_complete_year + 1)],
        names=["city", "year"],
    ).to_frame(index=False)
    observation_counts = precipitation.groupby(["city", "year"], as_index=False).size()
    rainy_days = (
        precipitation.loc[precipitation["value"] > RAINY_DAY_THRESHOLD]
        .groupby(["city", "year"], as_index=False)
        .size()
        .rename(columns={"size": "observed_rainy_days"})
    )
    result = (
        city_years.merge(rainy_days, on=["city", "year"], how="left")
        .merge(observation_counts, on=["city", "year"], how="left")
    )
    result["observed_rainy_days"] = result["observed_rainy_days"].fillna(0)
    result.loc[result["size"].isna(), "observed_rainy_days"] = np.nan
    return result.assign(
        indicator=RAINY_DAYS_INDICATOR,
        unit="days",
        observed_value=lambda frame: frame["observed_rainy_days"].astype(float),
    )[["city", "year", "indicator", "unit", "observed_value"]]
def _make_models() -> dict[str, object]:
    """Create deterministic, deliberately small models for a short annual series."""
    return {
        "Linear trend": Pipeline(
            [("scale_year", StandardScaler()), ("model", Ridge(alpha=1.0))]
        ),
        PYTORCH_MODEL_NAME: PyTorchHotDayRegressor(),
    }


def _fit_predict(
    model: object,
    train: pd.DataFrame,
    prediction_years: np.ndarray,
    minimum_prediction: float | None = None,
) -> np.ndarray:
    # Both models expose the scikit-learn fit/predict interface.
    model.fit(train[["year"]], train["observed_value"])
    predictions = model.predict(pd.DataFrame({"year": prediction_years}))
    return np.maximum(predictions, minimum_prediction) if minimum_prediction is not None else predictions


def _validation_residuals(
    train: pd.DataFrame, model_name: str, minimum_prediction: float | None
) -> np.ndarray:
    """Collect one-step expanding-window validation residuals within training."""
    residuals: list[float] = []
    # Need at least 10 years of history before the NN can fit reliably.
    first_validation_year = int(train["year"].min()) + 10
    for year in range(first_validation_year, int(train["year"].max()) + 1):
        history = train.loc[train["year"] < year]
        actual = train.loc[train["year"] == year, "observed_value"].iloc[0]
        prediction = _fit_predict(
            _make_models()[model_name], history, np.array([year]), minimum_prediction
        )[0]
        residuals.append(float(actual - prediction))
    return np.asarray(residuals)


def build_and_save_forecasts() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Evaluate both models, save forecasts to :data:`FORECAST_CSV_PATH`, and return all data.

    Returns ``(forecasts, metrics, historical_values)``.
    """
    historical = pd.concat(
        [prepare_hot_day_counts(), prepare_july_temperatures(), prepare_rainy_day_counts()],
        ignore_index=True,
    )
    last_complete_year = _last_complete_year()
    if last_complete_year < EVALUATION_START_YEAR:
        raise ValueError("At least one complete evaluation year is required for forecasting.")

    forecast_years = np.arange(last_complete_year + 1, last_complete_year + 1 + FORECAST_HORIZON_YEARS)
    generated_at = datetime.now(UTC).isoformat()
    forecast_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []

    for indicator, indicator_data in historical.groupby("indicator", sort=False):
        minimum_prediction = 0.0 if indicator in {HOT_DAYS_INDICATOR, RAINY_DAYS_INDICATOR} else None
        unit = indicator_data["unit"].iloc[0]
        for city, city_data in indicator_data.groupby("city", sort=True):
            city_data = city_data.dropna(subset=["observed_value"]).sort_values("year")
            train = city_data.loc[city_data["year"] < EVALUATION_START_YEAR]
            test = city_data.loc[city_data["year"].between(EVALUATION_START_YEAR, last_complete_year)]
            if train.shape[0] < 11 or test.empty:
                raise ValueError(f"Insufficient complete annual data to forecast {city}.")

            models = (
                {"Linear trend": _make_models()["Linear trend"]}
                if indicator == RAINY_DAYS_INDICATOR
                else _make_models()
            )
            for model_name, model in models.items():
                test_prediction = _fit_predict(
                    model, train, test["year"].to_numpy(), minimum_prediction
                )
                test_residuals = test["observed_value"].to_numpy() - test_prediction
                validation_residuals = _validation_residuals(train, model_name, minimum_prediction)
                lower_offset, upper_offset = np.quantile(validation_residuals, [0.1, 0.9])
                metric_rows.append(
                    {
                        "indicator": indicator,
                        "unit": unit,
                        "city": city,
                        "model": model_name,
                        "test_start_year": EVALUATION_START_YEAR,
                        "test_end_year": last_complete_year,
                        "mae": float(mean_absolute_error(test["observed_value"], test_prediction)),
                        "rmse": float(np.sqrt(np.mean(test_residuals**2))),
                    }
                )

                future_prediction = _fit_predict(model, city_data, forecast_years, minimum_prediction)
                for year, prediction in zip(forecast_years, future_prediction, strict=True):
                    forecast_rows.append(
                        {
                            "indicator": indicator,
                            "unit": unit,
                            "city": city,
                            "model": model_name,
                            "year": int(year),
                            "predicted_value": float(prediction),
                            "lower_80": float(
                                max(0, prediction + lower_offset)
                                if minimum_prediction is not None
                                else prediction + lower_offset
                            ),
                            "upper_80": float(
                                max(0, prediction + upper_offset)
                                if minimum_prediction is not None
                                else prediction + upper_offset
                            ),
                            "training_end_year": last_complete_year,
                            "generated_at": generated_at,
                        }
                    )

    forecasts = pd.DataFrame(forecast_rows).sort_values(["indicator", "city", "model", "year"]).reset_index(drop=True)
    metrics = pd.DataFrame(metric_rows).sort_values(["indicator", "city", "model"]).reset_index(drop=True)
    forecasts.to_csv(FORECAST_CSV_PATH, index=False)
    return forecasts, metrics, historical


@st.cache_data(show_spinner="Training global-warming forecast models...")
def load_forecasts(cache_version: str = FORECAST_CACHE_VERSION) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Cached Streamlit entry point for generating and exporting forecasts."""
    del cache_version  # Its value intentionally participates in Streamlit's cache key.
    return build_and_save_forecasts()
