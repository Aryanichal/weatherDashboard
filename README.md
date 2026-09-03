# Weather Dashboard (DWD Open Data)

An interactive Streamlit dashboard for exploring historical German weather
station data from the **DWD (Deutscher Wetterdienst) Climate Data Center**,
with on-demand regression and clustering analysis over a selection of
stations/parameters.

## Data sources

We use [`wetterdienst`](https://github.com/earthobservations/wetterdienst) [1],
a Python library that wraps the DWD's public open-data archive. No API key,
signup, or manual downloading is required. It fetches directly from DWD's
servers, and we cache results locally as parquet files under `data/`
(git-ignored).

Two distinct DWD Climate Data Center (CDC) products are used:

- **Historical daily station observations** ("climate_summary") [2], used by
  every tab under "Weather Analysis" (Time Series, Map, Regression,
  Clustering, Global Warming). Covers temperature, precipitation, wind,
  humidity, pressure, sunshine, and snow depth per station, back to each
  station's own start date.
- **MOSMIX point forecasts** [3], used by the "Live Weather" tab for current
  conditions and the roughly 10 day forecast for around 40 preset German
  cities.

Docs: https://wetterdienst.readthedocs.io/

See [References](#references) below for full citations

## Setup

Requires **Python 3.10+**.

```bash
git clone https://github.com/Aryanichal/weatherDashboard.git
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

## References

Data:

1. Gutzmann, B. and Motl, A. wetterdienst (version 0.133.0) [software]. 2024.
   DOI: 10.5281/zenodo.3960624. https://github.com/earthobservations/wetterdienst
2. Deutscher Wetterdienst (DWD), Climate Data Center (CDC). Historical daily
   station observations (temperature, pressure, precipitation, sunshine
   duration, wind, humidity) for Germany, version v24.3. Dataset ID:
   `urn:wmo:md:de-dwd-cdc:obsgermany-climate-daily-kl`. Available at:
   https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/
   (accessed via the `wetterdienst` library, see [1]).
3. Deutscher Wetterdienst (DWD). MOSMIX point weather forecasts. Available
   at: https://opendata.dwd.de/weather/local_forecasts/mos/ (accessed via the
   `wetterdienst` library, see [1]).

Software and libraries:

4. Pedregosa, F. et al. Scikit-learn: Machine learning in Python. Journal of
   Machine Learning Research, 12, pp. 2825 to 2830, 2011.
5. Paszke, A. et al. PyTorch: An imperative style, high performance deep
   learning library. Advances in Neural Information Processing Systems, 32,
   2019.
6. McKinney, W. Data structures for statistical computing in Python.
   Proceedings of the 9th Python in Science Conference, pp. 51 to 56, 2010.
7. Harris, C.R. et al. Array programming with NumPy. Nature, 585, pp. 357 to
   362, 2020.
8. Plotly Technologies Inc. Collaborative data science. Montreal, QC, 2015.
   https://plotly.com
9. Streamlit Inc. Streamlit, the fastest way to build data apps. 2019.
   https://streamlit.io

DWD's own citation terms are described at:
https://opendata.dwd.de/climate_environment/CDC/Terms_of_use.pdf

