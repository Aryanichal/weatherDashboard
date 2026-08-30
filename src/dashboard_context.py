"""Shared state passed from app.py into each tab's view module."""

import datetime as dt
from dataclasses import dataclass

import pandas as pd


@dataclass
class DashboardContext:
    raw: pd.DataFrame
    selected_names: list[str]
    id_by_name: dict[str, str]
    id_to_name: dict[str, str]
    start_date: dt.date
    end_date: dt.date
