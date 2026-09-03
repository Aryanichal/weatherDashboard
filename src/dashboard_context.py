"""Shared state passed from app.py into each tab's view module."""

import datetime as dt
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class DashboardContext:
    raw: pd.DataFrame
    selected_names: list[str]
    id_by_name: dict[str, str]
    id_to_name: dict[str, str]
    start_date: dt.date
    end_date: dt.date
    # Only meaningful for the Clustering tab, which replaces the shared
    # station multiselect with its own "Region" selectbox instead (see
    # app.py) -- clustering runs over every station in a region rather
    # than a hand-picked selection, so the multiselect above doesn't apply
    # to it at all. None for every other view.
    region: str | None = None
    # The actual st.columns() column the Region selectbox above was
    # rendered into (typed loosely as Any to avoid importing Streamlit's
    # internal DeltaGenerator type just for an annotation) -- a Streamlit
    # column/container reference stays writable after its own `with`
    # block exits, so Clustering (see _render_region_caption() in
    # src/views/clustering.py) uses this to append its own captions
    # directly under the Region dropdown instead of below the whole
    # Region/Date-range row, which would otherwise anchor them to
    # whichever column in that row ends up tallest rather than to Region
    # specifically. None for every other view.
    region_column: Any = None
