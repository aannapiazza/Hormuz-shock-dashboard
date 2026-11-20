"""
Panel 4 - Inflation & households
Author: Eleena Golchin

Story: the Hormuz oil shock is reaching consumer prices. Section 1 shows how
far inflation has moved since the war began, in Europe, the UK, the USA and
three of Asia's biggest oil importers. Section 2 lets you pick a future oil price
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
NORMAL_YEAR = "2025"                       # "normal" traffic = the 2025 average

# Oil and exchange rates: Yahoo Finance via yfinance (Sessions 6 and 11)
OIL_TICKER = "BZ=F"                                        # Brent crude, US$ per barrel
FX_TICKERS = {"EUR": ("EURUSD=X", "usd_per"), "GBP": ("GBPUSD=X", "usd_per"),   # US$ per 1 unit
              "KRW": ("KRW=X", "per_usd"), "CNY": ("CNY=X", "per_usd"),       # units per US$
              "INR": ("INR=X", "per_usd")}
CURRENCY = {"United Kingdom": "GBP", "United States": "USD", "South Korea": "KRW",
            "China": "CNY", "India": "INR"}               # everyone else pays in euros
SYMBOL = {"EUR": "€", "GBP": "£", "USD": "$", "KRW": "₩", "CNY": "¥", "INR": "₹"}
TYPICAL_BILL = {"EUR": 200, "GBP": 170, "USD": 220, "KRW": 150000, "CNY": 600, "INR": 3000}

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
    "weights": ("Eurostat basket weights", download_weights),
    "oil": ("Brent and exchange rates (yfinance)", download_oil),
    "hormuz": ("IMF PortWatch (Hormuz tankers)", download_hormuz),
}


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
    weights = {}
    if tables["weights"] is not None:
        weights = dict(zip(tables["weights"]["country"], tables["weights"]["weight"]))
    oil = None
    if tables["oil"] is not None:
        oil = tables["oil"].assign(date=pd.to_datetime(tables["oil"]["date"])).set_index("date")
    hormuz = None
    if tables["hormuz"] is not None:
        daily = tables["hormuz"].assign(date=pd.to_datetime(tables["hormuz"]["date"])).set_index("date")
        hormuz = daily.sort_index().resample("MS").mean()        # daily -> monthly averages
    return {"inflation": inflation, "weights": weights, "oil": oil, "hormuz": hormuz, "status": status}


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


# =============================================================================
# 3. ANALYSIS
# =============================================================================

def series_for(inflation: pd.DataFrame, country: str, measure: str) -> pd.Series:
    """One country's inflation for one measure, as a monthly Series."""
    rows = inflation[(inflation["country"] == country) & (inflation["measure"] == measure)]
    return rows.set_index("date")["value"].sort_index()


def change_since_war(s: pd.Series) -> tuple[float, float] | None:
    """Latest value and its change since February 2026, the last month before the war.

    Returns None if there is no data from both before and after the war.
    """
    before, after = s[s.index < WAR_START], s[s.index >= WAR_START]
    if before.empty or after.empty:
        return None
    return s.iloc[-1], s.iloc[-1] - before.iloc[-1]


def traffic_vs_normal(hormuz: pd.DataFrame, column: str = "capacity_tanker") -> pd.Series:
    """Monthly Hormuz tanker capacity as a % of the NORMAL_YEAR average (100 = normal)."""
    normal = hormuz.loc[NORMAL_YEAR, column].mean()
    return hormuz[column] / normal * 100


def currency_of(country: str) -> str:
    """The currency a country's households pay in."""
    return CURRENCY.get(country, "EUR")


def oil_change_yoy(oil: pd.DataFrame, currency: str) -> pd.Series:
    """Percentage change in the local-currency price of Brent vs 12 months earlier."""
    return (oil[currency].pct_change(12) * 100).dropna()


def fit_passthrough(energy: pd.Series, oil_change: pd.Series) -> dict:
    """How strongly, and how fast, oil prices feed into energy inflation.

    Step 1: for each delay of 0 to MAX_LAG_MONTHS months, correlate energy
            inflation with the oil-price change that many months earlier.
    Step 2: keep the delay with the highest correlation.
    Step 3: fit a straight line (least squares, np.polyfit):
                energy inflation = intercept + slope x oil change
            slope = extra points of energy inflation per 1% rise in oil.
    """
    correlations = {}
    for lag in range(MAX_LAG_MONTHS + 1):
        pair = pd.concat([energy, oil_change.shift(lag)], axis=1, sort=True).dropna()
        correlations[lag] = pair.iloc[:, 0].corr(pair.iloc[:, 1])
    best_lag = max(correlations, key=correlations.get)
    pair = pd.concat([energy.rename("energy"), oil_change.shift(best_lag).rename("oil")],
                     axis=1, sort=True).dropna()
    slope, intercept = np.polyfit(pair["oil"], pair["energy"], 1)
    return {"lag": best_lag, "slope": slope, "intercept": intercept,
            "r2": correlations[best_lag] ** 2, "points": pair}


def household_scenario(model: dict, brent_now: float, brent_future: float, energy_now: float,
                       headline_now: float, energy_weight: float, monthly_bill: float) -> dict:
    """Project energy inflation, headline inflation and a household's energy bill.

    Assumes exchange rates stay the same and that food and services
    inflation stay at today's rates (no second-round effects).
    """
    oil_change = (brent_future / brent_now - 1) * 100
    energy_future = model["intercept"] + model["slope"] * oil_change
    headline_future = headline_now + energy_weight / 100 * (energy_future - energy_now)
    extra_per_month = monthly_bill * energy_future / 100
    return {"oil_change": oil_change, "energy": energy_future,
            "headline": headline_future, "extra_per_month": extra_per_month}


def months_word(n: int) -> str:
    """'1 month' or '2 months'."""
    return f"{n} month{'s' if n != 1 else ''}"
# =============================================================================
# 4. CHARTS - Plotly
# =============================================================================

def style(fig: go.Figure, height: int, title: str, **layout) -> go.Figure:
    """The look shared by both charts: white background, dark text, title on the left.

    The charts are drawn with theme=None, so Streamlit keeps this white look
    even when the computer is in dark mode.
    """
    settings = dict(template="plotly_white", height=height, hovermode="x unified",
                    paper_bgcolor="white", plot_bgcolor="white", font=dict(color="#17202e"),
                    title=dict(text=f"<b>{title}</b>", x=0, xanchor="left", font=dict(size=16)),
                    margin=dict(l=10, r=20, t=50, b=40), legend=dict(orientation="h", y=-0.15, x=0))
    settings.update(layout)          # anything passed in replaces the default
    fig.update_layout(**settings)
    return fig


def add_war_and_events(fig: go.Figure, start: pd.Timestamp) -> go.Figure:
    """Shade the war period and draw a dotted line at each key event.

    Labels are only written when the chart starts in 2025 or later; over a
    longer period the events sit too close together to read, so only
    "War begins" is labelled. Labels alternate between two heights so
    neighbouring events don't overlap.
    """
    fig.add_vrect(x0=WAR_START, x1=END, fillcolor="#d23f3f", opacity=0.07, line_width=0, layer="below")
    zoomed_in = start >= pd.Timestamp("2025-01-01")
    for i, (date, label) in enumerate(EVENTS):
        fig.add_vline(x=pd.Timestamp(date), line=dict(color="#98a2b3", width=1, dash="dot"))
        if zoomed_in or i == 0:
            fig.add_annotation(x=pd.Timestamp(date), y=1 if i % 2 == 0 else 0.9, yref="paper", text=label,
                               showarrow=False, xanchor="left", yanchor="top", xshift=3,
                               font=dict(size=10, color="#6b7785"), bgcolor="rgba(255,255,255,0.8)")
    return fig


def chart_inflation(inflation, countries, measure, start, traffic=None) -> go.Figure:
    """Section 1 chart: one line per country, the war shaded, events marked.

    If `traffic` is given, Hormuz tanker capacity (% of normal) is drawn on a
    second axis on the right, so the supply cut and inflation can be compared.
    """
    fig = go.Figure()
    changes = {}
    for colour, country in zip(COLOURS, countries):
        s = series_for(inflation, country, measure)
        s = s[s.index >= start]
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=country, mode="lines",
                                 line=dict(color=colour, width=3 if country == countries[0] else 2),
                                 hovertemplate=f"{country}: %{{y:.1f}}%<extra></extra>"))
        result = change_since_war(s)
        if result:
            changes[country] = result[1]
    fig.add_hline(y=TARGET, line=dict(color="#6b7785", dash="dash", width=1),
                  annotation_text="2% target", annotation_position="bottom right")
    add_war_and_events(fig, start)
    if changes:   # a title that states the finding (Session 9)
        top = max(changes, key=lambda c: abs(changes[c]))
        title = (f"{measure} inflation in {top} is {'up' if changes[top] >= 0 else 'down'} "
                 f"{abs(changes[top]):.1f} points since the war began")
    else:
        title = f"{measure} inflation"
    extra = {}
    if traffic is not None:
        t = traffic[traffic.index >= start]
        fig.add_trace(go.Scatter(x=t.index, y=t.values, name="Hormuz tanker capacity (right axis)", yaxis="y2",
                                 mode="lines", line=dict(color="#1b2a41", width=2, dash="dot"),
                                 hovertemplate="Hormuz tankers: %{y:.0f}% of normal<extra></extra>"))
        extra["yaxis2"] = dict(title=f"Tanker capacity, % of {NORMAL_YEAR} average", overlaying="y", side="right",
                               range=[0, 140], ticksuffix="%", showgrid=False, tickmode="linear", tick0=0, dtick=20)
    return style(fig, 460, title, yaxis=dict(title=f"{measure} inflation, % a year", ticksuffix="%"), **extra)


def chart_passthrough(model, scenario, country, currency) -> go.Figure:
    """Section 2 chart: every past month, the fitted line, and your scenario."""
    p = model["points"]
    war = p.index >= WAR_START
    fig = go.Figure()
    for mask, name, colour, size in [(~war, "Months before the war", "#98a2b3", 7),
                                     (war, "Months since the war", "#d23f3f", 10)]:
        fig.add_trace(go.Scatter(x=p.loc[mask, "oil"], y=p.loc[mask, "energy"], mode="markers", name=name,
                                 marker=dict(color=colour, size=size), text=p.index[mask].strftime("%b %Y"),
                                 hovertemplate="%{text}: oil %{x:+.0f}%, energy %{y:.1f}%<extra></extra>"))
    x = np.linspace(min(p["oil"].min(), scenario["oil_change"]), max(p["oil"].max(), scenario["oil_change"]), 50)
    fig.add_trace(go.Scatter(x=x, y=model["intercept"] + model["slope"] * x, mode="lines", hoverinfo="skip",
                             name=f"Fitted line (R² = {model['r2']:.2f})", line=dict(color="#1b2a41", dash="dash")))
    fig.add_trace(go.Scatter(x=[scenario["oil_change"]], y=[scenario["energy"]], mode="markers", name="Your scenario",
                             marker=dict(symbol="star", size=22, color="#c2410c", line=dict(color="black", width=1)),
                             hovertemplate="Your scenario: oil %{x:+.0f}%, energy %{y:.1f}%<extra></extra>"))
    lag = months_word(model["lag"])
    return style(fig, 440,
                 f"In {country}, a 10% oil rise adds about {10 * model['slope']:.1f} points to energy inflation {lag} later",
                 hovermode="closest",
                 xaxis=dict(title=f"Change in the oil price in {currency} vs a year earlier, {lag} before (%)", zeroline=True),
                 yaxis=dict(title="Energy inflation, % a year", zeroline=True))


# =============================================================================
# 5. LAYOUT
# =============================================================================

def section_1_inflation(inflation: pd.DataFrame, hormuz: pd.DataFrame | None = None) -> None:
    """Section 1: how far has inflation moved since the war began?"""
    st.subheader("1 · Inflation since the war")
    c1, c2, c3 = st.columns([3, 1.5, 1.5])
    countries = c1.multiselect("Countries", all_countries(), key="infl_countries",
                               default=["Euro area", "Ireland", "United Kingdom", "United States", "China"])
    measure = c2.selectbox("Measure", MEASURES, key="infl_measure")
    start_year = c3.slider("Start year", START.year + 1, END.year, 2021, key="infl_start")
    if not countries:
        st.info("Pick at least one country.")
        return
    show_traffic = hormuz is not None and st.toggle(
        "Show oil tankers through Hormuz", value=True, key="infl_hormuz",
        help="Daily tanker capacity through the strait (IMF PortWatch), as a monthly % of the 2025 average.")
    traffic = traffic_vs_normal(hormuz) if show_traffic else None
    have = [c for c in countries if not series_for(inflation, c, measure).empty]
    missing = [c for c in countries if c not in have]

    cols = st.columns(max(1, min(len(have), 5)))
    for col, country in zip(cols, have[:5]):
        result = change_since_war(series_for(inflation, country, measure))
        if result:
            col.metric(country, f"{result[0]:.1f}%", f"{result[1]:+.1f} pts since Feb 2026",
                       delta_color="inverse")
    st.plotly_chart(chart_inflation(inflation, have, measure, pd.Timestamp(f"{start_year}-01-01"), traffic),
                    width="stretch", theme=None, key="infl_chart")
    if traffic is not None:
        st.caption(f"Tanker capacity through Hormuz in {traffic.index[-1]:%B %Y} was **{traffic.iloc[-1]:.1f}%** of the "
                   f"{NORMAL_YEAR} average, against {traffic.loc['2026-02-01']:.0f}% in February 2026, the month before the war.")
    if missing:
        st.caption(f"No {measure.lower()} figures published for: {', '.join(missing)}.")
    st.caption(f"Annual inflation to {END:%B %Y}. Sources: Eurostat HICP (euro countries); OECD CPI (UK, South "
               "Korea, China, India); US Bureau of Labor Statistics CPI; IMF PortWatch (tankers). Non-euro figures are national measures, close to "
               "but not exactly comparable with the euro-area HICP. Shaded: since 28 Feb 2026.")


def section_2_household(inflation: pd.DataFrame, weights: dict, oil: pd.DataFrame) -> None:
    """Section 2: what would a new oil price mean for my household?"""
    st.subheader("2 · What it means for your household")
    options = [c for c in all_countries() if currency_of(c) in oil
               and not series_for(inflation, c, "Energy").empty
               and not series_for(inflation, c, "Headline").empty]
    if not options:
        st.warning("No energy inflation figures available, so Section 2 cannot run.")
        return
    brent_now = float(oil["USD"].iloc[-1])
    c1, c2, c3 = st.columns(3)
    country = c1.selectbox("Country", options, key="infl_hh_country",
                           index=options.index("Ireland") if "Ireland" in options else 0)
    currency = currency_of(country)
    symbol = SYMBOL[currency]
    brent_future = c2.slider("Brent oil price in a year ($/barrel)", 40, 200, 120, step=5, key="infl_brent")
    typical = TYPICAL_BILL[currency]
    bill = c3.number_input(f"Your monthly energy bill ({symbol})", 0, typical * 10, typical,
                           step=max(10, typical // 20), key=f"infl_bill_{currency}")

    energy = series_for(inflation, country, "Energy")
    headline = series_for(inflation, country, "Headline")
    model = fit_passthrough(energy, oil_change_yoy(oil, currency))
    weight = weights.get(country, DEFAULT_ENERGY_WEIGHT)
    result = household_scenario(model, brent_now, brent_future, energy.iloc[-1],
                                headline.iloc[-1], weight, bill)

    extra_year = 12 * result["extra_per_month"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Energy inflation", f"{result['energy']:.1f}%",
              f"{result['energy'] - energy.iloc[-1]:+.1f} pts vs now", delta_color="inverse")
    m2.metric("Headline inflation", f"{result['headline']:.1f}%",
              f"{result['headline'] - headline.iloc[-1]:+.1f} pts vs now", delta_color="inverse")
    m3.metric("Your energy bill", f"{symbol}{bill + result['extra_per_month']:,.0f}/month",
              f"{'+' if extra_year >= 0 else '-'}{symbol}{abs(extra_year):,.0f} a year", delta_color="inverse")
    st.plotly_chart(chart_passthrough(model, result, country, currency), width="stretch", theme=None, key="infl_model")
    weight_note = "" if country in weights else " (an approximate weight: no official figure)"
    st.caption(
        f"Brent averaged ${brent_now:.0f} in {oil.index[-1]:%B %Y}, so ${brent_future} is a "
        f"{round(result['oil_change']) + 0:+d}% move. If oil stays flat, energy inflation falls back, because "
        f"last year's jump drops out of the comparison. Energy is {weight:.1f}% of the {country} basket"
        f"{weight_note}. Model: correlation at delays of 0–{MAX_LAG_MONTHS} months, then a least-squares line. "
        "It assumes exchange rates and other prices stay put, so it is a rough guide, not a forecast. "
        "Oil: Yahoo Finance via yfinance.".replace("$", "\\$"))


# =============================================================================
# PANEL
# =============================================================================

def render() -> None:
    """Draw the whole panel. app.py runs this file, which calls render() at the bottom."""
    st.header("🧾 Inflation & households: the bill arrives")
    data = load_data()
    problems = {k: v for k, v in data["status"].items() if not v.startswith(("saved", "live"))}
    if problems:
        st.warning("Some data could not be loaded: " + " · ".join(f"{k}: {v}" for k, v in problems.items()))
    if data["inflation"] is None:
        st.error("No inflation data. Check the inflation_*.csv files in the data folder.")
        return
    section_1_inflation(data["inflation"], data["hormuz"])
    st.divider()
    if data["oil"] is None:
        st.error("No oil data, so Section 2 cannot run. Check data/inflation_oil.csv.")
        return
    section_2_household(data["inflation"], data["weights"], data["oil"])


if __name__ == "__main__":
    # Runs when you start this file directly, and when app.py runs it inside its tab.
    st.set_page_config(page_title="Inflation & households", layout="wide")
    render()
