"""
Panel 4 - Inflation & households
Author: Eleena Golchin

Story: the Hormuz oil shock is reaching consumer prices. Section 1 shows how
far inflation has moved since the war began, in Europe, the UK, the USA and
Asia's three biggest economies. Section 2 lets you pick a future oil price
and see what it would mean for inflation and for your own energy bill.

How this file is organised:
    1. SETTINGS  - every data source and number you might want to change
    2. DATA      - saved copies in data/, with code to download them again
    3. ANALYSIS  - the maths, as small functions with docstrings
    4. CHARTS    - Plotly figures
    5. LAYOUT    - the two sections and their controls (Streamlit)

Run on its own:   python3 -m streamlit run panels/inflation.py
Refresh the data: python3 -c "from panels.inflation import save_all; save_all()"
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# =============================================================================
# 1. SETTINGS - change data sources here, nowhere else
# =============================================================================

# Data mode. False = read the saved copies in data/ (fast, works offline, the
# same numbers every time). True = download fresh data from the sources first
# and fall back to the saved copies if a website is down.
LIVE = False
END = pd.Timestamp("2026-10-31")          # last month shown (same for the whole dashboard)
START = pd.Timestamp("2015-01-01")        # first month downloaded
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Story dates (the same events as the other three panels)
WAR_START = pd.Timestamp("2026-02-28")    # US-Israel strikes on Iran
EVENTS = [("2026-02-28", "War begins"), ("2026-04-08", "Ceasefire"),
          ("2026-06-17", "US–Iran MOU"), ("2026-07-07", "Strikes resume")]
TARGET = 2.0                              # central banks' inflation target, %

MEASURES = ["Headline", "Energy", "Food", "Services"]

# Europe: Eurostat HICP, ECOICOP ver.2 dataset (the older one stops at Dec 2025)
EUROSTAT_COUNTRIES = {"Euro area": "EA", "Ireland": "IE", "Germany": "DE",
                      "France": "FR", "Italy": "IT", "Spain": "ES"}
EUROSTAT_CODES = {"Headline": "TOTAL", "Energy": "NRG", "Food": "FOOD", "Services": "SERV"}
EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"

# UK and Asia: OECD consumer prices
OECD_COUNTRIES = {"United Kingdom": "GBR", "Japan": "JPN", "China": "CHN", "India": "IND"}
OECD_CODES = {"Headline": "_T", "Energy": "CP045_0722", "Food": "CP01", "Services": "SERV"}
OECD_URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/"
            "{countries}.M.N.CPI.PA.{codes}.N.GY?startPeriod={start}&format=csvfilewithlabels")

# United States: Bureau of Labor Statistics CPI indexes
BLS_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
BLS_CODES = {"Headline": "CUUR0000SA0", "Energy": "CUUR0000SA0E",
             "Food": "CUUR0000SAF1", "Services": "CUUR0000SAS"}

# Oil and exchange rates: Yahoo Finance via yfinance (Sessions 6 and 11)
OIL_TICKER = "BZ=F"                                        # Brent crude, US$ per barrel
FX_TICKERS = {"EUR": ("EURUSD=X", "usd_per"), "GBP": ("GBPUSD=X", "usd_per"),   # US$ per 1 unit
              "JPY": ("JPY=X", "per_usd"), "CNY": ("CNY=X", "per_usd"),       # units per US$
              "INR": ("INR=X", "per_usd")}
CURRENCY = {"United Kingdom": "GBP", "United States": "USD", "Japan": "JPY",
            "China": "CNY", "India": "INR"}               # everyone else pays in euros
SYMBOL = {"EUR": "€", "GBP": "£", "USD": "$", "JPY": "¥", "CNY": "¥", "INR": "₹"}
TYPICAL_BILL = {"EUR": 200, "GBP": 170, "USD": 220, "JPY": 30000, "CNY": 600, "INR": 3000}

DEFAULT_ENERGY_WEIGHT = 7.0    # % of the basket, when no official weight is available
MAX_LAG_MONTHS = 6             # longest oil -> bills delay tested
TIMEOUT_SECONDS = 60           # give up on a slow website after this
HEADERS = {"User-Agent": "Mozilla/5.0 (UCD student dashboard)"}
COLOURS = ["#2e6fd8", "#c2410c", "#0f9b8e", "#7c5cd6", "#d48806", "#2e9b57",
           "#d23f3f", "#1b2a41", "#98a2b3", "#e377c2", "#17becf"]


def all_countries() -> list:
    """Every country the panel offers, in display order."""
    return list(EUROSTAT_COUNTRIES) + ["United Kingdom", "United States"] + \
        [c for c in OECD_COUNTRIES if c != "United Kingdom"]


# =============================================================================
# 2. DATA - every download returns the same tidy table: date, country, measure, value
# =============================================================================

def up_to_end(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows from START to END, so every run shows the same months."""
    dates = pd.to_datetime(df["date"])
    return df[(dates >= START) & (dates <= END)].copy()


def load(name: str, download) -> tuple[pd.DataFrame, str]:
    """Get one dataset: the saved copy in data/, or a fresh download.

    Returns the table and where it came from ("saved copy" or "live").
    If LIVE is on but the website fails, the saved copy is used instead,
    so the dashboard always runs (the Session 11 pattern).
    """
    path = DATA_DIR / f"inflation_{name}.csv"
    if LIVE or not path.exists():
        try:
            df = up_to_end(download())
            DATA_DIR.mkdir(exist_ok=True)
            df.to_csv(path, index=False)
            return df, "live"
        except Exception:
            if not path.exists():
                raise
    return up_to_end(pd.read_csv(path)), "saved copy"


def jsonstat_to_frame(j: dict) -> pd.DataFrame:
    """Turn Eurostat's JSON-stat reply into a table: one column per dimension + value.

    JSON-stat stores every number in one flat list; its position tells you
    which country, item and month it belongs to (like reading a grid row by row).
    """
    dims = j["id"]
    codes = []
    for d in dims:
        index = j["dimension"][d]["category"]["index"]
        if isinstance(index, dict):
            index = sorted(index, key=index.get)
        codes.append(list(index))
    values = j["value"]
    if isinstance(values, list):
        values = {i: v for i, v in enumerate(values) if v is not None}
    rows = []
    for flat, value in values.items():
        position = np.unravel_index(int(flat), j["size"])
        row = {d: codes[k][p] for k, (d, p) in enumerate(zip(dims, position))}
        row["value"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def eurostat(dataset: str, params: list) -> pd.DataFrame:
    """Download one Eurostat dataset, filtered by params, as a table."""
    response = requests.get(EUROSTAT_API + dataset, params=params,
                            headers=HEADERS, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return jsonstat_to_frame(response.json())


def download_eurostat() -> pd.DataFrame:
    """HICP annual inflation for the euro countries, one request per measure."""
    names = {code: name for name, code in EUROSTAT_COUNTRIES.items()}
    parts = []
    for measure, code in EUROSTAT_CODES.items():
        params = [("unit", "RCH_A"), ("coicop18", code), ("sinceTimePeriod", START.strftime("%Y-%m"))]
        params += [("geo", g) for g in EUROSTAT_COUNTRIES.values()]
        df = eurostat("prc_hicp_minr", params)
        parts.append(pd.DataFrame({"date": pd.to_datetime(df["time"]), "country": df["geo"].map(names),
                                   "measure": measure, "value": df["value"]}))
    return pd.concat(parts, ignore_index=True)


def download_weights() -> pd.DataFrame:
    """Latest share of energy in each euro country's shopping basket, as %."""
    params = [("coicop18", EUROSTAT_CODES["Energy"]), ("sinceTimePeriod", "2024")]
    params += [("geo", g) for g in EUROSTAT_COUNTRIES.values()]
    df = eurostat("prc_hicp_iw", params).sort_values("time")
    names = {code: name for name, code in EUROSTAT_COUNTRIES.items()}
    latest = df.groupby("geo")["value"].last()
    return pd.DataFrame({"date": END, "country": latest.index.map(names),
                         "weight": latest.values / 10})          # per 1000 -> %


# =============================================================================
# PANEL
# =============================================================================

def render() -> None:
    """Draw the whole panel. app.py runs this file, which calls render() at the bottom."""
    st.header("🧾 Inflation & households: the bill arrives")
    st.info("This panel is being built: the data and charts are coming next.")


if __name__ == "__main__":
    # Runs when you start this file directly, and when app.py runs it inside its tab.
    st.set_page_config(page_title="Inflation & households", layout="wide")
    render()
