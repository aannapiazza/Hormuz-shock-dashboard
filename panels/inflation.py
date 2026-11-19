"""
Panel 4 - Inflation & households
Author: Eleena Golchin

Story: the Hormuz oil shock is reaching consumer prices. Section 1 shows
how far inflation has moved since the war began. Section 2 lets you pick
a future oil price and see what it would mean for inflation and for your
own energy bill.

How this file is organised (same order as the panel template):
    1. SETTINGS  - every data source and number you might want to change
    2. DATA      - download the data (live first, saved copy if that fails)
    3. ANALYSIS  - the maths, as small functions with docstrings
    4. CHARTS    - matplotlib figures (Session 9 conventions)
    5. LAYOUT    - the two sections and their controls (Streamlit)
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

# =============================================================================
# 1. SETTINGS - change data sources here, nowhere else
# =============================================================================

# Countries to offer. Left: the name shown on screen. Right: the ECB code.
# To add one, add a line, e.g. "Portugal": "PT".
COUNTRIES = {
    "Euro area": "U2",
    "Ireland": "IE",
    "Germany": "DE",
    "France": "FR",
    "Italy": "IT",
    "Spain": "ES",
}

# Inflation measures to offer. Right: the ECB HICP item code.
# Full list: https://data.ecb.europa.eu/data/datasets/ICP
MEASURES = {
    "Headline": "000000",
    "Energy": "NRGY00",
    "Food, alcohol & tobacco": "FOOD00",
    "Services": "SERV00",
}

# ECB Data Portal - HICP, annual rate of change (%). No API key needed.
# {countries} and {items} are filled in from the two dictionaries above.
ECB_INFLATION_URL = (
    "https://data-api.ecb.europa.eu/service/data/ICP/"
    "M.{countries}.N.{items}.4.ANR?format=csvdata&startPeriod=2015-01"
)
# ECB - HICP basket weight of energy (parts per 1000), one value per year.
ECB_WEIGHT_URL = (
    "https://data-api.ecb.europa.eu/service/data/ICP/"
    "A.{countries}.N.NRGY00.4.INW?format=csvdata&startPeriod=2020"
)
# FRED - keyless CSV download (Session 10). Change the id to swap series.
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
OIL_SERIES = "MCOILBRENTEU"   # Brent crude, US$ per barrel, monthly
FX_SERIES = "EXUSEU"          # US$ per 1 euro, monthly

# Saved copies, used when the internet or an API is down (Session 11).
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INFLATION_BACKUP = DATA_DIR / "inflation_hicp.csv"
WEIGHT_BACKUP = DATA_DIR / "inflation_energy_weights.csv"
OIL_BACKUP = DATA_DIR / "inflation_brent.csv"
FX_BACKUP = DATA_DIR / "inflation_usd_per_eur.csv"

# Story settings
WAR_START = pd.Timestamp("2026-02-28")   # US-Israel strikes on Iran
ECB_TARGET = 2.0                         # %
DEFAULT_ENERGY_WEIGHT = 9.5              # % of the basket, if ECB weights fail
MAX_LAG_MONTHS = 6                       # longest oil -> bills delay tested


# =============================================================================
# 2. DATA - live download first, saved copy second
# =============================================================================

def load_csv(url: str, backup: Path) -> tuple[pd.DataFrame, str]:
    """Read a CSV from the web and keep a copy; use the copy if the web fails.

    Returns the table and a word describing where it came from:
    "live", "saved copy", or "missing".
    """
    try:
        df = pd.read_csv(url, storage_options={"User-Agent": "UCD-student-dashboard"})
        try:
            DATA_DIR.mkdir(exist_ok=True)
            df.to_csv(backup, index=False)
        except OSError:
            pass  # read-only server: fine, we still have the live data
        return df, "live"
    except Exception:
        if backup.exists():
            return pd.read_csv(backup), "saved copy"
        return pd.DataFrame(), "missing"


def tidy_ecb(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn the ECB's CSV into four clear columns: date, country, measure, value."""
    country_names = {code: name for name, code in COUNTRIES.items()}
    measure_names = {code: name for name, code in MEASURES.items()}
    return pd.DataFrame({
        "date": pd.to_datetime(raw["TIME_PERIOD"]),
        "country": raw["REF_AREA"].map(country_names),
        "measure": raw["ICP_ITEM"].astype(str).str.zfill(6).map(measure_names),
        "value": pd.to_numeric(raw["OBS_VALUE"], errors="coerce"),
    }).dropna()


def tidy_fred(raw: pd.DataFrame, series: str) -> pd.Series:
    """Turn a FRED CSV into a monthly Series indexed by date."""
    date_col = "observation_date" if "observation_date" in raw else raw.columns[0]
    values = pd.to_numeric(raw[series], errors="coerce")
    return pd.Series(values.values, index=pd.to_datetime(raw[date_col]), name=series).dropna()


@st.cache_data(ttl=6 * 60 * 60, show_spinner="Downloading ECB and FRED data...")
def load_data() -> dict:
    """Download everything this panel needs. Cached for 6 hours."""
    countries, items = "+".join(COUNTRIES.values()), "+".join(MEASURES.values())

    raw, s1 = load_csv(ECB_INFLATION_URL.format(countries=countries, items=items),
                       INFLATION_BACKUP)
    inflation = tidy_ecb(raw) if len(raw) else None

    raw, s2 = load_csv(ECB_WEIGHT_URL.format(countries=countries), WEIGHT_BACKUP)
    weights = {}
    if len(raw):
        latest = raw.sort_values("TIME_PERIOD").groupby("REF_AREA").last()
        names = {code: name for name, code in COUNTRIES.items()}
        weights = {names[c]: v / 10 for c, v in latest["OBS_VALUE"].items() if c in names}

    raw_oil, s3 = load_csv(FRED_URL.format(series=OIL_SERIES), OIL_BACKUP)
    raw_fx, s4 = load_csv(FRED_URL.format(series=FX_SERIES), FX_BACKUP)
    oil = None
    if len(raw_oil) and len(raw_fx):
        oil = pd.concat([tidy_fred(raw_oil, OIL_SERIES), tidy_fred(raw_fx, FX_SERIES)],
                        axis=1, join="inner")
        oil.columns = ["brent_usd", "usd_per_eur"]
        oil["brent_eur"] = oil["brent_usd"] / oil["usd_per_eur"]

    status = {"ECB inflation": s1, "ECB weights": s2, "FRED Brent": s3, "FRED euro rate": s4}
    return {"inflation": inflation, "weights": weights, "oil": oil, "status": status}


# =============================================================================
# 3. ANALYSIS
# =============================================================================

def series_for(inflation: pd.DataFrame, country: str, measure: str) -> pd.Series:
    """One country's inflation for one measure, as a monthly Series."""
    rows = inflation[(inflation["country"] == country) & (inflation["measure"] == measure)]
    return rows.set_index("date")["value"].sort_index()


def change_since_war(s: pd.Series) -> tuple[float, float] | None:
    """Latest value and its change since the last month before the war."""
    before = s[s.index < WAR_START]
    if s.empty or before.empty:
        return None
    return s.iloc[-1], s.iloc[-1] - before.iloc[-1]


def oil_change_yoy(oil: pd.DataFrame) -> pd.Series:
    """Percentage change in the euro price of Brent versus 12 months earlier."""
    return (oil["brent_eur"].pct_change(12) * 100).dropna()


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

    pair = pd.concat([energy.rename("energy"), oil_change.shift(best_lag).rename("oil")], sort=True,
                     axis=1).dropna()
    slope, intercept = np.polyfit(pair["oil"], pair["energy"], 1)
    return {"lag": best_lag, "slope": slope, "intercept": intercept,
            "r2": correlations[best_lag] ** 2, "points": pair}


def household_scenario(model: dict, brent_now: float, brent_future: float,
                       energy_now: float, headline_now: float,
                       energy_weight: float, monthly_bill: float) -> dict:
    """Project energy inflation, headline inflation and a household bill.

    Assumes the exchange rate stays the same and that food and services
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

COLOURS = ["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#d62728", "#8c564b"]


def chart_inflation(inflation, countries, measure, start) -> plt.Figure:
    """Section 1 chart: one line per country, war period shaded."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    changes = {}
    for colour, country in zip(COLOURS, countries):
        s = series_for(inflation, country, measure)
        s = s[s.index >= start]
        ax.plot(s.index, s.values, label=country, color=colour,
                linewidth=2.5 if country == countries[0] else 1.5)
        result = change_since_war(s)
        if result:
            changes[country] = result[1]
    ax.axvspan(WAR_START, inflation["date"].max(), color="red", alpha=0.08, label="Since the war")
    ax.axhline(ECB_TARGET, color="grey", linestyle="--", linewidth=1, label="ECB 2% target")
    ax.set_ylabel(f"{measure} inflation, % y/y")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left", ncol=3, fontsize=9)

    if changes:  # a title that states the finding (Session 9)
        top = max(changes, key=changes.get)
        word = "up" if changes[top] >= 0 else "down"
        title = f"{measure} inflation in {top} is {word} {abs(changes[top]):.1f} points since the war began"
    else:
        title = f"{measure} inflation"
    ax.set_title(title, loc="left", fontweight="bold")
    fig.tight_layout()
    return fig


def chart_passthrough(model, scenario, country) -> plt.Figure:
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
    ax.set_xlabel(f"Change in euro oil price vs a year earlier, {model['lag']} months before (%)")
    ax.set_ylabel("Energy inflation, % y/y")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=9)
    ax.set_title(f"In {country}, a 10% oil rise adds about {10 * model['slope']:.1f} points "
                 f"to energy inflation {model['lag']} months later", loc="left", fontweight="bold")
    fig.tight_layout()
    return fig


# =============================================================================
# 5. LAYOUT - two sections, each with its own controls
# =============================================================================

def section_1_inflation(inflation: pd.DataFrame) -> None:
    """Section 1: how far has inflation moved since the war began?"""
    st.subheader("1 · Inflation since the war")
    c1, c2, c3 = st.columns([3, 2, 2])
    countries = c1.multiselect("Countries", list(COUNTRIES), default=["Euro area", "Ireland"])
    measure = c2.selectbox("Measure", list(MEASURES), index=1)
    first_year = int(inflation["date"].dt.year.min())
    start_year = c3.slider("Start year", first_year, 2026, 2021)
    if not countries:
        st.info("Pick at least one country.")
        return

    cols = st.columns(len(countries[:4]))
    for col, country in zip(cols, countries[:4]):
        result = change_since_war(series_for(inflation, country, measure))
        if result:
            col.metric(country, f"{result[0]:.1f}%", f"{result[1]:+.1f} pts since Feb 2026",
                       delta_color="inverse")

    fig = chart_inflation(inflation, countries, measure, pd.Timestamp(f"{start_year}-01-01"))
    st.pyplot(fig)
    plt.close(fig)
    st.caption("Source: ECB Data Portal, HICP annual rate of change. Shaded: since 28 Feb 2026.")


def section_2_household(inflation: pd.DataFrame, weights: dict, oil: pd.DataFrame) -> None:
    """Section 2: what would a new oil price mean for my household?"""
    st.subheader("2 · What it means for your household")
    brent_now = float(oil["brent_usd"].iloc[-1])
    c1, c2, c3 = st.columns(3)
    country = c1.selectbox("Country", list(COUNTRIES), index=1, key="household_country")
    brent_future = c2.slider("Brent oil price in a year ($/barrel)", 40, 200,
                             int(round(brent_now / 5) * 5), step=5)
    bill = c3.number_input("Your monthly energy bill (€)", 0, 2000, 200, step=10)

    energy = series_for(inflation, country, "Energy")
    headline = series_for(inflation, country, "Headline")
    if energy.empty or headline.empty:
        st.warning(f"No energy or headline data for {country}.")
        return
    model = fit_passthrough(energy, oil_change_yoy(oil))
    weight = weights.get(country, DEFAULT_ENERGY_WEIGHT)
    result = household_scenario(model, brent_now, brent_future, energy.iloc[-1],
                                headline.iloc[-1], weight, bill)

    m1, m2, m3 = st.columns(3)
    m1.metric("Energy inflation", f"{result['energy']:.1f}%",
              f"{result['energy'] - energy.iloc[-1]:+.1f} pts vs now", delta_color="inverse")
    m2.metric("Headline inflation", f"{result['headline']:.1f}%",
              f"{result['headline'] - headline.iloc[-1]:+.1f} pts vs now", delta_color="inverse")
    m3.metric("Your energy bill", f"€{bill + result['extra_per_month']:,.0f}/month",
              f"{'+' if result['extra_per_month'] >= 0 else '-'}€{abs(12 * result['extra_per_month']):,.0f} a year",
              delta_color="inverse")

    fig = chart_passthrough(model, result, country)
    st.pyplot(fig)
    plt.close(fig)
    st.caption(
        f"Brent is ${brent_now:.0f} now, so ${brent_future} is a {result['oil_change']:+.0f}% move. "
        "If oil stays flat, energy inflation falls back, because last year's jump drops out "
        f"of the comparison. Energy is {weight:.1f}% of the {country} basket. Model: correlation at delays of "
        f"0–{MAX_LAG_MONTHS} months, then a least-squares line. It assumes the exchange rate "
        "and other prices stay put, so it is a rough guide, not a forecast. "
        "Sources: ECB Data Portal; FRED (MCOILBRENTEU, EXUSEU).")


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
    # Run this panel on its own:  streamlit run panels/inflation.py
    st.set_page_config(page_title="Inflation & households", layout="wide")
    render()
