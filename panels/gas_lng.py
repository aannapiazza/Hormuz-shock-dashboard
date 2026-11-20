"""
Panel 3 - Gas & LNG
Author: Eabha Kelly

Story: Hormuz carries about a fifth of the world's LNG, nearly all of it from
Qatar. This panel shows what closing it has done to gas prices, LNG shipping,
the countries that depend on Qatari gas, and Europe's winter storage.

Run on its own:  python3 -m streamlit run panels/gas_lng.py
Use in app.py:   from panels import gas_lng   then   gas_lng.render()

Data: every chart reads a CSV file in the data/ folder (see DATA_FILES below).
Each file has a source and url column, so every number can be traced.
Daily gas prices are downloaded live from Yahoo Finance (yfinance); if that
fails, the panel uses the saved copy in data/gas_prices_daily.csv.
Interactive charts use Plotly.

How this file is organised (same order as the group's panel template):
    1. SETTINGS  - data files, tickers, colours and fixed numbers you might change
    2. DATA      - read the CSV files and download live prices (saved copy as backup)
    3. ANALYSIS  - the calculations, as small functions with docstrings
    4. CHARTS    - one function per Plotly figure
    5. LAYOUT    - the header, KPI tiles and one function per tab (Streamlit)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ===========================================================================
# 1. SETTINGS - change data sources and fixed numbers here, nowhere else
# ===========================================================================

# ---------- where the data lives ----------
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILES = {
    "prices": "gas_prices_monthly.csv",   # World Bank monthly TTF price
    "benchmarks": "gas_benchmarks.csv",   # Europe vs Asia at four moments
    "tankers": "gas_tankers.csv",         # LNG tankers through Hormuz per month
    "exposure": "gas_exposure.csv",       # dependence on Qatari LNG by country
    "storage": "gas_storage.csv",         # EU storage: 2026, 2025, 5-year average
    "events": "gas_events.csv",           # key war events for the price chart
}

# ---------- live daily prices (Yahoo Finance via yfinance) ----------
DAILY_TICKERS = {
    "ttf_eur_mwh": "TTF=F",     # Dutch TTF gas futures, euros per MWh
    "hh_usd_mmbtu": "NG=F",     # US Henry Hub gas futures, dollars per MMBtu
    "eurusd": "EURUSD=X",       # US dollars per 1 euro
}
DAILY_START = "2025-10-01"                        # a few months before the war, for comparison
DAILY_BACKUP = DATA_DIR / "gas_prices_daily.csv"  # saved copy, used if the download fails
MWH_PER_MMBTU = 0.293071                          # energy conversion: 1 MMBtu = 0.293071 MWh

# ---------- colours (same as the design) ----------
RED, AMBER, TEAL, BLUE, VIOLET, MUTED = "#ff5a4e", "#ffb020", "#2dd4bf", "#5aa9ff", "#a78bfa", "#8fa0bb"
GRID, INK, DARK = "#22314a", "#e8edf5", "#0b1320"
CFG = {"displayModeBar": False}

# ---------- fixed numbers used in the story ----------
TTF_2025_AVG = 11.96          # World Bank, 2025 average TTF, $/MMBtu
USD_PER_EUR_MWH = 0.346       # 1 €/MWh ≈ 0.346 $/MMBtu (approximate FX)
WORLD_AVG_QATAR_SHARE = 19.6  # Qatar's share of world LNG imports, 2024 (EPRINC)
QATAR_CAPACITY_OFFLINE = "16–17%"       # after the 19 March Ras Laffan strike (S&P Global, IEA) – no dataset, so set here
WAR_START = pd.Timestamp("2026-02-28")   # US–Israel strikes on Iran
VOL_WINDOW = 30                          # trading days used for rolling volatility
TRADING_DAYS = 252                       # trading days in a year, to annualise volatility

# Explanations shown when a row of the 2026 vs 2022 chart is clicked
ROW_NOTES = {
    "Before the war (Feb 2026 avg)": "Both benchmarks were around $11/MMBtu in February, before the 28 February strikes.",
    "March 2026 avg": "Prices jumped to their highest monthly average since January 2023. Asia rose more, because most Hormuz LNG normally goes there.",
    "October 2026 avg": "The highest level since December 2022. The Europe–Asia gap has almost closed, because both regions are competing for the same US cargoes.",
    "2022 crisis peak (approx.)": "For comparison: after Russia invaded Ukraine, TTF hit about $90 and Europe paid far more than Asia.",
}


# ===========================================================================
# 2. DATA - read the CSV files; download live prices (saved copy if that fails)
# ===========================================================================

@st.cache_data
def load_data() -> dict:
    """Read every gas CSV from data/ into a pandas DataFrame.

    Returns a dict like {"prices": DataFrame, ...}. A file that is missing
    comes back as None, so the panel can say which one is missing instead
    of crashing. Dates are turned into real dates here, once.
    """
    data = {}
    for key, name in DATA_FILES.items():
        path = DATA_DIR / name
        data[key] = pd.read_csv(path) if path.exists() else None

    if data["prices"] is not None:
        # "2026-03" -> 15 March 2026, so each point sits mid-month on the chart
        data["prices"]["date"] = pd.to_datetime(data["prices"]["month"]) + pd.Timedelta(days=14)
    if data["tankers"] is not None:
        data["tankers"]["label"] = pd.to_datetime(data["tankers"]["month"]).dt.strftime("%b")
    if data["storage"] is not None:
        data["storage"]["date"] = pd.to_datetime(data["storage"]["date"])
    if data["events"] is not None:
        data["events"]["date"] = pd.to_datetime(data["events"]["date"])
    return data


def download_daily_prices() -> pd.DataFrame:
    """Download daily closing prices for European gas, US gas and EUR/USD.

    Returns one row per trading day with columns: date, ttf_eur_mwh,
    hh_usd_mmbtu, eurusd. Gaps (e.g. holidays in one market) are filled with
    the previous day's value; days before all three series start are dropped.
    """
    import yfinance as yf   # imported here so the rest of the panel works without it
    raw = yf.download(list(DAILY_TICKERS.values()), start=DAILY_START,
                      auto_adjust=True, progress=False)["Close"]
    raw = raw.ffill().dropna()
    daily = pd.DataFrame({col: raw[ticker] for col, ticker in DAILY_TICKERS.items()})
    daily.index = pd.to_datetime(daily.index).tz_localize(None)
    daily.index.name = "date"
    return daily.reset_index()


def with_backup(download, backup: Path) -> tuple:
    """Run a download; save a copy if it works, use the copy if it fails.

    Returns (DataFrame or None, status) where status is "live",
    "saved copy" or "missing (...)". Same approach as panels/inflation.py.
    """
    try:
        df = download()
        if df is None or df.empty:
            raise ValueError("no rows returned")
        try:
            df.to_csv(backup, index=False)
        except OSError:
            pass   # read-only folder: fine, we still have the live data
        return df, "live"
    except Exception as error:
        if backup.exists():
            return pd.read_csv(backup, parse_dates=["date"]), "saved copy"
        return None, f"missing ({type(error).__name__})"


@st.cache_data(ttl=6 * 60 * 60, show_spinner="Downloading live gas prices...")
def load_daily_prices() -> tuple:
    """Live daily prices, cached for 6 hours so the page stays fast."""
    return with_backup(download_daily_prices, DAILY_BACKUP)


# ===========================================================================
# 3. ANALYSIS - the calculations behind the numbers on screen
# ===========================================================================

def ttf_in_usd(daily: pd.DataFrame) -> pd.Series:
    """Convert TTF from euros per MWh to dollars per MMBtu, day by day.

    €/MWh × (US$ per €) gives US$/MWh; × 0.293071 MWh per MMBtu gives US$/MMBtu.
    Using each day's own exchange rate keeps it comparable with US prices.
    """
    return daily["ttf_eur_mwh"] * daily["eurusd"] * MWH_PER_MMBTU


def change_since_war(dates: pd.Series, values: pd.Series) -> dict:
    """Compare the last value before the war with the latest value.

    Returns {"before", "latest", "pct", "latest_date"}. "before" is the last
    observation on or before 27 February 2026.
    """
    before = values[dates < WAR_START].iloc[-1]
    latest = values.iloc[-1]
    return {"before": before, "latest": latest, "pct": (latest / before - 1) * 100,
            "latest_date": dates.iloc[-1]}


def europe_us_gap(daily: pd.DataFrame) -> pd.DataFrame:
    """Daily gap between European (TTF) and US (Henry Hub) gas, both in $/MMBtu.

    Adds three columns: ttf_usd, gap_usd (TTF minus Henry Hub) and ratio
    (how many times more Europe pays).
    """
    out = daily[["date"]].copy()
    out["ttf_usd"] = ttf_in_usd(daily)
    out["hh_usd"] = daily["hh_usd_mmbtu"]
    out["gap_usd"] = out["ttf_usd"] - out["hh_usd"]
    out["ratio"] = out["ttf_usd"] / out["hh_usd"]
    return out


def rolling_volatility(daily: pd.DataFrame, window: int = VOL_WINDOW) -> pd.Series:
    """Annualised volatility of TTF, in %, over a rolling window of trading days.

    Uses daily log returns, ln(price today / price yesterday). Their standard
    deviation over the window, times sqrt(252), is the usual way to express
    how jumpy a price is over a year.
    """
    log_returns = np.log(daily["ttf_eur_mwh"] / daily["ttf_eur_mwh"].shift(1))
    return log_returns.rolling(window).std() * np.sqrt(TRADING_DAYS) * 100


def monthly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """Average the daily TTF price ($/MMBtu) into calendar months.

    Used to cross-check the World Bank monthly series against Yahoo Finance.
    """
    s = pd.Series(ttf_in_usd(daily).values, index=daily["date"])
    return s.resample("MS").mean().rename("ttf_usd").reset_index()


def tanker_recovery(tankers: pd.DataFrame) -> dict:
    """Latest month's LNG tanker count as a share of the pre-war month (Feb 2026)."""
    prewar = tankers.loc[tankers["month"] == "2026-02", "tankers"].iloc[0]
    last = tankers.iloc[-1]
    return {"month": last["label"], "count": int(last["tankers"]), "prewar": int(prewar),
            "pct": last["tankers"] / prewar * 100}


def gas_at_risk(exposure: pd.DataFrame) -> dict:
    """Qatari LNG volumes by region, and the country with the most at risk."""
    by_region = exposure.groupby("region")["from_qatar_bcfd"].sum()
    top = exposure.sort_values("from_qatar_bcfd", ascending=False).iloc[0]
    most_dependent = exposure.sort_values("qatar_share_pct", ascending=False).iloc[0]
    return {"asia_share": by_region.get("Asia", 0) / by_region.sum() * 100,
            "top_volume": top["country"], "top_volume_bcfd": top["from_qatar_bcfd"],
            "most_dependent": most_dependent["country"], "most_dependent_pct": most_dependent["qatar_share_pct"]}


def benchmark_change(bench: pd.DataFrame, column: str) -> dict:
    """Latest 2026 benchmark (October average) compared with before the war.

    Reads the first row (before the war) and the last 2026 row of
    gas_benchmarks.csv, so the tile updates if the file gets a newer month.
    """
    rows_2026 = bench[bench["period"].str.contains("2026")]
    first, last = rows_2026.iloc[0], rows_2026.iloc[-1]
    return {"label": last["period"].replace(" 2026 avg", ""), "latest": last[column], "before": first[column],
            "pct": (last[column] / first[column] - 1) * 100}


def data_as_of(data: dict) -> str:
    """Build the 'Data as of …' label from the newest date in the data itself."""
    newest = data["storage"]["date"].max()
    last_month = pd.to_datetime(data["prices"]["month"]).max()
    return f"Data as of {newest:%d %B %Y} · monthly prices to {last_month:%B %Y}"


def storage_position(storage: pd.DataFrame) -> dict:
    """Where EU storage stands: latest level, gap to the 5-year average, and drawdown.

    The drawdown rate is how many percentage points a week storage has fallen
    since its 2026 peak.
    """
    s26 = storage[storage["series"] == "2026"].sort_values("date")
    avg = storage[storage["series"] == "5-year average"].set_index("date")["pct_full"]
    latest = s26.iloc[-1]
    peak = s26.loc[s26["pct_full"].idxmax()]
    weeks = max((latest["date"] - peak["date"]).days / 7, 1e-9)
    gap = latest["pct_full"] - avg.get(latest["date"], np.nan)
    return {"latest": latest["pct_full"], "latest_date": latest["date"], "gap_to_avg": gap,
            "peak": peak["pct_full"], "peak_date": peak["date"],
            "drawdown_per_week": (peak["pct_full"] - latest["pct_full"]) / weeks}


# ===========================================================================
# 4. CHARTS - one function per Plotly figure (dark theme)
# ===========================================================================

def _layout(fig, **kw):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color=INK, size=13),
        hoverlabel=dict(bgcolor=DARK, bordercolor="#26354f"), **kw)
    return fig


def _add_events(fig, events, y_top):
    for _, ev in events.iterrows():
        d = ev["date"].strftime("%Y-%m-%d")
        fig.add_vline(x=d, line=dict(color="#33445f", width=1, dash="dot"))
        fig.add_annotation(x=d, y=y_top, text=ev["event"], showarrow=False, textangle=-90,
                           xanchor="right", yanchor="top", font=dict(size=10, color=MUTED))


def price_path_chart(prices, events, show_events, daily=None):
    y = prices["ttf_usd_per_mmbtu"]
    chg = y.pct_change() * 100          # % change from the month before
    fig = go.Figure(go.Scatter(
        x=prices["date"], y=y, mode="lines+markers", line=dict(color=BLUE, width=3, shape="spline", smoothing=0.6),
        marker=dict(size=10, color=[TEAL if c < 0 else BLUE for c in chg.fillna(0)], line=dict(color=DARK, width=1.5)),
        fill="tozeroy", fillcolor="rgba(90,169,255,.10)",
        customdata=["—" if pd.isna(c) else (f"▲ +{c:.1f}%" if c >= 0 else f"▼ {c:.1f}%") + " vs previous month" for c in chg],
        hovertemplate="<b>%{x|%B %Y}: $%{y:.2f}/MMBtu</b><br>%{customdata}<extra></extra>"))
    y_max, x_end = 35, prices["date"].max() + pd.Timedelta(days=20)
    if daily is not None:       # thin line of live daily prices behind the monthly averages
        daily_usd = ttf_in_usd(daily)
        fig.add_trace(go.Scatter(x=daily["date"], y=daily_usd, mode="lines", name="Daily TTF (live)",
                                 line=dict(color="rgba(167,139,250,.75)", width=1.2),
                                 hovertemplate="%{x|%d %b %Y}: $%{y:.2f}/MMBtu (daily)<extra></extra>"))
        y_max = max(y_max, float(daily_usd.max()) * 1.1)
        x_end = max(x_end, daily["date"].max() + pd.Timedelta(days=5))
    # Price labels as annotations (not trace text), so they don't clutter the slider strip
    for d, v in zip(prices["date"], y):
        fig.add_annotation(x=d, y=v, text=f"${v:.1f}", showarrow=False, yshift=14, font=dict(size=11, color="#c7d2e3"))
    fig.add_hline(y=TTF_2025_AVG, line=dict(color=TEAL, dash="dash", width=1.5),
                  annotation_text=f"2025 average ${TTF_2025_AVG}", annotation_font_color=TEAL, annotation_position="bottom right")
    if show_events and events is not None:
        _add_events(fig, events, y_max - 1)
    return _layout(fig, height=430, margin=dict(l=10, r=20, t=20, b=30), hovermode="x", showlegend=False,
                   xaxis=dict(type="date", range=["2025-12-20", x_end], gridcolor=GRID, tickformat="%b", dtick="M1",
                              rangeslider=dict(visible=True, thickness=0.06, bgcolor="#121c2d")),
                   yaxis=dict(title=dict(text="$ per MMBtu", standoff=12), gridcolor=GRID, range=[0, y_max], fixedrange=True, automargin=True))


def europe_us_chart(gap: pd.DataFrame, vol: pd.Series, show: str, show_vol: bool):
    """Daily European vs US gas prices, with the gap shaded; optional volatility panel below."""
    rows = 2 if show_vol else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        row_heights=[0.7, 0.3] if show_vol else [1.0])
    if show == "Prices and gap ($/MMBtu)":
        fig.add_trace(go.Scatter(x=gap["date"], y=gap["hh_usd"], name="US (Henry Hub)", mode="lines",
                                 line=dict(color=TEAL, width=2),
                                 hovertemplate="US: $%{y:.2f}<extra></extra>"), row=1, col=1)
        fig.add_trace(go.Scatter(x=gap["date"], y=gap["ttf_usd"], name="Europe (TTF)", mode="lines",
                                 line=dict(color=BLUE, width=2), fill="tonexty", fillcolor="rgba(255,90,78,.15)",
                                 customdata=gap[["gap_usd"]].values,
                                 hovertemplate="Europe: $%{y:.2f}<br>Gap: $%{customdata[0]:.2f}<extra></extra>"), row=1, col=1)
        fig.update_yaxes(title_text="$ per MMBtu", rangemode="tozero", row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=gap["date"], y=gap["ratio"], name="Europe ÷ US", mode="lines",
                                 line=dict(color=RED, width=2.5),
                                 hovertemplate="Europe pays %{y:.1f}× the US price<extra></extra>"), row=1, col=1)
        fig.add_hline(y=1, line=dict(color=MUTED, dash="dot"), row=1, col=1)
        fig.update_yaxes(title_text="Times the US price", rangemode="tozero", ticksuffix="×", row=1, col=1)
    if WAR_START >= gap["date"].min():
        fig.add_vline(x=WAR_START.strftime("%Y-%m-%d"), line=dict(color=MUTED, dash="dot"))
        fig.add_annotation(x=WAR_START.strftime("%Y-%m-%d"), y=1, yref="paper", text="War begins", showarrow=False,
                           xanchor="left", yanchor="top", xshift=4, font=dict(size=11, color=MUTED))
    if show_vol:
        fig.add_trace(go.Scatter(x=gap["date"], y=vol, name=f"Volatility ({VOL_WINDOW}-day)", mode="lines",
                                 line=dict(color=AMBER, width=1.8), fill="tozeroy", fillcolor="rgba(255,176,32,.10)",
                                 hovertemplate="Volatility: %{y:.0f}%<extra></extra>"), row=2, col=1)
        fig.update_yaxes(title_text="Volatility", ticksuffix="%", rangemode="tozero", row=2, col=1)
    fig.update_xaxes(gridcolor=GRID, tickformat="%b %Y")
    fig.update_yaxes(gridcolor=GRID, automargin=True)
    return _layout(fig, height=520 if show_vol else 420, margin=dict(l=10, r=20, t=30, b=30),
                   hovermode="x unified", legend=dict(orientation="h", y=1.08, x=0))


def _convert(values, unit):
    values = list(values)
    if unit == "€/MWh":
        return [v / USD_PER_EUR_MWH for v in values]
    if unit == "% vs pre-war":
        return [(v / values[0] - 1) * 100 for v in values]
    return values


def _selected_row(rows):
    try:
        pts = st.session_state["gas_dumb"]["selection"]["points"]
        if pts:
            return rows.index(pts[0]["y"])
    except (KeyError, TypeError, ValueError, IndexError):
        pass
    return None


def dumbbell_chart(bench, unit, highlight):
    rows = list(bench["period"])
    ttf, jkm = _convert(bench["ttf_usd_per_mmbtu"], unit), _convert(bench["jkm_usd_per_mmbtu"], unit)
    fig = go.Figure()
    for i, row in enumerate(rows):
        fig.add_trace(go.Scatter(x=[ttf[i], jkm[i]], y=[row, row], mode="lines", hoverinfo="skip", showlegend=False,
                                 line=dict(color=MUTED if i == highlight else "#33445f", width=9 if i == highlight else 6)))
    opac = [1 if highlight is None or i == highlight else 0.35 for i in range(len(rows))]
    fmt = "%{x:+.0f}%" if unit == "% vs pre-war" else "%{x:.1f} " + unit
    fig.add_trace(go.Scatter(x=ttf, y=rows, mode="markers", name="Europe (TTF)", hovertemplate="TTF: " + fmt + "<extra></extra>",
                             marker=dict(size=16, color=BLUE, opacity=opac, line=dict(color=DARK, width=2))))
    fig.add_trace(go.Scatter(x=jkm, y=rows, mode="markers", name="Asia (JKM)", hovertemplate="JKM: " + fmt + "<extra></extra>",
                             marker=dict(size=16, color=VIOLET, symbol="diamond", opacity=opac, line=dict(color=DARK, width=2))))
    fig.add_shape(type="rect", xref="paper", yref="y", x0=0, x1=1, y0=len(rows) - 1.5, y1=len(rows) - 0.5,
                  fillcolor="rgba(255,255,255,.03)", line_width=0)
    for i, row in enumerate(rows):          # dots overlap when the two prices are almost equal: say so
        close = abs(ttf[i] - jkm[i]) <= 0.05 * max(abs(ttf[i]), abs(jkm[i]), 1)   # within 5% of each other
        if close and not (unit == "% vs pre-war" and i == 0):
            both = f"{ttf[i]:+.0f}%" if unit == "% vs pre-war" else f"≈{ttf[i]:.0f}"
            fig.add_annotation(x=max(ttf[i], jkm[i]), y=row, text=f"TTF & JKM both {both}", showarrow=False,
                               xanchor="left", xshift=16, yshift=12, font=dict(size=11, color=MUTED))
    return _layout(fig, height=380, margin=dict(l=10, r=20, t=10, b=60), clickmode="event+select",
                   xaxis=dict(title=unit, gridcolor=GRID, rangemode="tozero", ticksuffix="%" if unit == "% vs pre-war" else ""),
                   yaxis=dict(autorange="reversed", fixedrange=True, automargin=True, gridcolor=GRID), legend=dict(orientation="h", y=-0.22, x=0))


def transits_chart(tankers, as_pct):
    prewar = tankers.loc[tankers["month"] == "2026-02", "tankers"].iloc[0]   # February = last normal month
    counts = tankers["tankers"]
    vals = counts / prewar * 100 if as_pct else counts
    colours = [MUTED if m == "2026-02" else (AMBER if t == "Kpler" else RED)
               for m, t in zip(tankers["month"], tankers["tracker"])]
    fig = go.Figure(go.Bar(
        x=tankers["label"], y=vals, marker_color=colours, showlegend=False,
        text=[f"{v:.0f}%" if as_pct else str(c) for v, c in zip(vals, counts)], textposition="outside",
        customdata=tankers[["tracker", "note"]].values,
        hovertemplate="<b>%{x}: %{text}</b><br>%{customdata[1]}<br><i>Source: %{customdata[0]}</i><extra></extra>"))
    ref = 100 if as_pct else prewar
    fig.add_hline(y=ref, line=dict(color=TEAL, dash="dash", width=1.5),
                  annotation_text="Pre-war level", annotation_font_color=TEAL, annotation_position="top right")
    for name, c in [("Kpler (all LNG-carrier transits)", AMBER), ("S&P Global (laden tankers exiting)", RED)]:
        fig.add_trace(go.Bar(x=[None], y=[None], name=name, marker_color=c, showlegend=True))
    return _layout(fig, height=400, margin=dict(l=10, r=20, t=30, b=40), showlegend=True, barmode="overlay",
                   legend=dict(orientation="h", y=-0.15, x=0),
                   yaxis=dict(title=dict(text="% of pre-war" if as_pct else "LNG tankers per month", standoff=12), gridcolor=GRID, automargin=True,
                              range=[0, 115 if as_pct else prewar * 1.15], ticksuffix="%" if as_pct else ""),
                   xaxis=dict(fixedrange=True))


def exposure_chart(exposure, view, regions, metric):
    rows = exposure[exposure["region"].isin(regions)]
    colour = {"Asia": VIOLET, "Europe": BLUE}
    if view == "Ranking":
        col = "qatar_share_pct" if metric == "Share of LNG imports from Qatar" else "from_qatar_bcfd"
        rows = rows.sort_values(col)
        fig = go.Figure(go.Bar(
            y=rows["country"], x=rows[col], orientation="h",
            marker_color=[colour[r] for r in rows["region"]],
            text=[f"{v:.0f}%" if col == "qatar_share_pct" else f"{v:.1f}" for v in rows[col]], textposition="outside",
            customdata=rows[["region", "total_lng_imports_bcfd", "from_qatar_bcfd", "qatar_share_pct"]].values,
            hovertemplate="<b>%{y}</b> (%{customdata[0]})<br>Qatar share: %{customdata[3]:.1f}%<br>"
                          "From Qatar: %{customdata[2]:.1f} Bcf/d of %{customdata[1]:.1f} Bcf/d total<extra></extra>"))
        return _layout(fig, height=440, margin=dict(l=10, r=40, t=10, b=40),
                       xaxis=dict(title="% of LNG imports from Qatar" if col == "qatar_share_pct" else "Bcf/d from Qatar",
                                  gridcolor=GRID, ticksuffix="%" if col == "qatar_share_pct" else ""),
                       yaxis=dict(fixedrange=True, automargin=True, ticksuffix="  "))
    # Bubble view: x = how big an LNG buyer, y = how dependent on Qatar, size = volume at risk
    fig = go.Figure()
    for reg in regions:
        rr = rows[rows["region"] == reg]
        fig.add_trace(go.Scatter(
            x=rr["total_lng_imports_bcfd"], y=rr["qatar_share_pct"], mode="markers+text", name=reg,
            text=rr["country"], textposition="top center", textfont=dict(size=11, color="#c7d2e3"),
            marker=dict(size=[max(10, v * 38) for v in rr["from_qatar_bcfd"]], color=colour[reg], opacity=0.75,
                        line=dict(color=DARK, width=1.5)),
            customdata=rr[["from_qatar_bcfd"]].values,
            hovertemplate="<b>%{text}</b><br>Total LNG imports: %{x:.1f} Bcf/d<br>Qatar share: %{y:.1f}%<br>"
                          "At risk: %{customdata[0]:.1f} Bcf/d<extra></extra>"))
    fig.add_hline(y=WORLD_AVG_QATAR_SHARE, line=dict(color=MUTED, dash="dot"),
                  annotation_text=f"World average {WORLD_AVG_QATAR_SHARE}%",
                  annotation_font_color=MUTED, annotation_position="bottom right")
    return _layout(fig, height=440, margin=dict(l=10, r=20, t=10, b=40), legend=dict(orientation="h", y=1.06, x=0),
                   xaxis=dict(title=dict(text="Total LNG imports (Bcf/d) – how big a buyer", standoff=10), type="log", gridcolor=GRID, automargin=True),
                   yaxis=dict(title=dict(text="% from Qatar – how exposed", standoff=12), gridcolor=GRID, range=[-5, 100], ticksuffix="%", automargin=True))


def storage_chart(storage, show_2025, show_5yr, show_targets):
    def series(name):
        return storage[storage["series"] == name].sort_values("date")
    fig = go.Figure()
    if show_5yr:
        s = series("5-year average")
        fig.add_trace(go.Scatter(x=s["date"], y=s["pct_full"], name="5-year average",
                                 mode="lines+markers", line=dict(color=MUTED, dash="dash", width=2), marker=dict(size=7),
                                 hovertemplate="5-yr avg: %{y:.1f}%<extra></extra>"))
    if show_2025:
        s = series("2025 (same date)")
        fig.add_trace(go.Scatter(x=s["date"], y=s["pct_full"], name="Same date in 2025",
                                 mode="lines+markers", line=dict(color=AMBER, width=2), marker=dict(size=7),
                                 hovertemplate="2025: %{y:.1f}%<extra></extra>"))
    s26 = series("2026")
    fig.add_trace(go.Scatter(x=s26["date"], y=s26["pct_full"], name="2026",
                             mode="lines+markers", line=dict(color=RED, width=3.5), marker=dict(size=9),
                             fill="tozeroy", fillcolor="rgba(255,90,78,.08)",
                             hovertemplate="<b>2026: %{y:.1f}%</b><extra></extra>"))
    if show_targets:
        fig.add_hline(y=90, line=dict(color=TEAL, dash="dot"), annotation_text="EU target 90%",
                      annotation_font_color=TEAL, annotation_position="top left")
        fig.add_hline(y=80, line=dict(color=TEAL, dash="dot", width=1), annotation_text="Flexible target 80%",
                      annotation_font_color=TEAL, annotation_position="bottom left")
    peak = s26.loc[s26["pct_full"].idxmax()]      # highest point of 2026, found from the data
    first = s26.iloc[0]
    fig.add_annotation(x=peak["date"], y=peak["pct_full"], text=f"Peak {peak['pct_full']:.0f}% ({peak['date']:%d %b})",
                       showarrow=True, arrowcolor=MUTED, ax=-60, ay=-35, font=dict(size=11, color=INK))
    fig.add_annotation(x=first["date"], y=first["pct_full"], text=f"Summer starts at {first['pct_full']:.0f}%",
                       showarrow=True, arrowcolor=MUTED, ax=70, ay=45, font=dict(size=11, color=INK))
    return _layout(fig, height=420, margin=dict(l=10, r=20, t=10, b=40), hovermode="x unified",
                   xaxis=dict(type="date", range=["2026-03-20", "2026-11-25"], tickformat="%b", gridcolor=GRID),
                   yaxis=dict(title=dict(text="% full", standoff=12), range=[0, 100], ticksuffix="%", gridcolor=GRID, automargin=True),
                   legend=dict(orientation="h", y=1.08, x=0))


def sunburst_chart():
    fig = go.Figure(go.Sunburst(
        ids=["all", "hz", "nh", "asia", "oth"],
        labels=["World LNG trade", "Via Hormuz<br>~20%", "Not via Hormuz<br>~80%", "To Asia<br>83%", "Europe &<br>other 17%"],
        parents=["", "all", "all", "hz", "hz"], values=[100, 20, 80, 16.6, 3.4], branchvalues="total",
        marker=dict(colors=["#121c2d", "#ff6b5e", "#2c3d5c", "#6fb4ff", "#9aabc6"], line=dict(color="#121c2d", width=1)),
        rotation=90, sort=False, textfont=dict(size=13, color=INK), insidetextorientation="horizontal",
        hovertemplate="<b>%{label}</b><br>%{value:.1f}% of world LNG trade<extra></extra>"))
    return _layout(fig, height=380, margin=dict(l=4, r=4, t=4, b=4), uniformtext=dict(minsize=10, mode="show"))


# ===========================================================================
# 5. LAYOUT - header, KPI tiles and one function per tab
# ===========================================================================

def section_prices(data: dict, daily, daily_status: str) -> None:
    """Tab 1: monthly price path, live daily prices and the 2026 vs 2022 comparison."""
    st.subheader("European gas prices through the war")
    c1, c2 = st.columns(2)
    show_ev = c1.toggle("Show key events", value=True, key="gas_ev")
    show_daily = c2.toggle("Show daily prices (live)", value=True, key="gas_daily", disabled=daily is None)
    st.plotly_chart(price_path_chart(data["prices"], data["events"], show_ev, daily if show_daily else None),
                    width="stretch", theme=None, config=CFG)
    if daily is not None:
        last = daily.iloc[-1]
        st.caption(f"Latest daily close ({last['date']:%d %b %Y}): TTF €{last['ttf_eur_mwh']:.2f}/MWh "
                   f"≈ ${ttf_in_usd(daily).iloc[-1]:.2f}/MMBtu · US Henry Hub ${last['hh_usd_mmbtu']:.2f}/MMBtu "
                   f"({daily_status}).")

        # ---- What the daily data says (calculated in the ANALYSIS section) ----
        war = change_since_war(daily["date"], ttf_in_usd(daily))
        gap = europe_us_gap(daily).iloc[-1]
        vol = rolling_volatility(daily)
        prewar_vol = vol[(daily["date"] >= "2026-01-01") & (daily["date"] < WAR_START)].mean()
        a1, a2, a3 = st.columns(3)
        a1.metric("European gas since the war began", f"{war['pct']:+.0f}%",
                  help=f"Daily TTF: ${war['before']:.2f}/MMBtu on the last day before 28 Feb, "
                       f"${war['latest']:.2f} on {war['latest_date']:%d %b}.")
        a2.metric("Europe pays vs the US", f"{gap['ratio']:.1f}×",
                  help=f"Latest gap: ${gap['gap_usd']:.2f}/MMBtu (TTF ${gap['ttf_usd']:.2f} minus Henry Hub ${gap['hh_usd']:.2f}).")
        a3.metric(f"Price volatility ({VOL_WINDOW}-day)", f"{vol.iloc[-1]:.0f}%",
                  delta=f"{vol.iloc[-1] - prewar_vol:+.0f} pts vs Jan–Feb", delta_color="inverse",
                  help="Annualised standard deviation of daily TTF returns. Higher = a jumpier, riskier market.")
        check = monthly_from_daily(daily).merge(
            data["prices"].assign(month_start=pd.to_datetime(data["prices"]["month"])),
            left_on="date", right_on="month_start")
        if len(check):
            diff = (check["ttf_usd"] - check["ttf_usd_per_mmbtu"]).abs().mean()
            st.caption(f"Cross-check: averaging the Yahoo Finance daily prices by month gives values within "
                       f"${diff:.2f}/MMBtu of the World Bank's monthly figures, on average, over {len(check)} months.")
    st.caption("Monthly average of the European benchmark (Dutch TTF), from the World Bank (data/gas_prices_monthly.csv). "
               "Hover a month for the price and the change from the month before; drag the slider under the chart to zoom in. "
               "The thin violet line is daily TTF from Yahoo Finance (TTF=F), converted to $/MMBtu with each day's EUR/USD rate.")

    st.subheader("How big is this gas shock? 2026 vs 2022")
    bench = data["benchmarks"]
    rows = list(bench["period"])
    unit = st.radio("Units", ["$/MMBtu", "€/MWh", "% vs pre-war"], horizontal=True, key="gas_unit")
    row = _selected_row(rows)
    st.plotly_chart(dumbbell_chart(bench, unit, row), width="stretch", theme=None,
                    on_select="rerun", selection_mode="points", key="gas_dumb", config=CFG)
    if row is None:
        st.caption("👆 Click a dot to compare Europe and Asia at that moment.")
    else:
        r = bench.iloc[row]
        ttf, jkm = r["ttf_usd_per_mmbtu"], r["jkm_usd_per_mmbtu"]
        gap = jkm - ttf
        who = "Asia paid more" if gap > 0.05 else "Europe paid more" if gap < -0.05 else "About level"
        st.info(f"**{r['period']}**: TTF ${ttf}/MMBtu · JKM ${jkm}/MMBtu · **{who}**"
                f"{f' (${abs(gap):.2f})' if abs(gap) > 0.05 else ''}\n\n{ROW_NOTES.get(r['period'], r['note'])}")


def section_europe_us(data: dict, daily, daily_status: str) -> None:
    """Tab 2: daily Europe vs US prices with a date-range slider."""
    st.subheader("Two gas markets: Europe vs the US")
    if daily is None:
        st.info("Live daily prices are unavailable right now, so this chart can't be drawn. "
                "It needs data/gas_prices_daily.csv or an internet connection.")
    else:
        gap_all = europe_us_gap(daily)
        vol_all = rolling_volatility(daily)
        first, last_day = gap_all["date"].min().date(), gap_all["date"].max().date()
        start_default = max(first, pd.Timestamp("2026-01-01").date())
        c1, c2 = st.columns([2, 1])
        start, end = c1.slider("Period", min_value=first, max_value=last_day,
                               value=(start_default, last_day), format="DD MMM YYYY", key="gas_range")
        show = c2.radio("Show", ["Prices and gap ($/MMBtu)", "Ratio (Europe ÷ US)"], key="gas_show")
        show_vol = st.toggle("Add volatility panel", value=False, key="gas_vol")

        in_range = (gap_all["date"].dt.date >= start) & (gap_all["date"].dt.date <= end)
        gap, vol = gap_all[in_range], vol_all[in_range]
        if len(gap) < 2:
            st.warning("Pick a longer period.")
        else:
            st.plotly_chart(europe_us_chart(gap, vol, show, show_vol), width="stretch", theme=None, config=CFG)
            widest = gap.loc[gap["gap_usd"].idxmax()]
            m1, m2, m3 = st.columns(3)
            m1.metric("Average gap in this period", f"${gap['gap_usd'].mean():.2f}/MMBtu")
            m2.metric("Europe paid on average", f"{gap['ratio'].mean():.1f}× the US price")
            m3.metric("Widest gap", f"${widest['gap_usd']:.2f}", help=f"On {widest['date']:%d %b %Y}.")
            st.caption("Daily closing prices from Yahoo Finance (TTF=F, NG=F, EURUSD=X), with TTF converted to $/MMBtu "
                       "using each day's exchange rate. The shaded area is the gap Europe pays above the US. "
                       f"Volatility is the annualised {VOL_WINDOW}-day standard deviation of daily TTF returns. "
                       "Drag the ends of the Period slider to focus on any part of the war; the figures below the chart "
                       "update for the period you pick.")


def section_supply(data: dict, daily, daily_status: str) -> None:
    """Tab 3: LNG tankers through Hormuz and where Hormuz LNG goes."""
    left, right = st.columns([3, 2])
    with left:
        st.subheader("LNG tankers through Hormuz each month")
        as_pct = st.toggle("Show as % of pre-war traffic", key="gas_pct")
        st.plotly_chart(transits_chart(data["tankers"], as_pct), width="stretch", theme=None, config=CFG)
        rec = tanker_recovery(data["tankers"])
        st.markdown(f"**{rec['month']}: {rec['count']} tankers, {rec['pct']:.0f}% of the pre-war {rec['prewar']}.**")
        st.caption("Hover a bar for what happened that month (data/gas_tankers.csv). Two trackers are used: Kpler counts "
                   "every LNG-carrier transit and S&P Global counts laden tankers leaving, so the bars aren't strictly "
                   "like-for-like. Some ships cross with transponders off, so true numbers may be a little higher.")
    with right:
        st.subheader("Where the world's LNG comes from, and where Hormuz LNG goes")
        st.caption("Click a segment to zoom in, and click the centre to zoom back out. EIA estimates for 2024.")
        st.plotly_chart(sunburst_chart(), width="stretch", theme=None, config=CFG)


def section_exposure(data: dict, daily, daily_status: str) -> None:
    """Tab 4: which countries depend most on Qatari LNG."""
    st.subheader("Which countries depend most on Qatari LNG?")
    c1, c2, c3 = st.columns([1.2, 1.2, 1.6])
    view = c1.radio("View", ["Ranking", "Bubble map"], horizontal=True, key="gas_view")
    regions = c2.multiselect("Regions", ["Asia", "Europe"], default=["Asia", "Europe"], key="gas_reg")
    metric = c3.radio("Rank by", ["Share of LNG imports from Qatar", "Volume from Qatar (Bcf/d)"],
                      horizontal=True, key="gas_metric", disabled=(view != "Ranking"))
    if regions:
        st.plotly_chart(exposure_chart(data["exposure"], view, regions, metric), width="stretch", theme=None, config=CFG)
    else:
        st.warning("Pick at least one region.")
    risk = gas_at_risk(data["exposure"])
    st.markdown(f"**Asia takes {risk['asia_share']:.0f}% of the Qatari LNG in this table. "
                f"{risk['top_volume']} has the most at risk ({risk['top_volume_bcfd']:.1f} Bcf/d); "
                f"{risk['most_dependent']} is the most dependent ({risk['most_dependent_pct']:.0f}% of its LNG).**")
    st.caption("2024 annual averages (Energy Institute, via EPRINC; data/gas_exposure.csv). In the bubble map, further right "
               "means a bigger LNG buyer, higher up means more dependent on Qatar, and a bigger bubble means more gas at risk. "
               "Pakistan is the most exposed. China has the most gas at risk. Japan buys a lot of LNG but little of it from Qatar.")


def section_storage(data: dict, daily, daily_status: str) -> None:
    """Tab 5: EU gas storage against 2025, the 5-year average and EU targets."""
    st.subheader("EU gas storage: refilling fell short")
    c1, c2, c3 = st.columns(3)
    s25 = c1.checkbox("Compare with 2025", value=True, key="gas_s25")
    s5 = c2.checkbox("Show 5-year average", value=True, key="gas_s5")
    tg = c3.checkbox("Show EU targets", value=True, key="gas_tg")
    st.plotly_chart(storage_chart(data["storage"], s25, s5, tg), width="stretch", theme=None, config=CFG)
    pos = storage_position(data["storage"])
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Storage on {pos['latest_date']:%d %b}", f"{pos['latest']:.1f}%")
    m2.metric("Gap to 5-year average", f"{pos['gap_to_avg']:+.1f} pts")
    m3.metric(f"Drawdown since {pos['peak_date']:%d %b} peak", f"{pos['drawdown_per_week']:.1f} pts/week",
              help=f"From {pos['peak']:.1f}% to {pos['latest']:.1f}%.")
    st.caption("Hover anywhere to compare years on the same date. GIE AGSI data as reported by Argus, S&P Global, GMK Center "
               "and TASS (data/gas_storage.csv; the 'how' column marks which values are derived). Europe started summer at "
               "only 28%, never reached the 80% flexible target, and by mid-November was drawing down faster than usual.")


def render() -> None:
    """Draw the whole panel. app.py calls this inside the panel's tab."""
    st.header("🔥 Gas & LNG: Qatar's exports cut off")
    st.caption("Nearly all of Qatar's LNG, about a fifth of world supply, has to pass through Hormuz. "
               "Then the 19 March strike on Ras Laffan knocked out part of its capacity for years.")

    data = load_data()
    missing = [DATA_FILES[k] for k, df in data.items() if df is None]
    if missing:
        st.error(f"Missing data file(s) in data/: {', '.join(missing)}. Check the files are in the repo.")
        return
    daily, daily_status = load_daily_prices()
    live_note = {"live": "📡 live daily prices from Yahoo Finance",
                 "saved copy": "💾 daily prices from saved copy (download failed)"}.get(daily_status, "⚠️ daily prices unavailable")
    st.markdown(f"`{data_as_of(data)}` · 💾 {len(DATA_FILES)} data files loaded from `data/` · {live_note}")

    # ---- KPI tiles: calculated from the data (see ANALYSIS) ----
    rec = tanker_recovery(data["tankers"])
    jkm = benchmark_change(data["benchmarks"], "jkm_usd_per_mmbtu")
    pos = storage_position(data["storage"])
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Qatari LNG capacity offline", QATAR_CAPACITY_OFFLINE,
              help="After the 19 March strike on Ras Laffan. This damage lasts even if the strait reopens. Sources: S&P Global, IEA.")
    k1.caption("For about 4 years")
    k2.metric(f"Hormuz LNG tankers, {rec['month']}", f"{rec['count']}",
              help=f"From data/gas_tankers.csv. Pre-war month (Feb 2026): {rec['prewar']}.")
    k2.caption(f"{rec['pct']:.0f}% of the pre-war {rec['prewar']} a month")
    k3.metric(f"Asian LNG (JKM), {jkm['label']} avg", f"${jkm['latest']:.2f}",
              delta=f"{jkm['pct']:+.0f}% vs before the war", delta_color="inverse",
              help=f"Per MMBtu, from data/gas_benchmarks.csv: ${jkm['before']:.2f} before the war. Source: EIA, citing Bloomberg.")
    k4.metric(f"EU gas storage, {pos['latest_date']:%d %b}", f"{pos['latest']:.1f}%",
              delta=f"{pos['gap_to_avg']:+.0f} pts vs 5-yr avg", delta_color="normal",
              help="From data/gas_storage.csv (GIE AGSI data). Lowest for the date since records began in 2011.")

    tabs = st.tabs(["📈 Prices", "⚖️ Europe vs US", "🚢 Supply & shipping", "🌍 Who's exposed", "🏭 Europe's winter"])
    sections = [section_prices, section_europe_us, section_supply, section_exposure, section_storage]
    for tab, section in zip(tabs, sections):
        with tab:
            section(data, daily, daily_status)

    # ---- Takeaway + sources ----
    st.success("**Takeaway:** gas prices are at their highest since 2022, and LNG traffic through Hormuz is only a third "
               "of normal. Europe enters winter with record-low storage, so a cold snap could push prices higher still.")
    st.caption("Sources: listed per row in the data/gas_*.csv files (source and url columns). Main sources: World Bank Pink Sheet, "
               "EIA, IEA, Kpler, S&P Global, Energy Institute via EPRINC, and GIE AGSI storage data.")


if __name__ == "__main__":
    # Run this panel on its own:  python3 -m streamlit run panels/gas_lng.py
    st.set_page_config(page_title="Hormuz Shock – Gas & LNG", layout="wide")
    render()
