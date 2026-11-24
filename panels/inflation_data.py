"""
Data for the inflation panel: downloads from Eurostat, the OECD, the US BLS,
Yahoo Finance and IMF PortWatch, with saved copies in data/ (Session 11 pattern).

Refresh the saved copies: python3 -c "from panels.inflation_data import save_all; save_all()"
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st

# Data mode. False = read the saved copies in data/ (fast, works offline, the
# same numbers every time). True = download fresh data from the sources first
# and fall back to the saved copies if a website is down.
LIVE = False
END = pd.Timestamp("2026-10-31")          # last month shown (same for the whole dashboard)
START = pd.Timestamp("2015-01-01")        # first month downloaded
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

MEASURES = ["Headline", "Energy", "Food", "Services"]

# Europe: Eurostat HICP, ECOICOP ver.2 dataset (the older one stops at Dec 2025)
EUROSTAT_COUNTRIES = {"Euro area": "EA", "Ireland": "IE", "Germany": "DE",
                      "France": "FR", "Italy": "IT", "Spain": "ES"}
EUROSTAT_CODES = {"Headline": "TOTAL", "Energy": "NRG", "Food": "FOOD", "Services": "SERV"}
EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"

# UK and Asia: OECD consumer prices
OECD_COUNTRIES = {"United Kingdom": "GBR", "South Korea": "KOR", "China": "CHN", "India": "IND"}
# (Japan was dropped: the OECD stopped publishing its CPI in this series after June 2021.)
OECD_CODES = {"Headline": "_T", "Energy": "CP045_0722", "Food": "CP01", "Services": "SERV"}
OECD_URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/"
            "{countries}.M.N.CPI.PA.{codes}.N.GY?startPeriod={start}&format=csvfilewithlabels")

# United States: Bureau of Labor Statistics CPI indexes
BLS_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
BLS_CODES = {"Headline": "CUUR0000SA0", "Energy": "CUUR0000SA0E",
             "Food": "CUUR0000SAF1", "Services": "CUUR0000SAS"}

# Shipping: IMF PortWatch daily chokepoint transits (satellite ship-tracking data).
# The full file downloaded from portwatch.imf.org is kept in data/ as the raw source.
PORTWATCH_RAW = DATA_DIR / "portwatch_daily_chokepoints.csv"
PORTWATCH_API = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
                 "Daily_Chokepoints_Data/FeatureServer/0/query")
CHOKEPOINT = "Strait of Hormuz"

# Oil and exchange rates: Yahoo Finance via yfinance (Sessions 6 and 11)
SPOT_BRENT = DATA_DIR / "oil_monthly_brent_data.csv"     # EIA spot Brent (FRED MCOILBRENTEU), saved by the oil panel
OIL_TICKER = "BZ=F"                                        # Brent crude, US$ per barrel
FX_TICKERS = {"EUR": ("EURUSD=X", "usd_per"), "GBP": ("GBPUSD=X", "usd_per"),   # US$ per 1 unit
              "KRW": ("KRW=X", "per_usd"), "CNY": ("CNY=X", "per_usd"),       # units per US$
              "INR": ("INR=X", "per_usd")}
TIMEOUT_SECONDS = 60           # give up on a slow website after this
HEADERS = {"User-Agent": "Mozilla/5.0 (UCD student dashboard)"}
def all_countries() -> list:
    """Every country the panel offers, in display order."""
    return list(EUROSTAT_COUNTRIES) + ["United Kingdom", "United States"] + \
        [c for c in OECD_COUNTRIES if c != "United Kingdom"]
# =============================================================================
# Every download returns the same tidy table: date, country, measure, value
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


def download_oecd() -> pd.DataFrame:
    """CPI annual inflation for the UK, South Korea, China and India from the OECD."""
    url = OECD_URL.format(countries="+".join(OECD_COUNTRIES.values()),
                          codes="+".join(OECD_CODES.values()), start=START.strftime("%Y-%m"))
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    raw = pd.read_csv(io.StringIO(response.text))
    names = {code: name for name, code in OECD_COUNTRIES.items()}
    measures = {code: name for name, code in OECD_CODES.items()}
    return pd.DataFrame({"date": pd.to_datetime(raw["TIME_PERIOD"]),
                         "country": raw["REF_AREA"].map(names),
                         "measure": raw["EXPENDITURE"].map(measures),
                         "value": raw["OBS_VALUE"]}).dropna()


def download_bls() -> pd.DataFrame:
    """US CPI price indexes from the BLS, turned into annual % changes.

    The BLS publishes index levels (e.g. 337.5), not inflation rates, so the
    rate is worked out here: (this month / same month a year ago - 1) x 100.
    Months the BLS didn't publish (shown as "-") are left empty.
    """
    body = {"seriesid": list(BLS_CODES.values()), "startyear": str(END.year - 9),
            "endyear": str(END.year)}                              # the free API allows 10 years
    response = requests.post(BLS_URL, json=body, headers=HEADERS, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    measures = {code: name for name, code in BLS_CODES.items()}
    parts = []
    for series in response.json()["Results"]["series"]:
        months = [d for d in series["data"] if d["period"] != "M13"]   # M13 = yearly average
        index = pd.Series(
            pd.to_numeric([d["value"] for d in months], errors="coerce"),
            index=pd.to_datetime([f"{d['year']}-{d['period'][1:]}-01" for d in months]),
        ).sort_index().asfreq("MS")                # one row per month, gaps stay empty
        rate = ((index / index.shift(12) - 1) * 100).dropna()
        parts.append(pd.DataFrame({"date": rate.index, "country": "United States",
                                   "measure": measures[series["seriesID"]], "value": rate.values}))
    return pd.concat(parts, ignore_index=True)


def download_oil() -> pd.DataFrame:
    """Monthly average Brent price in US$ and in each country's own currency (yfinance)."""
    import yfinance as yf
    tickers = [OIL_TICKER] + [t for t, _ in FX_TICKERS.values()]
    raw = yf.download(tickers, start=(START - pd.DateOffset(years=1)).strftime("%Y-%m-%d"),
                      auto_adjust=True, progress=False)["Close"].ffill()
    monthly = raw.resample("MS").mean()
    oil = pd.DataFrame({"USD": monthly[OIL_TICKER]})
    for currency, (ticker, kind) in FX_TICKERS.items():
        rate = monthly[ticker]
        oil[currency] = oil["USD"] / rate if kind == "usd_per" else oil["USD"] * rate
    oil.index.name = "date"
    return oil.dropna().reset_index()


def download_hormuz() -> pd.DataFrame:
    """Daily oil-tanker traffic through the Strait of Hormuz (IMF PortWatch).

    Reads the raw PortWatch file in data/ if it is there; otherwise asks the
    PortWatch API for the Hormuz rows directly. Keeps only Hormuz and the
    columns this panel uses.
    """
    if PORTWATCH_RAW.exists():
        df = pd.read_csv(PORTWATCH_RAW)
    else:
        rows, offset = [], 0
        while True:
            reply = requests.get(PORTWATCH_API, timeout=TIMEOUT_SECONDS, params={
                "where": f"portname='{CHOKEPOINT}'", "outFields": "*", "f": "json",
                "orderByFields": "date", "resultOffset": offset, "resultRecordCount": 2000}).json()
            batch = [f["attributes"] for f in reply.get("features", [])]
            rows += batch
            if len(batch) < 2000:
                break
            offset += 2000
        df = pd.DataFrame(rows)
        if pd.api.types.is_numeric_dtype(df["date"]):       # the API sends dates in milliseconds
            df["date"] = pd.to_datetime(df["date"], unit="ms")
    df = df[df["portname"] == CHOKEPOINT]
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    return df[["date", "n_tanker", "n_total", "capacity_tanker"]].sort_values("date")
SOURCES = {   # file name in data/: (label shown on screen, download function)
    "eurostat": ("Eurostat (Europe)", download_eurostat),
    "oecd": ("OECD (UK and Asia)", download_oecd),
    "bls": ("BLS (USA)", download_bls),
    "oil": ("Brent and exchange rates (yfinance)", download_oil),
    "hormuz": ("IMF PortWatch (Hormuz tankers)", download_hormuz),
}


def to_spot_brent(oil: pd.DataFrame) -> pd.DataFrame:
    """Use the same Brent price as the oil panel (EIA spot, monthly, via FRED) instead of Yahoo's futures.

    The exchange rates still come from Yahoo Finance: each currency's price is
    rescaled so that it is spot Brent converted at that month's rate.
    """
    if not SPOT_BRENT.exists():                 # oil panel's file missing: keep the futures prices
        return oil
    spot = pd.read_csv(SPOT_BRENT, parse_dates=["observation_date"]).set_index("observation_date")["MCOILBRENTEU"]
    rates = oil.div(oil["USD"], axis=0)         # units of each currency per US$
    return rates.mul(spot.reindex(oil.index), axis=0).dropna()


@st.cache_data(show_spinner="Loading inflation and oil data...")
def load_data() -> dict:
    """Load every dataset this panel needs. Cached, so it runs once per session."""
    tables, status = {}, {}
    for name, (label, download) in SOURCES.items():
        try:
            tables[name], status[label] = load(name, download)
        except Exception as error:
            tables[name], status[label] = None, f"missing ({type(error).__name__})"

    parts = [tables[n] for n in ("eurostat", "oecd", "bls") if tables[n] is not None]
    inflation = None
    if parts:
        inflation = pd.concat(parts, ignore_index=True)
        inflation["date"] = pd.to_datetime(inflation["date"])
        inflation["value"] = pd.to_numeric(inflation["value"], errors="coerce")
        inflation = inflation.dropna()
    oil = None
    if tables["oil"] is not None:
        oil = to_spot_brent(tables["oil"].assign(date=pd.to_datetime(tables["oil"]["date"])).set_index("date"))
    hormuz = None
    if tables["hormuz"] is not None:
        daily = tables["hormuz"].assign(date=pd.to_datetime(tables["hormuz"]["date"])).set_index("date")
        hormuz = daily.sort_index().resample("MS").mean()        # daily -> monthly averages
    return {"inflation": inflation, "oil": oil, "hormuz": hormuz, "status": status}


def save_all() -> None:
    """Download every dataset again and save it in data/ (run before submitting)."""
    for name, (label, download) in SOURCES.items():
        try:
            df = up_to_end(download())
            DATA_DIR.mkdir(exist_ok=True)
            df.to_csv(DATA_DIR / f"inflation_{name}.csv", index=False)
            print(f"saved   {label}: {len(df)} rows, to {pd.to_datetime(df['date']).max():%b %Y}")
        except Exception as error:
            print(f"FAILED  {label}: {error}")




