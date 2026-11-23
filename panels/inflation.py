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
from datetime import date
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
TARGET = 2.0                              # central banks' inflation target, %
PHASES = [   # the phases of the war, shaded on the Section 1 charts: (name, start, end, colour)
    ("War & closure", "2026-02-28", "2026-04-08", "#d23f3f"),
    ("Ceasefire", "2026-04-08", "2026-07-07", "#2e6fd8"),
    ("Conflict resumes", "2026-07-07", "2026-10-31", "#7c5cd6"),
]

# The time slider at the top of the panel links both sections: Section 1 shows
# only these months, and Section 2 starts its scenario from the last of them.
DEFAULT_PERIOD = (date(2025, 1, 1), END.date())

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


def chosen_period() -> tuple[pd.Timestamp, pd.Timestamp]:
    """Draw the panel's time slider and return (first month, last day) of the period picked.

    The start is moved back to the 1st of its month, because the data is
    monthly (each month is dated on the 1st).
    """
    st.session_state.setdefault("infl_period", DEFAULT_PERIOD)      # first visit: Jan 2025 to Oct 2026
    start, end = st.slider("Period", min_value=date(START.year + 1, 1, 1), max_value=END.date(),
                           format="MMM YYYY", key="infl_period",
                           help="The chart shows these months. The numbers and the bill use the last one.")
    return pd.Timestamp(start).to_period("M").to_timestamp(), pd.Timestamp(end)


def value_at(s: pd.Series | pd.DataFrame, end: pd.Timestamp):
    """The last value on or before `end` (the latest month the period reaches)."""
    return s[s.index <= end].iloc[-1]


def in_period(s: pd.Series | pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp):
    """Only the rows dated from start to end (both included)."""
    return s[(s.index >= start) & (s.index <= end)]


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
            "r2": correlations[best_lag] ** 2, "points": pair, "correlations": correlations}


def new_bill(model: dict, brent_now: float, brent_future: float, bill: float) -> dict:
    """Energy inflation and the monthly bill a year from now, if Brent moves from brent_now to brent_future."""
    oil_change = (brent_future / brent_now - 1) * 100
    energy = model["intercept"] + model["slope"] * oil_change
    return {"oil_change": oil_change, "energy": energy, "bill": bill * (1 + energy / 100)}



def story_numbers(inflation: pd.DataFrame, traffic: pd.Series | None, end: pd.Timestamp = END) -> list[dict]:
    """The three numbers at the top of Section 1, as of the end of the time period, each with a note.

    Each card: label, value, delta (change since February 2026, the last month
    before the war; none if the period ends before then), delta_color, note.
    A card is left out if its data is missing.
    """
    feb = pd.Timestamp("2026-02-01")
    cards = []
    others = []                                  # food and services, to compare with energy in its note
    for measure in ("Food", "Services"):
        o = series_for(inflation, "Euro area", measure).loc[:end]
        if not o.empty:
            moved = change_since_war(o)
            others.append(f"{measure.lower()} {o.iloc[-1]:.1f}%" + (f" ({moved[1]:+.1f} pts)" if moved else ""))
    energy_note = "Energy is the direct link from oil to prices."
    if others:
        energy_note += " Same month: " + ", ".join(others) + "."
    for measure, label, note in [
            ("Headline", "Euro-area inflation", "All prices, average of the euro countries. The ECB aims for 2%."),
            ("Energy", "Euro-area energy inflation", energy_note)]:
        s = series_for(inflation, "Euro area", measure).loc[:end]
        if s.empty:
            continue
        result = change_since_war(s)
        cards.append(dict(label=f"{label}, {s.index[-1]:%b %Y}", value=f"{s.iloc[-1]:.1f}%",
                          delta=f"{result[1]:+.1f} pts since Feb 2026" if result else None,
                          delta_color="inverse", note=note))
    if traffic is not None and not traffic.loc[:end].empty:
        t = traffic.loc[:end]
        delta = f"{t.iloc[-1] - traffic.loc[feb]:+.0f} pts since Feb 2026" if t.index[-1] > feb else None
        cards.append(dict(label=f"Tankers through Hormuz, {t.index[-1]:%b %Y}", value=f"{t.iloc[-1]:.1f}%",
                          delta=delta, delta_color="normal",
                          note=f"Oil tankers through the strait, against the {NORMAL_YEAR} average (IMF PortWatch)."))
    return cards

def key_takeaway(inflation: pd.DataFrame, end: pd.Timestamp = END) -> str:
    """The panel's main point in two sentences, as of the end of the period, counting every country."""
    if end < WAR_START:
        return "This period ends before the war started. Drag the end past February 2026 to see what changed."
    rises = [r[1] for r in (change_since_war(series_for(inflation, c, "Energy").loc[:end]) for c in all_countries()) if r]
    energy = change_since_war(series_for(inflation, "Euro area", "Energy").loc[:end])
    headline = change_since_war(series_for(inflation, "Euro area", "Headline").loc[:end])
    if not rises or not energy or not headline:
        return ""
    up = sum(r > 0 for r in rises)
    which = "all" if up == len(rises) else f"{up} of the"
    return (f"Energy prices have risen faster since the war started in {which} {len(rises)} countries that publish "
            f"them. In the euro area, energy inflation is up {energy[1]:.0f} points, but overall inflation is up "
            f"only {headline[1]:.1f}.")


def months_word(n: int) -> str:
    """'1 month' or '2 months'."""
    return f"{n} month{'s' if n != 1 else ''}"
# =============================================================================
# 4. CHARTS - Plotly
# =============================================================================

def style(fig: go.Figure, height: int, title: str, title_size: int = 16, **layout) -> go.Figure:
    """The look shared by both charts: white background, dark text, title on the left.

    The charts are drawn with theme=None, so Streamlit keeps this white look
    even when the computer is in dark mode.
    """
    settings = dict(template="plotly_white", height=height, hovermode="x unified",
                    paper_bgcolor="white", plot_bgcolor="white", font=dict(color="#17202e"),
                    title=dict(text=f"<b>{title}</b>", x=0, xanchor="left", font=dict(size=title_size)),
                    margin=dict(l=10, r=20, t=50, b=40), legend=dict(orientation="h", y=-0.15, x=0))
    settings.update(layout)          # anything passed in replaces the default
    fig.update_layout(**settings)
    return fig


def add_war_and_events(fig: go.Figure, start: pd.Timestamp, end: pd.Timestamp = END,
                       label: bool = True) -> go.Figure:
    """Shade each phase of the war in its own light colour, with its name at the top.

    Only the part of each phase inside the chosen period is shaded. Names sit at
    two heights in turn, so a short phase's name doesn't run into the next one.
    """
    for i, (name, p_start, p_end, colour) in enumerate(PHASES):
        x0, x1 = max(pd.Timestamp(p_start), start), min(pd.Timestamp(p_end), end)
        if x0 >= x1:                                 # phase outside the chosen period
            continue
        fig.add_vrect(x0=x0, x1=x1, fillcolor=colour, opacity=0.09, line_width=0, layer="below")
        if label:
            fig.add_annotation(x=x0, y=1 if i % 2 == 0 else 0.93, yref="paper", text=name, showarrow=False,
                               xanchor="left", yanchor="top", xshift=3, font=dict(size=11, color=colour),
                               bgcolor="rgba(255,255,255,0.8)")
    return fig


def chart_inflation(inflation, countries, measure, start, end, traffic=None) -> go.Figure:
    """The panel's one chart: inflation by country, with the war's phases shaded and
    tanker traffic through Hormuz as a light grey area on the right-hand axis."""
    fig = go.Figure()
    if traffic is not None:
        t = in_period(traffic, start, end)
        fig.add_trace(go.Scatter(x=t.index, y=t.values, name="Tankers through Hormuz (% of normal, right axis)",
                                 yaxis="y2", mode="lines", fill="tozeroy", line=dict(color="rgba(27,42,65,0.35)", width=1),
                                 fillcolor="rgba(27,42,65,0.07)", hovertemplate="Tankers: %{y:.0f}% of normal<extra></extra>"))
    for colour, country in zip(COLOURS, countries):
        s = in_period(series_for(inflation, country, measure), start, end)
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=country, mode="lines",
                                 line=dict(color=colour, width=3 if country == countries[0] else 2),
                                 hovertemplate=f"{country}: %{{y:.1f}}%<extra></extra>"))
    fig.add_hline(y=TARGET, line=dict(color="#98a2b3", dash="dash", width=1),
                  annotation_text="2% target", annotation_position="bottom left")
    add_war_and_events(fig, start, end)
    return style(fig, 450, f"{measure} inflation since the war started", margin=dict(l=10, r=50, t=50, b=40),
                 yaxis=dict(title=f"{measure} inflation, % a year", ticksuffix="%"),
                 yaxis2=dict(overlaying="y", side="right", range=[0, 300], tickvals=[0, 50, 100], ticksuffix="%",
                             showgrid=False, tickfont=dict(size=10, color="#98a2b3")),
                 xaxis=month_axis(start, end))


def month_axis(start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """An x-axis from start to end whose ticks count back from the LAST month, so it is always labelled."""
    months = (end.year - start.year) * 12 + end.month - start.month
    step = 1 if months <= 12 else 2 if months <= 24 else 3 if months <= 48 else 6 if months <= 96 else 12
    return dict(range=[start, end], tick0=end.to_period("M").to_timestamp(), dtick=f"M{step}", tickformat="%b %Y")






# =============================================================================
# 5. LAYOUT
# =============================================================================

def story_card(col, card: dict) -> None:
    """One small number above the chart. Its note shows when you hover over the (?) icon."""
    note = card.get("note")
    col.metric(card["label"], card["value"], card.get("delta"), delta_color=card.get("delta_color", "normal"),
               help=note.replace("$", "\\$") if note else None)      # \\$ stops Streamlit reading $...$ as maths
        
    

def bill_calculator(inflation: pd.DataFrame, oil: pd.DataFrame, end: pd.Timestamp) -> None:
    """The small 'Your energy bill' box: pick a country, an oil price and today's bill."""
    st.markdown("**Your energy bill**")   
    st.caption("What a new oil price would mean for you")
    options = [c for c in all_countries() if currency_of(c) in oil and not series_for(inflation, c, "Energy").empty]
    country = st.selectbox("Country", options, key="infl_hh_country",
                           index=options.index("Ireland") if "Ireland" in options else 0)
    currency = currency_of(country)
    symbol = SYMBOL[currency]
    brent_future = st.slider("Oil price in a year ($ a barrel)", 40, 200, 120, step=5, key="infl_brent")
    typical = TYPICAL_BILL[currency]
    bill = st.number_input(f"Monthly bill today ({symbol})", 0, typical * 10, typical,
                           step=max(10, typical // 20), key=f"infl_bill_{currency}")
    base = oil.index[oil.index <= end][-1]                  # the last month of the time period
    brent_now = float(oil.loc[base, "USD"])
    model = fit_passthrough(series_for(inflation, country, "Energy"), oil_change_yoy(oil, currency))
    result = new_bill(model, brent_now, brent_future, bill)
    extra = 12 * (result["bill"] - bill)
    st.metric("New monthly bill", f"{symbol}{result['bill']:,.0f}",
              f"{'+' if extra >= 0 else '-'}{symbol}{abs(extra):,.0f} a year", delta_color="inverse")
    st.caption(f"From {base:%b %Y}, when oil was \\${brent_now:.0f} a barrel. Energy inflation would be "
               f"{result['energy']:.1f}%. Bills usually follow oil about {months_word(model['lag'])} later.")


# =============================================================================
# PANEL
# =============================================================================

def render() -> None:
    """Draw the whole panel. app.py runs this file, which calls render() at the bottom."""
    st.header("Inflation and households")
    data = load_data()
    problems = {k: v for k, v in data["status"].items() if not v.startswith(("saved", "live"))}
    if problems:
        st.warning("Some data could not be loaded: " + " · ".join(f"{k}: {v}" for k, v in problems.items()))
    if data["inflation"] is None:
        st.error("No inflation data. Check the inflation_*.csv files in the data folder.")
        return
    inflation, oil = data["inflation"], data["oil"]
    traffic = traffic_vs_normal(data["hormuz"]) if data["hormuz"] is not None else None
    takeaway = st.empty()                            # filled in once the period is known

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        start, end = chosen_period()
    countries = c2.multiselect("Countries", all_countries(), key="infl_countries",
                               default=["Euro area", "United Kingdom", "United States"])
    measure = c3.selectbox("Measure", MEASURES, index=1, key="infl_measure")
    takeaway.success("**Key takeaway**  \n" + key_takeaway(inflation, end))

    st.subheader("Inflation since the war")
    chart_col, calc_col = st.columns([3, 1], gap="medium")
    with chart_col.container(border=True):
        for col, card in zip(st.columns(3), story_numbers(inflation, traffic, end)):
            story_card(col, card)
        have = [c for c in countries if not series_for(inflation, c, measure).empty]
        if have:
            st.plotly_chart(chart_inflation(inflation, have, measure, start, end, traffic),
                            width="stretch", theme=None, key="infl_chart")
        else:
            st.info("Pick at least one country that publishes this measure.")
    if oil is not None:
        with calc_col.container(border=True):
            bill_calculator(inflation, oil, end)
    method_and_sources(data["status"])


def method_and_sources(status: dict) -> None:
    """A closed box at the bottom with the method and the sources."""
    with st.expander("Method and sources"):
        st.markdown(
            "**The bill calculator** looks at how energy prices have followed oil prices since 2016. It tries delays "
            f"of 0 to {MAX_LAG_MONTHS} months, keeps the one that fits best, and draws a straight line through the "
            "result. Your bill is read off that line. It ignores wages and exchange-rate changes, so treat it as a "
            "rough estimate.\n\n"
            "**Data**, monthly to October 2026: Eurostat HICP for the euro countries; OECD CPI for the UK, South "
            "Korea, China and India; the US Bureau of Labor Statistics for the USA (to September 2026, and October "
            "2025 was never published because of the government shutdown); Brent and exchange rates from Yahoo "
            "Finance; oil tankers through Hormuz from IMF PortWatch, against the 2025 average. China has no energy "
            "figures and India only headline.\n\n"
            "Loaded from: " + ", ".join(f"{k}: {v}" for k, v in status.items()) + ".")
        
        
if __name__ == "__main__":
    # Runs when you start this file directly, and when app.py runs it inside its tab.
    st.set_page_config(page_title="Inflation & households", layout="wide")
    render()
