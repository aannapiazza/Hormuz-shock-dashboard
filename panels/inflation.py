"""
Panel 4 - Inflation & households
Author: Eleena Golchin

Story: the Hormuz oil shock is reaching consumer prices. Section 1 shows
how far inflation has moved since the war began, in Europe, the UK, the
USA and Russia. Section 2 lets you pick a future oil price and see what it
would mean for inflation and for your own energy bill.

How this file is organised (same order as the panel template):
    1. SETTINGS  - every data source and number you might want to change
    2. DATA      - download the data (live first, saved copy if that fails)
    3. ANALYSIS  - the maths, as small functions with docstrings
    4. CHARTS    - matplotlib figures (Session 9 conventions)
    5. LAYOUT    - the two sections and their controls (Streamlit)
"""

import io
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import streamlit as st

# =============================================================================
# 1. SETTINGS - change data sources here, nowhere else
# =============================================================================

MEASURES = ["Headline", "Energy", "Food", "Services"]

# --- Euro countries: Eurostat HICP (no API key) ------------------------------
# Since Jan 2026 the HICP is published in the ECOICOP ver.2 dataset below
# (the older datasets stop at Dec 2025). "EA" = the euro area at each date.
# To add a country, add a line, e.g. "Portugal": "PT".
EUROSTAT_COUNTRIES = {
    "Euro area": "EA",
    "Ireland": "IE",
    "Germany": "DE",
    "France": "FR",
    "Italy": "IT",
    "Spain": "ES",
}
EUROSTAT_CODES = {"Headline": "TOTAL", "Energy": "NRG", "Food": "FOOD", "Services": "SERV"}
EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
INFLATION_DATASET = "prc_hicp_minr"   # monthly rates of change
INFLATION_UNIT = "RCH_A"              # annual rate of change, %
WEIGHT_DATASET = "prc_hicp_iw"        # item weights, per 1000

# --- United Kingdom: OECD consumer prices (no API key) -----------------------
OECD_COUNTRIES = {"United Kingdom": "GBR"}
OECD_CODES = {"Headline": "_T", "Energy": "CP045_0722", "Food": "CP01", "Services": "SERV"}
OECD_URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/"
            "{countries}.M.N.CPI.PA.{codes}.N.GY?startPeriod={start}&format=csvfilewithlabels")

# --- United States: Bureau of Labor Statistics CPI (no API key) --------------
# These are price indexes; the panel turns them into annual % changes itself.
BLS_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
BLS_CODES = {"Headline": "CUUR0000SA0", "Energy": "CUUR0000SA0E",
             "Food": "CUUR0000SAF1", "Services": "CUUR0000SAS"}

# --- Russia: Central Bank of Russia (headline inflation only) ----------------
CBR_URL = ("https://www.cbr.ru/eng/hd_base/infl/?UniDbQuery.Posted=True"
           "&UniDbQuery.From=01.{start_year}&UniDbQuery.To=12.2030")

# Each country's currency, used to price oil in Section 2.
CURRENCY = {"United Kingdom": "GBP", "United States": "USD", "Russia": "RUB"}  # others: EUR
SYMBOL = {"EUR": "€", "GBP": "£", "USD": "$", "RUB": "₽"}

# --- Oil and exchange rates: yfinance (Sessions 6 and 11) ---------------------
OIL_TICKER = "BZ=F"                               # Brent, US$ per barrel
FX_TICKERS = {"EUR": "EURUSD=X", "GBP": "GBPUSD=X"}  # US$ per 1 euro / 1 pound

START_YEAR = 2015
DATA_DIR = Path(__file__).resolve().parent.parent / "data"   # saved copies

# --- Story settings ------------------------------------------------------------
WAR_START = pd.Timestamp("2026-02-28")   # US-Israel strikes on Iran
TARGET = 2.0                             # ECB, Bank of England and Fed target, %
DEFAULT_ENERGY_WEIGHT = 7.0              # % of the basket, if no official weight
MAX_LAG_MONTHS = 6                       # longest oil -> bills delay tested
TIMEOUT_SECONDS = 60                     # give up on a slow website after this
HEADERS = {"User-Agent": "Mozilla/5.0 (UCD student dashboard)"}


def all_countries() -> list:
    """Every country the panel offers, in display order."""
    return list(EUROSTAT_COUNTRIES) + list(OECD_COUNTRIES) + ["United States", "Russia"]


# =============================================================================
# 2. DATA - live download first, saved copy second (Session 11 pattern)
# Every download returns the same tidy table: date, country, measure, value
# =============================================================================

def with_backup(name: str, download) -> tuple[pd.DataFrame | None, str]:
    """Run a download; save a copy if it works, use the copy if it fails."""
    backup = DATA_DIR / f"inflation_{name}.csv"
    try:
        df = download()
        if df is None or df.empty:
            raise ValueError("no rows returned")
        try:
            DATA_DIR.mkdir(exist_ok=True)
            df.to_csv(backup, index=False)
        except OSError:
            pass  # read-only server: fine, we still have the live data
        return df, "live"
    except Exception as error:
        if backup.exists():
            return pd.read_csv(backup), "saved copy"
        return None, f"missing ({type(error).__name__})"


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
    """HICP inflation for the euro countries, one request per measure."""
    names = {code: name for name, code in EUROSTAT_COUNTRIES.items()}
    parts = []
    for measure, code in EUROSTAT_CODES.items():
        params = [("unit", INFLATION_UNIT), ("coicop18", code),
                  ("sinceTimePeriod", f"{START_YEAR}-01")]
        params += [("geo", g) for g in EUROSTAT_COUNTRIES.values()]
        try:
            df = eurostat(INFLATION_DATASET, params)
        except Exception:
            continue  # one measure failing should not stop the others
        parts.append(pd.DataFrame({"date": pd.to_datetime(df["time"]),
                                   "country": df["geo"].map(names),
                                   "measure": measure, "value": df["value"]}))
    return pd.concat(parts, ignore_index=True) if parts else None


def download_weights() -> pd.DataFrame:
    """Latest energy weight in each euro country's basket, as %."""
    params = [("coicop18", EUROSTAT_CODES["Energy"]), ("sinceTimePeriod", "2024")]
    params += [("geo", g) for g in EUROSTAT_COUNTRIES.values()]
    df = eurostat(WEIGHT_DATASET, params).sort_values("time")
    names = {code: name for name, code in EUROSTAT_COUNTRIES.items()}
    latest = df.groupby("geo")["value"].last()
    return pd.DataFrame({"country": latest.index.map(names), "weight": latest.values / 10})


def download_oecd() -> pd.DataFrame:
    """CPI inflation for the OECD countries (the UK)."""
    url = OECD_URL.format(countries="+".join(OECD_COUNTRIES.values()),
                          codes="+".join(OECD_CODES.values()), start=f"{START_YEAR}-01")
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
    """US CPI indexes from the BLS, turned into annual % changes."""
    this_year = pd.Timestamp.today().year
    body = {"seriesid": list(BLS_CODES.values()),
            "startyear": str(this_year - 9), "endyear": str(this_year)}  # max 10 years
    response = requests.post(BLS_URL, json=body, headers=HEADERS, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    measures = {code: name for name, code in BLS_CODES.items()}
    parts = []
    for series in response.json()["Results"]["series"]:
        months = [d for d in series["data"] if d["period"] != "M13"]  # M13 = yearly average
        index = pd.Series(
            pd.to_numeric([d["value"] for d in months], errors="coerce"),  # "-" = not published
            index=pd.to_datetime([f"{d['year']}-{d['period'][1:]}-01" for d in months]),
        ).sort_index().asfreq("MS")              # one row per month, gaps stay empty
        rate = ((index / index.shift(12) - 1) * 100).dropna()   # index -> annual % change
        parts.append(pd.DataFrame({"date": rate.index, "country": "United States",
                                   "measure": measures[series["seriesID"]],
                                   "value": rate.values}))
    return pd.concat(parts, ignore_index=True)


def download_cbr() -> pd.DataFrame:
    """Russia's headline inflation from the Central Bank of Russia's website table."""
    response = requests.get(CBR_URL.format(start_year=START_YEAR), headers=HEADERS,
                            timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    table = next(t for t in pd.read_html(io.StringIO(response.text))
                 if any("inflation" in str(c).lower() for c in t.columns))
    date_col = table.columns[0]
    infl_col = next(c for c in table.columns if "inflation" in str(c).lower()
                    and "target" not in str(c).lower())
    return pd.DataFrame({
        "date": pd.to_datetime(table[date_col].astype(str), format="%m.%Y", errors="coerce"),
        "country": "Russia", "measure": "Headline",
        "value": pd.to_numeric(table[infl_col].astype(str).str.replace(",", "."), errors="coerce"),
    }).dropna()


def download_oil() -> pd.DataFrame:
    """Monthly average Brent price in US$, euros and pounds (yfinance)."""
    import yfinance as yf
    tickers = [OIL_TICKER] + list(FX_TICKERS.values())
    raw = yf.download(tickers, start=f"{START_YEAR - 1}-01-01",
                      auto_adjust=True, progress=False)["Close"].ffill()
    monthly = raw.resample("MS").mean().dropna()
    oil = pd.DataFrame({"brent_usd": monthly[OIL_TICKER]})
    for currency, ticker in FX_TICKERS.items():
        oil[f"brent_{currency.lower()}"] = monthly[OIL_TICKER] / monthly[ticker]
    oil.index.name = "date"
    return oil.reset_index()


@st.cache_data(ttl=6 * 60 * 60, show_spinner="Downloading inflation and oil data...")
def load_data() -> dict:
    """Download everything this panel needs. Cached for 6 hours."""
    status, parts = {}, []
    for name, download in [("Eurostat (euro area)", download_eurostat),
                           ("OECD (UK)", download_oecd),
                           ("BLS (USA)", download_bls),
                           ("Central Bank (Russia)", download_cbr)]:
        file_name = name.split()[0].lower()
        df, status[name] = with_backup(file_name, download)
        if df is not None:
            parts.append(df)
    inflation = None
    if parts:
        inflation = pd.concat(parts, ignore_index=True)
        inflation["date"] = pd.to_datetime(inflation["date"])
        inflation["value"] = pd.to_numeric(inflation["value"], errors="coerce")
        inflation = inflation.dropna()

    df, status["Weights"] = with_backup("weights", download_weights)
    weights = dict(zip(df["country"], df["weight"])) if df is not None else {}

    df, status["Oil (yfinance)"] = with_backup("oil", download_oil)
    oil = None if df is None else df.assign(date=pd.to_datetime(df["date"])).set_index("date")

    return {"inflation": inflation, "weights": weights, "oil": oil, "status": status}


# =============================================================================
# 3. ANALYSIS
# =============================================================================

def series_for(inflation: pd.DataFrame, country: str, measure: str) -> pd.Series:
    """One country's inflation for one measure, as a monthly Series."""
    rows = inflation[(inflation["country"] == country) & (inflation["measure"] == measure)]
    return rows.set_index("date")["value"].sort_index()


def change_since_war(s: pd.Series) -> tuple[float, float] | None:
    """Latest value and its change since the last month before the war.

    Returns None if there is no data from both before and after the war.
    """
    before, after = s[s.index < WAR_START], s[s.index >= WAR_START]
    if before.empty or after.empty:
        return None
    return s.iloc[-1], s.iloc[-1] - before.iloc[-1]


def currency_of(country: str) -> str:
    """The currency a country's households pay in."""
    return CURRENCY.get(country, "EUR")


def oil_change_yoy(oil: pd.DataFrame, currency: str) -> pd.Series:
    """Percentage change in the local-currency price of Brent vs 12 months earlier."""
    return (oil[f"brent_{currency.lower()}"].pct_change(12) * 100).dropna()


def fit_passthrough(energy: pd.Series, oil_change: pd.Series) -> dict:
    """How strongly, and how fast, oil prices feed into energy inflation.

    Step 1: for each delay of 0 to MAX_LAG_MONTHS months, correlate energy
            inflation with the oil-price change that many months earlier.
    Step 2: keep the delay with the highest correlation.
    Step 3: fit a straight line (least squares, np.polyfit):
                energy inflation = intercept + slope * oil change
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


def household_scenario(model: dict, brent_now: float, brent_future: float,
                       energy_now: float, headline_now: float,
                       energy_weight: float, monthly_bill: float) -> dict:
    """Project energy inflation, headline inflation and a household bill.

    Assumes exchange rates stay the same and that food and services
    inflation stay at today's rates (no second-round effects).
    """
    oil_change = (brent_future / brent_now - 1) * 100
    energy_future = model["intercept"] + model["slope"] * oil_change
    headline_future = headline_now + energy_weight / 100 * (energy_future - energy_now)
    extra_per_month = monthly_bill * energy_future / 100
    return {"oil_change": oil_change, "energy": energy_future,
            "headline": headline_future, "extra_per_month": extra_per_month}


# =============================================================================
# 4. CHARTS - fig, ax = plt.subplots(); the title states the finding
# =============================================================================

COLOURS = ["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#d62728",
           "#8c564b", "#e377c2", "#17becf", "#7f7f7f"]


def chart_inflation(inflation, countries, measure, start) -> plt.Figure:
    """Section 1 chart: one line per country, war period shaded."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    changes = {}
    for colour, country in zip(COLOURS, countries):
        s = series_for(inflation, country, measure)
        s = s[s.index >= start]
        if s.empty:
            continue
        ax.plot(s.index, s.values, label=country, color=colour,
                linewidth=2.5 if country == countries[0] else 1.5)
        result = change_since_war(s)
        if result:
            changes[country] = result[1]
    ax.axvspan(WAR_START, inflation["date"].max(), color="red", alpha=0.08, label="Since the war")
    ax.axhline(TARGET, color="grey", linestyle="--", linewidth=1, label="2% target")
    ax.set_ylabel(f"{measure} inflation, % y/y")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left", ncol=3, fontsize=9)

    if changes:  # a title that states the finding (Session 9)
        top = max(changes, key=lambda c: abs(changes[c]))
        word = "up" if changes[top] >= 0 else "down"
        title = (f"{measure} inflation in {top} is {word} "
                 f"{abs(changes[top]):.1f} points since the war began")
    else:
        title = f"{measure} inflation (no data since the war yet)"
    ax.set_title(title, loc="left", fontweight="bold")
    fig.tight_layout()
    return fig


def chart_passthrough(model, scenario, country, currency) -> plt.Figure:
    """Section 2 chart: past months, the fitted line, and your scenario."""
    p = model["points"]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    war = p.index >= WAR_START
    ax.scatter(p.loc[~war, "oil"], p.loc[~war, "energy"], s=18, color="#9aa7b8",
               label="Months before the war")
    ax.scatter(p.loc[war, "oil"], p.loc[war, "energy"], s=30, color="#d62728",
               label="Months since the war")
    x = np.linspace(min(p["oil"].min(), scenario["oil_change"]),
                    max(p["oil"].max(), scenario["oil_change"]), 50)
    ax.plot(x, model["intercept"] + model["slope"] * x, color="black",
            linestyle="--", label=f"Fitted line (R² = {model['r2']:.2f})")
    ax.scatter([scenario["oil_change"]], [scenario["energy"]], marker="*", s=350,
               color="#ff7f0e", edgecolor="black", zorder=5, label="Your scenario")
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.axvline(0, color="grey", linewidth=0.8)
    ax.set_xlabel(f"Change in oil price in {currency} vs a year earlier, "
                  f"{model['lag']} month{'s' if model['lag'] != 1 else ''} before (%)")
    ax.set_ylabel("Energy inflation, % y/y")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=9)
    ax.set_title(f"In {country}, a 10% oil rise adds about {10 * model['slope']:.1f} points "
                 f"to energy inflation {model['lag']} month{'s' if model['lag'] != 1 else ''} later",
                 loc="left", fontweight="bold")
    fig.tight_layout()
    return fig


# =============================================================================
# 5. LAYOUT - two sections, each with its own controls
# =============================================================================

def section_1_inflation(inflation: pd.DataFrame) -> None:
    """Section 1: how far has inflation moved since the war began?"""
    st.subheader("1 · Inflation since the war")
    c1, c2, c3 = st.columns([3, 2, 2])
    countries = c1.multiselect("Countries", all_countries(),
                               default=["Euro area", "Ireland", "United Kingdom", "United States"])
    measure = c2.selectbox("Measure", MEASURES, index=0)
    start_year = c3.slider("Start year", START_YEAR, 2026, 2021)
    if not countries:
        st.info("Pick at least one country.")
        return

    have = [c for c in countries if not series_for(inflation, c, measure).empty]
    missing = [c for c in countries if c not in have]
    cols = st.columns(max(1, min(len(have), 5)))
    for col, country in zip(cols, have[:5]):
        result = change_since_war(series_for(inflation, country, measure))
        if result:
            col.metric(country, f"{result[0]:.1f}%", f"{result[1]:+.1f} pts since Feb 2026",
                       delta_color="inverse")

    fig = chart_inflation(inflation, have, measure, pd.Timestamp(f"{start_year}-01-01"))
    st.pyplot(fig)
    plt.close(fig)
    if missing:
        st.caption(f"No {measure.lower()} data for: {', '.join(missing)}. "
                   "Russia publishes headline inflation only.")
    st.caption("Sources: Eurostat HICP (euro countries); OECD CPI (UK); US BLS CPI (USA); "
               "Central Bank of Russia. The UK, US and Russian figures are national measures, "
               "so they are close to, but not exactly comparable with, the euro-area HICP. "
               "Shaded: since 28 Feb 2026.")


def section_2_household(inflation: pd.DataFrame, weights: dict, oil: pd.DataFrame) -> None:
    """Section 2: what would a new oil price mean for my household?"""
    st.subheader("2 · What it means for your household")
    options = [c for c in all_countries()
               if not series_for(inflation, c, "Energy").empty
               and not series_for(inflation, c, "Headline").empty]
    if not options:
        st.warning("No energy inflation data available, so Section 2 cannot run.")
        return
    brent_now = float(oil["brent_usd"].iloc[-1])
    c1, c2, c3 = st.columns(3)
    country = c1.selectbox("Country", options,
                           index=options.index("Ireland") if "Ireland" in options else 0,
                           key="household_country")
    currency = currency_of(country)
    symbol = SYMBOL[currency]
    brent_future = c2.slider("Brent oil price in a year ($/barrel)", 40, 200,
                             int(round(brent_now / 5) * 5), step=5)
    bill = c3.number_input(f"Your monthly energy bill ({symbol})", 0, 2000, 200, step=10)

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
              f"{'+' if extra_year >= 0 else '-'}{symbol}{abs(extra_year):,.0f} a year",
              delta_color="inverse")

    fig = chart_passthrough(model, result, country, currency)
    st.pyplot(fig)
    plt.close(fig)
    weight_note = ("" if country in weights
                   else " (an approximate weight: no official figure was downloaded)")
    st.caption(
        f"Brent is ${brent_now:.0f} now, so ${brent_future} is a {round(result['oil_change']) + 0:+d}% move. "
        "If oil stays flat, energy inflation falls back, because last year's jump drops out "
        f"of the comparison. Energy is {weight:.1f}% of the {country} basket{weight_note}. "
        f"Model: correlation at delays of 0–{MAX_LAG_MONTHS} months, then a least-squares line. "
        "It assumes exchange rates and other prices stay put, so it is a rough guide, "
        "not a forecast. Oil: Yahoo Finance via yfinance (BZ=F, EURUSD=X, GBPUSD=X).")


def render() -> None:
    """Draw the whole panel. app.py calls this inside the panel's tab."""
    st.header("🧾 Inflation & households")
    data = load_data()

    status = " · ".join(f"{k}: {v}" for k, v in data["status"].items())
    if all(v == "live" for v in data["status"].values()):
        st.caption(f"📡 Live data — {status}")
    else:
        st.warning(f"Some data could not be downloaded — {status}")

    if data["inflation"] is None:
        st.error("No inflation data. Check the internet connection, or the saved copies in data/.")
        return
    section_1_inflation(data["inflation"])
    st.divider()
    if data["oil"] is None:
        st.error("No oil data, so Section 2 cannot run.")
        return
    section_2_household(data["inflation"], data["weights"], data["oil"])


if __name__ == "__main__":
    # Run this panel on its own:  python3 -m streamlit run panels/inflation.py
    st.set_page_config(page_title="Inflation & households", layout="wide")
    render()
