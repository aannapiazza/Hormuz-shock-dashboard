"""
Hormuz | Shipping & Markets

Story: how much traffic goes through the Strait of Hormuz, and what Brent and WTI
oil futures did at the same time. Section 1 shows where things stand now. Section 2
compares traffic and Brent over time. Section 3 zooms in on one month.

How this file is organised:
    1. SETTINGS  - every date, source and number you might want to change
    2. DATA      - the shipping CSV (IMF PortWatch) and the market prices (Yahoo Finance)
    3. ANALYSIS  - the maths, as small functions with docstrings
    4. CHARTS    - Plotly figures
    5. LAYOUT    - the sections and their controls (Streamlit)

Run on its own:   python3 -m streamlit run hormuz_dashboard.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# SETTINGS: 
END = pd.Timestamp("2026-10-31")          # last day shown, same for the whole dashboard (None = all data)
WAR_START = pd.Timestamp("2026-02-28")    # US-Israel strikes on Iran
EVENTS = [("2026-02-28", "War begins"), ("2026-04-08", "Ceasefire"),
          ("2026-06-17", "US–Iran MOU"), ("2026-07-08", "Strikes resume")]
PREWAR_DATE = pd.Timestamp("2026-02-27")      # pre-war reference
BASELINE_START = pd.Timestamp("2026-01-01")   # normal traffic = average daily transits
BASELINE_END = pd.Timestamp("2026-02-27")     # in this window (needs at least 14 days of data)
MARKET_SYMBOLS = {"BRENT": "BZ=F", "WTI": "CL=F", "VIX": "^VIX", "DOLLAR INDEX": "DX-Y.NYB"}
MARKET_HISTORY = "2y"                         # how much price history to download
LIVE = False                                  # False = read the saved copy in data/; True = download from Yahoo
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MARKET_FILE = DATA_DIR / "shipping_markets.csv"   # saved copy of the four market series
TIME_RANGES = {"Last 30 days": 30, "Last 90 days": 90, "Last 180 days": 180,
               "Last year": 365, "All data": None}    # label: days (None = everything)
DEFAULT_RANGE = "Last year"
MONTHS_SHOWN = 18                             # bars in the monthly chart
VIEWS = ["Absolute", "% vs pre-war"]
SECOND_CHARTS = ["Monthly traffic", "Tanker share", "Traffic vs Brent (scatter)", "Brent daily change"]
MONTH_NOTES = {
    "2026-02": "The war begins on 28 Feb, the last day of the month.",
    "2026-03": "The first full month of the war.",
    "2026-04": "Brent hit 138 USD on 7 Apr, before the next day's ceasefire.",
    "2026-05": "Talks stall and the strait stays effectively shut.",
    "2026-06": "The 17 Jun MOU raises hopes that the strait will reopen.",
    "2026-07": "Strikes resume on 8 Jul, and Iran declares the strait closed on 12 Jul.",
    "2026-09": "Prices rebound as global inventories keep falling.",
    "2026-10": "37 ships attacked in the month.",
}
COLOURS = {"navy": "#1b2a41", "blue": "#2e6fd8", "orange": "#c2410c", "purple": "#7c5cd6",
           "red": "#d23f3f", "green": "#2e9b57", "grey": "#98a2b3", "light": "#9db4d1"}


# DATA 
def load_shipping_data():
    csv_path = DATA_DIR / "portwatch_daily_chokepoints.csv"     # the same PortWatch file the inflation panel uses
    if not csv_path.is_file():
        raise FileNotFoundError("data/portwatch_daily_chokepoints.csv is missing (download it from portwatch.imf.org).")
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    required_columns = {"portname", "date", "n_total", "n_tanker"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError("Missing CSV columns: " + ", ".join(sorted(missing_columns)))

    df = df.loc[df["portname"].astype("string").str.contains("Hormuz", case=False, na=False)].copy()
    if df.empty:
        raise ValueError("No Hormuz records were found in the CSV.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    for column in ["n_total", "n_tanker"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["date", "n_total", "n_tanker"]).sort_values("date").reset_index(drop=True)
    if END is not None:
        df = df[df["date"] <= END].reset_index(drop=True)
    if df.empty:
        raise ValueError("The CSV contains no valid Hormuz shipping records.")
    if df["date"].duplicated().any():
        raise ValueError("Multiple Hormuz records were found for the same date. "
                         "Check the CSV before calculating daily totals.")

    counts = df[["n_total", "n_tanker"]]
    if ((counts < 0).any(axis=1) | (df["n_tanker"] > df["n_total"]) | (counts % 1 != 0).any(axis=1)).any():
        raise ValueError("Invalid vessel counts in the CSV. Counts must be non-negative whole numbers, "
                         "and tankers cannot exceed total vessels.")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_market_data(symbol, period=MARKET_HISTORY):
    history = yf.Ticker(symbol).history(period=period)
    if history.empty or "Close" not in history.columns:
        return pd.Series(dtype=float)
    prices = pd.to_numeric(history["Close"], errors="coerce").dropna()
    prices = prices.loc[np.isfinite(prices.to_numpy())]
    index = pd.DatetimeIndex(prices.index)        # no time zone, like the shipping dates
    prices.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    prices = prices.sort_index()
    return prices if END is None else prices[prices.index <= END]


def load_markets(live=LIVE):
    """All four market series: the saved copy in data/, or a fresh Yahoo download that is then saved.

    If the download fails, the saved copy is used (the Session 11 pattern), so the
    numbers stay the same on every run and the panel works offline.
    """
    if live or not MARKET_FILE.exists():
        try:
            prices = pd.DataFrame({label: load_market_data(symbol) for label, symbol in MARKET_SYMBOLS.items()})
            prices.index.name = "date"
            prices.to_csv(MARKET_FILE)
        except Exception:
            pass
    if not MARKET_FILE.exists():
        return {label: pd.Series(dtype=float) for label in MARKET_SYMBOLS}
    saved = pd.read_csv(MARKET_FILE, parse_dates=["date"], index_col="date")
    return {label: saved[label].dropna() if label in saved else pd.Series(dtype=float) for label in MARKET_SYMBOLS}


def safe_market_data(symbol):
    """load_market_data, but an empty Series instead of an error if Yahoo fails."""
    try:
        return load_market_data(symbol)
    except Exception:
        return pd.Series(dtype=float)


# ANALYSIS
def percentage_change(prices):
    """Percentage change between the last two observations."""
    if len(prices) < 2:
        return None
    values = prices.iloc[-2:].to_numpy(dtype=float)
    if not np.all(np.isfinite(values)) or values[0] <= 0:
        return None
    return float(np.diff(values)[0] / values[0] * 100)


def get_prewar_price(brent):
    """Exact reference-date close from the same BZ=F series; no spot fallback."""
    if PREWAR_DATE not in brent.index:
        return None
    value = float(brent.loc[PREWAR_DATE])
    return value if np.isfinite(value) and value > 0 else None


def pct(old, new) -> float:
    """Percentage change from old to new."""
    return (new / old - 1) * 100


def signed(v, decimals=1) -> str:
    """A number with a + sign when positive."""
    return f"{'+' if v > 0 else ''}{v:.{decimals}f}"


def nice_date(ts) -> str:
    """'19 Nov 2026'."""
    ts = pd.Timestamp(ts)
    return f"{ts.day} {ts.strftime('%b %Y')}"


def between(data, start, last):
    """The part of a daily table or price series from start to last."""
    return data.loc[(data.index >= start) & (data.index <= last)]


def build_daily(shipping_df):
    """One row per calendar day, with 7-day averages (they need seven consecutive observations)."""
    daily = shipping_df.set_index("date")[["n_total", "n_tanker"]].asfreq("D")
    out = daily.join(daily.rolling(window=7, min_periods=7).mean().add_suffix("_avg7"))
    out["share_avg7"] = out["n_tanker_avg7"] / out["n_total_avg7"] * 100
    return out


def prewar_baseline(shipping_df):
    """Average daily transits in the pre-war window, or None if the CSV doesn't cover it."""
    window = shipping_df[(shipping_df["date"] >= BASELINE_START) & (shipping_df["date"] <= BASELINE_END)]
    if len(window) < 14:
        return None
    return {"n_total": float(window["n_total"].mean()), "n_tanker": float(window["n_tanker"].mean())}


def build_monthly(shipping_df, brent, base):
    """One row per month: average daily transits, tanker share, change vs pre-war, Brent average."""
    start = shipping_df["date"].dt.to_period("M").dt.to_timestamp()
    m = (shipping_df.assign(Start=start).groupby("Start")
         .agg(Total=("n_total", "mean"), Tankers=("n_tanker", "mean"), Days=("date", "count")).reset_index())
    m["Share"] = m["Tankers"] / m["Total"] * 100
    m["vsPrewar"] = (m["Total"] / base["n_total"] - 1) * 100 if base else np.nan
    m["Brent"] = m["Start"].map(brent.resample("MS").mean()) if not brent.empty else np.nan
    m["DaysInMonth"] = m["Start"].dt.days_in_month
    m["Month"] = m["Start"].dt.strftime("%Y-%m")
    return m


# CHARTS 
def style(fig, height, title, **layout):
    """The look shared by all charts: white background, dark text, title on the left.
    Charts are drawn with theme=None, so they stay white in dark mode."""
    settings = dict(template="plotly_white", height=height, hovermode="x unified",
                    paper_bgcolor="white", plot_bgcolor="white", font=dict(color="#17202e"),
                    title=dict(text=f"<b>{title}</b>", x=0, xanchor="left", font=dict(size=16)),
                    margin=dict(l=10, r=20, t=50, b=40), legend=dict(orientation="h", y=-0.15, x=0))
    settings.update(layout)          # anything passed in replaces the default
    fig.update_layout(**settings)
    return fig


def line(x, y, name, colour, width=3, hover="%{y:.1f}", **extra):
    """One line of a chart."""
    return go.Scatter(x=x, y=y, name=name, mode="lines", connectgaps=False, line=dict(color=colour, width=width),
                      hovertemplate=f"{hover}<extra></extra>", **extra)


def finish(fig, height, title, start, last, reference=None, **layout):
    """Add the war shading, event lines and (optionally) a pre-war reference line, then style the chart.
    Labels appear for all events only when the chart covers about a year or less (to not overlap)."""
    if reference is not None:
        fig.add_hline(y=reference[0], line=dict(color="#6b7785", dash="dash", width=1),
                      annotation_text=reference[1], annotation_position="bottom right")
    fig.add_vrect(x0=WAR_START, x1=last, fillcolor="#d23f3f", opacity=0.07, line_width=0, layer="below")
    zoomed_in = (last - start).days <= 400
    for i, (date, label) in enumerate(EVENTS):
        when = pd.Timestamp(date)
        if not (start <= when <= last):
            continue
        fig.add_vline(x=when, line=dict(color="#98a2b3", width=1, dash="dot"))
        if zoomed_in or i == 0:
            fig.add_annotation(x=when, y=1 if i % 2 == 0 else 0.9, yref="paper", text=label,
                               showarrow=False, xanchor="left", yanchor="top", xshift=3,
                               font=dict(size=10, color="#6b7785"), bgcolor="rgba(255,255,255,0.8)")
    return style(fig, height, title, xaxis=dict(range=[start, last]), **layout)


def chart_traffic(daily, start, last, view, show_tankers, show_avg, base):
    """Daily ships (and tankers) through Hormuz, with 7-day averages."""
    as_pct = view == VIEWS[1] and base is not None
    d = between(daily, start, last)
    fig = go.Figure()
    # (column, name, faint colour, strong colour, shown?). In % view only the averages are drawn.
    for column, name, faint, strong, shown in [
            ("n_total", "All ships", "rgba(27,42,65,0.35)", COLOURS["navy"], True),
            ("n_tanker", "Tankers", "rgba(46,111,216,0.40)", COLOURS["blue"], show_tankers)]:
        if not shown:
            continue
        if not as_pct:
            fig.add_trace(line(d.index, d[column], name, faint, 1.2, f"{name}: %{{y:.1f}}"))
        if show_avg or as_pct:
            avg = d[column + "_avg7"]
            y, hover = ((avg / base[column] - 1) * 100, "%{y:+.1f}%") if as_pct else (avg, "%{y:.1f}")
            fig.add_trace(line(d.index, y, f"{name} (7-day avg)", strong, 3, f"{name} (7-day avg): {hover}"))

    current = daily["n_total_avg7"].dropna()
    title = "Daily ship traffic through Hormuz"
    if base is not None and not current.empty:
        change = pct(base["n_total"], current.iloc[-1])
        title = f"Hormuz traffic is {abs(change):.0f}% {'below' if change < 0 else 'above'} its pre-war level"
    return finish(fig, 420, title, start, last, (0 if as_pct else base["n_total"], "pre-war average") if base else None,
                  yaxis=dict(title="% vs pre-war average" if as_pct else "Vessels per day",
                             ticksuffix="%" if as_pct else ""))


def chart_brent(brent, wti, start, last, view, show_wti, prewar_price=None):
    """Brent futures (and optionally WTI), as USD per barrel or % vs the pre-war price."""
    as_pct = view == VIEWS[1] and prewar_price is not None
    b = between(brent, start, last)
    fmt = "%{y:+.1f}%" if as_pct else "$%{y:.2f}"
    fig = go.Figure(line(b.index, (b / prewar_price - 1) * 100 if as_pct else b, "Brent", COLOURS["green"], 3,
                         f"Brent: {fmt}"))
    if show_wti and not as_pct and not wti.empty:
        w = between(wti, start, last)
        fig.add_trace(line(w.index, w, "WTI", COLOURS["grey"], 2, "WTI: $%{y:.2f}"))

    title = "Brent futures"
    if not brent.empty and prewar_price is not None:
        change = pct(prewar_price, brent.iloc[-1])
        title = f"Brent is {abs(change):.0f}% {'above' if change >= 0 else 'below'} its pre-war price"
    return finish(fig, 420, title, start, last, (0 if as_pct else prewar_price, "pre-war futures level") if prewar_price is not None else None,
                  yaxis=dict(title="% vs pre-war" if as_pct else "USD per barrel", ticksuffix="%" if as_pct else ""))


def chart_second(mode, monthly, selected, daily, brent, start, last):
    """Monthly bars, tanker share, traffic/Brent scatter, or Brent daily change."""
    d, b = between(daily, start, last), between(brent, start, last)
    if mode == SECOND_CHARTS[0]:
        m = monthly.tail(MONTHS_SHOWN)
        colours = [COLOURS["orange"] if v == selected else COLOURS["light"] for v in m["Month"]]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=m["Start"], y=m["Total"], name="All ships", marker_color=colours,
                             text=[f"{v:.0f}" for v in m["Total"]], textposition="outside", cliponaxis=False,
                             hovertemplate="%{x|%b %Y}: %{y:.1f} ships a day<extra></extra>"))
        fig.add_trace(go.Bar(x=m["Start"], y=m["Tankers"], name="Tankers", marker_color=COLOURS["navy"],
                             hovertemplate="%{x|%b %Y}: %{y:.1f} tankers a day<extra></extra>"))
        fig.update_layout(barmode="overlay")
        return style(fig, 380, "Average daily transits each month (the selected month is orange)",
                     hovermode="closest", xaxis=dict(tickformat="%b %y"), yaxis=dict(title="Average per day"))
    if mode == SECOND_CHARTS[1]:
        fig = go.Figure(line(d.index, d["share_avg7"], "Tanker share", COLOURS["purple"], 3, "Tanker share: %{y:.1f}%",
                             fill="tozeroy", fillcolor="rgba(124,92,214,0.12)"))
        return finish(fig, 380, "Tankers as a share of all ships (7-day average)", start, last, showlegend=False,
                      yaxis=dict(title="% of all ships", ticksuffix="%"))
    if mode == SECOND_CHARTS[2]:
        # Match actual observations by date; do not fill missing market prices.
        points = (
            d[["n_total_avg7"]]
            .join(b.rename("Brent"), how="inner")
            .replace([np.inf, -np.inf], np.nan)
            .dropna(subset=["n_total_avg7", "Brent"])
            .copy()
        )
        fig = go.Figure()
        if points.empty:
            fig.add_annotation(
                text="No matching traffic and Brent observations in this time range.",
                x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
            )
        else:
            points["Month"] = points.index.strftime("%Y-%m")
            palette = [
                "#2e6fd8", "#7c5cd6", "#2e9b57", "#c2410c",
                "#1b2a41", "#b38a25", "#008b9a", "#c05a93",
                "#687c32", "#986144", "#5965a8", "#7c8798",
            ]
            for month, group in points.groupby("Month", sort=True):
                month_number = pd.Timestamp(month + "-01").month
                focused = month == selected
                fig.add_trace(go.Scatter(
                    x=group["n_total_avg7"],
                    y=group["Brent"],
                    mode="markers",
                    name=pd.Timestamp(month + "-01").strftime("%b %Y"),
                    text=group.index.strftime("%d %b %Y"),
                    marker=dict(
                        color=palette[month_number - 1],
                        size=11 if focused else 8,
                        opacity=0.95 if focused else 0.65,
                        symbol="diamond" if focused else "circle",
                        line=dict(color="white", width=0.7),
                    ),
                    hovertemplate=(
                        "<b>%{text}</b><br>"
                        "Traffic (7-day avg): %{x:.1f} vessels/day<br>"
                        "Brent futures: $%{y:.2f}/barrel<extra>%{fullData.name}</extra>"
                    ),
                ))
        return style(
            fig, 440, "Ship traffic vs Brent futures",
            hovermode="closest",
            xaxis=dict(title="Vessels per day (7-day average)", rangemode="tozero"),
            yaxis=dict(title="Brent futures (USD per barrel)", tickprefix="$"),
            legend=dict(title=dict(text="Month · selected month = diamonds"),
                        orientation="h", y=-0.25, x=0),
            margin=dict(l=10, r=20, t=55, b=110),
        )
    change = between((brent.pct_change() * 100).dropna(), start, last)
    fig = go.Figure(go.Bar(x=change.index, y=change, hovertemplate="%{y:+.2f}%<extra></extra>",
                           marker_color=[COLOURS["red"] if v > 0 else COLOURS["green"] for v in change]))
    return finish(fig, 380, "Brent daily change (red = rise, green = fall)", start, last, showlegend=False,
                  yaxis=dict(title="% change on the previous day", ticksuffix="%"))


# LAYOUT
def market_metric(column, label, prices, prefix="", caption="{date}"):
    """A metric with the latest price and its change on the previous observation."""
    if prices.empty:
        return column.metric(label, "Unavailable")
    change = percentage_change(prices)
    column.metric(label, f"{prefix}{float(prices.iloc[-1]):.2f}",
                  delta=f"{change:+.2f}%" if change is not None else None, delta_color="off")
    column.caption(caption.format(date=f"{prices.index[-1]:%d %b %Y}"))


def section_1_now(shipping_df, daily, base, brent, wti, prewar_price=None):
    """Section 1: where do traffic and prices stand now?"""
    st.subheader("Where things stand")
    traffic_col, tanker_col, brent_col, wti_col = st.columns(4)     # latest observations
    if shipping_df is not None:
        latest = shipping_df.iloc[-1]
        previous = shipping_df.iloc[-2] if len(shipping_df) >= 2 else None
        # Only describe changes as daily when dates are consecutive.
        consecutive = previous is not None and latest["date"] - previous["date"] == pd.Timedelta(days=1)
        for column, label, key, note in [(traffic_col, "Ship transits", "n_total", ""),
                                         (tanker_col, "Tanker transits", "n_tanker", " · included in total")]:
            delta = f"{int(latest[key] - previous[key]):+d} vs previous day" if consecutive else None
            column.metric(label, f"{int(latest[key]):,}", delta=delta, delta_color="off")
            column.caption(f"{latest['date']:%d %b %Y}{note}")
    else:
        traffic_col.metric("Ship transits", "Unavailable")
        tanker_col.metric("Tanker transits", "Unavailable")
    market_metric(brent_col, "BRENT futures", brent, "$", "USD/barrel · {date}")
    market_metric(wti_col, "WTI futures", wti, "$", "USD/barrel · {date}")

    c1, c2, c3, c4 = st.columns(4)                                   # compared with before the war
    average = daily["n_total_avg7"].dropna() if daily is not None else pd.Series(dtype=float)
    share = daily["share_avg7"].dropna() if daily is not None else pd.Series(dtype=float)
    if base is not None and not average.empty:
        c1.metric("Traffic vs pre-war (7-day avg)", f"{signed(pct(base['n_total'], average.iloc[-1]))}%",
                  help=f"7-day average of ships a day, against {base['n_total']:.0f} a day on average "
                       f"between {nice_date(BASELINE_START)} and {nice_date(BASELINE_END)}.")
    else:
        c1.metric("Traffic vs pre-war (7-day avg)", "n/a", help="The CSV does not cover the pre-war window.")
    c2.metric("Tanker share (7-day)", f"{share.iloc[-1]:.1f}%" if not share.empty else "n/a", help="7-day average.")
    b, w = (None if p.empty else float(p.iloc[-1]) for p in (brent, wti))
    reference_help = (
        f"BZ=F close of USD {prewar_price:.2f} on {nice_date(PREWAR_DATE)}; same series as the current price."
        if prewar_price is not None
        else f"No valid BZ=F close available on {nice_date(PREWAR_DATE)}."
    )
    c3.metric("Brent futures vs pre-war",
              f"{signed(pct(prewar_price, b))}%" if b is not None and prewar_price is not None else "n/a",
              help=reference_help)
    c4.metric("Brent–WTI gap", f"${b - w:.2f}" if b and w else "n/a", help="Latest futures prices.")
    st.caption("Market percentage changes compare the last two available observations.")


def section_2_over_time(shipping_df, daily, base, brent, wti, prewar_price=None):
    """Section 2: traffic and Brent over time. Returns the time window the charts use."""
    st.subheader("Traffic and prices over time")
    c1, c2, c3 = st.columns([1.2, 1.2, 2])
    period = c1.selectbox("Time range", list(TIME_RANGES), index=list(TIME_RANGES).index(DEFAULT_RANGE),
                          key="hs_range")
    view = c2.selectbox("View", VIEWS, key="hs_view")
    with c3:
        show_tankers = st.toggle("Show tankers", value=True, key="hs_tankers")
        show_avg = st.toggle("Show 7-day averages", value=True, key="hs_avg")
        show_wti = st.toggle("Compare Brent with WTI", value=False, key="hs_wti", disabled=view == VIEWS[1],
                             help="Only in the absolute view.")

    dates = ([shipping_df["date"].min(), shipping_df["date"].max()] if shipping_df is not None else []) + \
            ([brent.index.min(), brent.index.max()] if not brent.empty else [])
    last, days = max(dates), TIME_RANGES[period]
    start = last - pd.Timedelta(days=days - 1) if days else min(dates)

    left, right = st.columns(2, gap="large")
    with left:
        if shipping_df is None:
            st.info("Shipping data is unavailable.")
        else:
            if view == VIEWS[1] and base is None:
                st.caption("The CSV does not cover the pre-war window, so counts are shown instead of % changes.")
            st.plotly_chart(chart_traffic(daily, start, last, view, show_tankers, show_avg, base),
                            width="stretch", theme=None, key="hs_traffic_chart")
            st.caption("Daily vessel counts · IMF PortWatch. Tankers are included in all ships. "
                       "Each 7-day average needs seven consecutive daily observations.")
    with right:
        if brent.empty:
            st.info("Brent prices are temporarily unavailable.")
        else:
            if view == VIEWS[1] and prewar_price is None:
                st.caption("The reference-date BZ=F close is unavailable; Brent is shown in USD per barrel.")
            st.plotly_chart(chart_brent(brent, wti, start, last, view, show_wti, prewar_price),
                            width="stretch", theme=None, key="hs_brent_chart")
            st.caption("Daily closes of Brent futures · Yahoo Finance. Quotes may be delayed. "
                       f"Shaded: since {nice_date(WAR_START)}.")
    return start, last


def section_3_month(monthly, daily, brent, start, last, shipping_last):
    """Section 3: a closer look, and one month in focus."""
    st.subheader("Closer look")
    left, right = st.columns([2, 1], gap="large")
    with right:                     # drawn first, because the chart needs the chosen month
        months = monthly["Month"].tolist()
        selected = st.selectbox("Month in focus", months, index=len(months) - 1, key="hs_month",
                                format_func=lambda m: pd.Timestamp(m + "-01").strftime("%B %Y"))
        row = monthly[monthly["Month"] == selected].iloc[0]
        a, b = st.columns(2)
        a.metric("Ships a day", f"{row['Total']:.1f}")
        b.metric("Tankers a day", f"{row['Tankers']:.1f}")
        a.metric("Tanker share", f"{row['Share']:.1f}%")
        b.metric("vs pre-war traffic", "n/a" if pd.isna(row["vsPrewar"]) else f"{signed(row['vsPrewar'])}%")
        month_start = pd.Timestamp(selected + "-01")
        month_end = month_start + pd.offsets.MonthEnd(0)

        month_prices = brent.loc[
            (brent.index >= month_start)
            & (brent.index <= month_end)
        ].dropna()

        if month_prices.empty:
            st.caption("Brent futures monthly average: unavailable")
        else:
            st.caption(
                f"Brent futures monthly average: USD {month_prices.mean():.2f}/barrel"
                f" · {month_prices.count()} trading observations"
            )

        st.caption(
            f"Shipping data: {int(row['Days'])}"
            f" of {int(row['DaysInMonth'])} calendar days"
        )
        if row["Days"] < row["DaysInMonth"] and selected == months[-1]:
            st.caption(f"Partial month: data to {nice_date(shipping_last)}.")
        if selected in MONTH_NOTES:
            st.info(MONTH_NOTES[selected])
    with left:
        mode = st.radio("Second chart", SECOND_CHARTS, index=2, horizontal=True, key="hs_second", label_visibility="collapsed")
        if mode == SECOND_CHARTS[2] and brent.empty:
            st.info("Brent prices are temporarily unavailable.")
        else:
            st.plotly_chart(chart_second(mode, monthly, selected, daily, brent, start, last),
                            width="stretch", theme=None, key="hs_second_chart")
        if mode == SECOND_CHARTS[2]:
            st.caption(
                "Each point matches a 7-day traffic average and a Brent close on the same date. "
                "Only dates with both observations are included; missing prices are not filled. "
                "Colours identify months; diamonds highlight the month in focus. "
                "The chart uses the time range selected above, in absolute units. "
                "Association does not establish causation."
            )
        else:
            st.caption("These charts do not establish a causal relationship.")


def render():
    st.caption("Shipping: daily IMF PortWatch data from a local CSV. "
               "Markets: daily observations from Yahoo Finance; quotes may be delayed."
               + (f" Data shown to {nice_date(END)}." if END is not None else ""))
    shipping_df = None
    try:
        shipping_df = load_shipping_data()
    except Exception as error:
        st.error(f"Shipping data unavailable: {error}")
    with st.spinner("Loading market data..."):
        market_data = load_markets()
    market_errors = [label for label, prices in market_data.items() if prices.empty]
    if market_errors:
        st.warning("Market data could not be retrieved for: " + ", ".join(market_errors) + ".")

    brent, wti = market_data["BRENT"], market_data["WTI"]
    prewar_price = get_prewar_price(brent)
    if prewar_price is None:
        st.warning(
            f"No BZ=F close was retrieved for {nice_date(PREWAR_DATE)}. "
            "Brent comparisons with the pre-war price are unavailable."
        )
    daily = base = monthly = None
    if shipping_df is not None:
        daily, base = build_daily(shipping_df), prewar_baseline(shipping_df)
        monthly = build_monthly(shipping_df, brent, base)
    if shipping_df is None and brent.empty:
        st.stop()

    st.divider()
    section_1_now(shipping_df, daily, base, brent, wti, prewar_price)
    st.divider()
    start, last = section_2_over_time(shipping_df, daily, base, brent, wti, prewar_price)
    if shipping_df is not None:
        st.divider()
        section_3_month(monthly, daily, brent, start, last, shipping_df["date"].max())

    with st.expander("More market indicators"):
        for column, label in zip(st.columns(2), ["VIX", "DOLLAR INDEX"]):
            market_metric(column, label, market_data[label], caption="Observation: {date}")
        st.caption("VIX measures expected US equity market volatility. "
                   "The Dollar Index tracks the US dollar against a basket of currencies.")

    with st.expander("Shipping data and download"):
        if shipping_df is None:
            st.info("No shipping data available.")
        else:
            st.markdown("**Monthly summary**")
            summary = monthly[["Month", "Total", "Tankers", "Share", "vsPrewar", "Brent", "Days"]].rename(
                columns={"Total": "Ships/day", "Tankers": "Tankers/day", "Share": "Tanker share %",
                         "vsPrewar": "vs pre-war %", "Brent": "Brent avg", "Days": "Days with data"})
            st.dataframe(summary.sort_values("Month", ascending=False).round(1), width="stretch", hide_index=True)
            st.markdown("**Daily records**")
            st.dataframe(shipping_df.sort_values("date", ascending=False), width="stretch", hide_index=True)
            st.download_button("Download Hormuz data", shipping_df.to_csv(index=False).encode("utf-8"),
                               file_name="hormuz_shipping.csv", mime="text/csv", key="download_hormuz_shipping")

    with st.expander("Futures prices and download"):
        futures = pd.concat([brent.rename("Brent BZ=F"), wti.rename("WTI CL=F")], axis=1)
        futures.index.name = "Date"
        st.caption("Yahoo Finance daily closes, USD per barrel. These are futures, not EIA spot prices.")
        if futures.empty:
            st.info("No futures prices available.")
        else:
            st.dataframe(futures.sort_index(ascending=False), width="stretch")
            monthly_brent = brent.resample("MS").agg(["mean", "count"]).rename(
                columns={"mean": "Brent futures monthly average", "count": "Price observations"})
            st.dataframe(monthly_brent.sort_index(ascending=False).round(2), width="stretch")
            st.download_button("Download futures prices", futures.to_csv().encode("utf-8"),
                               file_name="hormuz_futures_prices.csv", mime="text/csv", key="hs_futures_download")

    base_note = (f" Pre-war traffic is the average of daily transits between {nice_date(BASELINE_START)} "
                 f"and {nice_date(BASELINE_END)}." if base else "")
    brent_reference_note = (
        f"The pre-war Brent futures reference is the BZ=F close on {nice_date(PREWAR_DATE)} "
        f"(USD {prewar_price:.2f})."
        if prewar_price is not None else "The pre-war Brent futures reference is unavailable."
    )
    st.caption("Sources: IMF PortWatch (Hormuz daily transits) and Yahoo Finance (market prices). "
               "Shipping data updates when the CSV is replaced. Market requests are cached for five minutes "
               "and run when the app executes. Shipping and market observations may have different dates. "
               + brent_reference_note
               + base_note)
def render_card():
    """The small version for the home page: two numbers and one chart, like the other panels' cards."""
    try:
        shipping_df = load_shipping_data()
    except Exception as error:
        st.error(f"Shipping data unavailable: {error}")
        return

    daily = build_daily(shipping_df)
    base = prewar_baseline(shipping_df)
    last = shipping_df["date"].max()
    start = last - pd.Timedelta(days=364)

    month = shipping_df[shipping_df["date"] >= last.replace(day=1)]
    c1, c2 = st.columns(2)
    for col, column, label in [(c1, "n_total", "Ships a day through Hormuz"),
                               (c2, "n_tanker", "Tankers a day")]:
        now = month[column].mean()
        col.metric(f"{label}, {last:%b}", f"{now:.1f}",
                   f"{pct(base[column], now):+.0f}% vs pre-war" if base else None)

    fig = chart_traffic(daily, start, last, view=VIEWS[0],
                        show_tankers=False, show_avg=True, base=base)
    fig.update_traces(fill="tozeroy", fillcolor="rgba(27,42,65,0.06)",
                      selector=dict(name="All ships (7-day avg)"))
    fig.update_layout(height=380, showlegend=False, title_text="",
                      margin=dict(l=10, r=20, t=10, b=40))
    st.plotly_chart(fig, width="stretch", theme=None, key="hs_card_timeline",
                    config={"displayModeBar": False})

if __name__ == "__main__":
    st.set_page_config(page_title="Hormuz | Shipping & Markets", layout="wide")
    render()
    
