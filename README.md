# Weather Dashboard (DWD Open Data)

An interactive Streamlit dashboard for exploring historical German weather
station data from the **DWD (Deutscher Wetterdienst) Climate Data Center**,
with on-demand regression and clustering analysis over a selection of
stations/parameters.

## Data source

We use [`wetterdienst`](https://github.com/earthobservations/wetterdienst), a
Python library that wraps the DWD's public open-data archive (no API key,
no signup, no manual downloading). It fetches directly from DWD's servers and
we cache results locally as parquet files under `data/` (git-ignored).

Docs: https://wetterdienst.readthedocs.io/

## Setup

Requires **Python 3.10+**.

```bash
git clone <this-repo-url>
cd weatherDashboard

python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Run the dashboard:

```bash
streamlit run app.py
```

It opens at `http://localhost:8501`. The first load for a given
station/date-range selection fetches from DWD and caches locally, so it will
be slow once and fast after.

### Sanity-checking the data layer alone

```bash
python -m src.data_loader
```

This fetches one year of data for Berlin-Tempelhof and prints a preview —
useful to confirm your setup works before touching the Streamlit app.

## Project structure

```
app.py               # Streamlit entry point — UI, tabs, layout
src/data_loader.py    # Fetches + locally caches DWD station data
src/analysis.py        # Regression / clustering helpers (sklearn)
src/forecasting.py     # Hot-day and July-temperature forecasts (linear trend + PyTorch neural network)
data/                  # Local cache of downloaded data (git-ignored)
.streamlit/config.toml # Streamlit theme/server config
```

The **Global Warming Future Trend Prediction** section exports its generated
city hot-day (days above 30 °C) and average-July-temperature forecasts to
`data/global_warming_forecasts.csv`. It uses complete annual data only, so an
in-progress calendar year is not used to train or score a forecast.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branching workflow and code
organization conventions.

## Roadmap ideas
- More parameters/datasets beyond `climate_summary` (wind, sun, soil, ...)
- Additional analysis tools (e.g. anomaly detection, seasonal decomposition)
- Compare regions/clusters over custom date ranges
- Export selected data + chart as a report
