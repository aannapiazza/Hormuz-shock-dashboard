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

# 1. SETTINGS - change dates, symbols and notes here, nowhere else

END = pd.Timestamp("2026-10-31")
# war started
WAR_START = pd.Timestamp("2026-02-28")    # US-Israel strikes on Iran
EVENTS = [("2026-02-28", "War begins"), ("2026-04-08", "Ceasefire"),
          ("2026-06-17", "US–Iran MOU"), ("2026-07-07", "Strikes resume")]
# Pre-war reference
PREWAR_DATE = pd.Timestamp("2026-02-27")
PREWAR_PRICE = 71.32                       # Brent settlement on PREWAR_DATE, USD per barrel
BASELINE_START = pd.Timestamp("2026-01-01")   # normal traffic = average daily transits
BASELINE_END = pd.Timestamp("2026-02-27") 
# Market prices:
MARKET_SYMBOLS = {"BRENT": "BZ=F", "WTI": "CL=F", "VIX": "^VIX", "DOLLAR INDEX": "DX-Y.NYB"}
MARKET_HISTORY = "2y" 
TIME_RANGES = {"Last 30 days": 30, "Last 90 days": 90, "Last 180 days": 180,
               "Last year": 365, "All data": None}
DEFAULT_RANGE = "Last year"
MONTHS_SHOWN = 18                    
VIEWS = ["Absolute", "% vs pre-war"]
SECOND_CHARTS = ["Monthly traffic", "Tanker share", "Traffic and Brent", "Brent daily change"]
MONTH_NOTES = {
    "2026-02": "The war begins on 28 Feb, the last day of the month.",
    "2026-03": "The first full month of the war.",
    "2026-04": "Brent hit 138 USD on 7 Apr, before the next day's ceasefire.",
    "2026-05": "Talks stall and the strait stays effectively shut.",
    "2026-06": "The 17 Jun MOU raises hopes that the strait will reopen.",
    "2026-07": "Strikes resume on 7 Jul, and Iran declares the strait closed on 12 Jul.",
    "2026-09": "Prices rebound as global inventories keep falling.",
    "2026-10": "37 ships attacked in the month.",
}
COLOURS = {"navy": "#1b2a41", "blue": "#2e6fd8", "orange": "#c2410c", "purple": "#7c5cd6",
           "red": "#d23f3f", "green": "#2e9b57", "grey": "#98a2b3", "light": "#9db4d1"}
# DATA

def load_shipping_data():
    csv_path = Path(__file__).resolve().parent / "Daily_Chokepoints_Data.csv"

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip() #end reading file
    required_columns = {
        "portname",
        "date",
        "n_total",
        "n_tanker",
    }
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            "Missing CSV columns: "
            + ", ".join(sorted(missing_columns))
        ) #check columns

    df = df.loc[
        df["portname"]
        .astype("string")
        .str.contains("Hormuz", case=False, na=False)
    ].copy() # Hormuz datas
    if df.empty:
        raise ValueError(
            "No Hormuz records were found in the CSV."
        )
    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
        utc=True,
    ).dt.tz_convert(None).dt.normalize() #convertion in dates and tz:convert remove jet lag

    for column in ["n_total", "n_tanker"]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = (
        df.dropna(subset=["date", "n_total", "n_tanker"])
        .sort_values("date")
        .reset_index(drop=True)
    )
    if END is not None:
        df = df[df["date"] <= END].reset_index(drop=True)
    if df.empty:
        raise ValueError(
            "The CSV contains no valid Hormuz shipping records."
        )
    if df["date"].duplicated().any():
        raise ValueError(
            "Multiple Hormuz records were found for the same date. "
            "Check the CSV before calculating daily totals."
        )

    invalid_counts = (
        (df["n_total"] < 0)
        | (df["n_tanker"] < 0)
        | (df["n_tanker"] > df["n_total"])
        | (df["n_total"] % 1 != 0)
        | (df["n_tanker"] % 1 != 0)
    )

    if invalid_counts.any():
        raise ValueError(
            "Invalid vessel counts in the CSV. Counts must be "
            "non-negative whole numbers, and tankers cannot "
            "exceed total vessels."
        )

    return df

@st.cache_data(ttl=300, show_spinner=False)
def load_market_data(symbol, period=MARKET_HISTORY):
    history = yf.Ticker(symbol).history(period=period)
    if history.empty or "Close" not in history.columns:
        return pd.Series(dtype=float)
    prices = pd.to_numeric(
        history["Close"],
        errors="coerce",
    ).dropna() #keeps valid prices
    prices = prices.loc[np.isfinite(prices.to_numpy())]
  # data adjustments
    index = pd.DatetimeIndex(prices.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    prices.index = index.normalize()
    prices = prices.sort_index()
    if END is not None:
        prices = prices[prices.index <= END]
    return prices
    
# ANALYSIS

def percentage_change(prices):
    """Percentage change between the last two observations."""
    if len(prices) < 2:
        return None
    values = prices.iloc[-2:].to_numpy(dtype=float)
    if not np.all(np.isfinite(values)) or values[0] <= 0:
        return None
    return float(np.diff(values)[0] / values[0] * 100)
    
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

def build_daily(shipping_df: pd.DataFrame) -> pd.DataFrame:
    """One row per calendar day, with 7-day averages.
    Missing days stay empty, and a 7-day average needs seven consecutive observations."""
    daily = shipping_df.set_index("date")[["n_total", "n_tanker"]].asfreq("D")
    averages = daily.rolling(window=7, min_periods=7).mean().add_suffix("_avg7")
    out = daily.join(averages)
    out["share_avg7"] = out["n_tanker_avg7"] / out["n_total_avg7"] * 100
    return out


def prewar_baseline(shipping_df: pd.DataFrame):
    """Average daily transits in the pre-war window, or None if the CSV doesn't cover it."""
    window = shipping_df[(shipping_df["date"] >= BASELINE_START) & (shipping_df["date"] <= BASELINE_END)]
    if len(window) < 14:
        return None
    return {"n_total": float(window["n_total"].mean()), "n_tanker": float(window["n_tanker"].mean())}

def build_monthly(shipping_df: pd.DataFrame, brent: pd.Series, base) -> pd.DataFrame:
    """One row per month: average daily transits, tanker share, change vs pre-war, Brent average."""
    start = shipping_df["date"].dt.to_period("M").dt.to_timestamp()
    m = (shipping_df.assign(Start=start)
         .groupby("Start")
         .agg(Total=("n_total", "mean"), Tankers=("n_tanker", "mean"), Days=("date", "count"))
         .reset_index())
    m["Share"] = m["Tankers"] / m["Total"] * 100
    m["vsPrewar"] = (m["Total"] / base["n_total"] - 1) * 100 if base else np.nan
    m["Brent"] = m["Start"].map(brent.resample("MS").mean()) if not brent.empty else np.nan
    m["DaysInMonth"] = m["Start"].dt.days_in_month
    m["Month"] = m["Start"].dt.strftime("%Y-%m")
    return m

# CHARTS

def style(fig: go.Figure, height: int, title: str, **layout) -> go.Figure:
    """The look shared by all charts: white background, dark text, title on the left. Charts are drawn with theme=None."""
    settings = dict(template="plotly_white", height=height, hovermode="x unified",
                    paper_bgcolor="white", plot_bgcolor="white", font=dict(color="#17202e"),
                    title=dict(text=f"<b>{title}</b>", x=0, xanchor="left", font=dict(size=16)),
                    margin=dict(l=10, r=20, t=50, b=40), legend=dict(orientation="h", y=-0.15, x=0))
    settings.update(layout)          
    fig.update_layout(**settings)
    return fig

def add_war_and_events(fig: go.Figure, start: pd.Timestamp, last: pd.Timestamp) -> go.Figure:
"""Shade the war period and mark each key event with a dotted line.
Labels appear for all events only when the chart covers about a year or less(to not overlap)"""

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
    return fig


def chart_traffic(daily, start, last, view, show_tankers, show_avg, base) -> go.Figure:
    """Daily ships through Hormuz, with 7-day averages."""
    as_pct = view == VIEWS[1] and base is not None
    d = daily.loc[(daily.index >= start) & (daily.index <= last)]
    fig = go.Figure()
    def add(column, name, colour, width):
        if as_pct:
            y = (d[column] / base[column.replace("_avg7", "")] - 1) * 100
            hover = f"{name}: %{{y:+.1f}}%<extra></extra>"
        else:
            y, hover = d[column], f"{name}: %{{y:.1f}}<extra></extra>"
        fig.add_trace(go.Scatter(x=d.index, y=y, name=name, mode="lines", connectgaps=False,
                                 line=dict(color=colour, width=width), hovertemplate=hover))

    if as_pct:          # daily counts are too noisy as percentages, so only the averages are drawn
        add("n_total_avg7", "All ships (7-day avg)", COLOURS["navy"], 3)
        if show_tankers:
            add("n_tanker_avg7", "Tankers (7-day avg)", COLOURS["blue"], 3)
    else:
        add("n_total", "All ships", "rgba(27,42,65,0.35)", 1.2)
        if show_avg:
            add("n_total_avg7", "All ships (7-day avg)", COLOURS["navy"], 3)
        if show_tankers:
            add("n_tanker", "Tankers", "rgba(46,111,216,0.40)", 1.2)
            if show_avg:
                add("n_tanker_avg7", "Tankers (7-day avg)", COLOURS["blue"], 3)
    if base is not None:
        ref = 0 if as_pct else base["n_total"]
        fig.add_hline(y=ref, line=dict(color="#6b7785", dash="dash", width=1),
                      annotation_text="pre-war average", annotation_position="bottom right")
    add_war_and_events(fig, start, last)

    current = daily["n_total_avg7"].dropna()
    if base is not None and not current.empty:
        change = pct(base["n_total"], current.iloc[-1])
        title = f"Hormuz traffic is {abs(change):.0f}% {'below' if change < 0 else 'above'} its pre-war level"
    else:
        title = "Daily ship traffic through Hormuz"
    return style(fig, 420, title, xaxis=dict(range=[start, last]),
                 yaxis=dict(title="% vs pre-war average" if as_pct else "Vessels per day",
                            ticksuffix="%" if as_pct else ""))
    
def chart_brent(brent, wti, start, last, view, show_wti) -> go.Figure:
    """Brent futures (and optionally WTI), as USD per barrel or % vs the pre-war price."""
    as_pct = view == VIEWS[1]
    b = brent.loc[(brent.index >= start) & (brent.index <= last)]
    convert = (lambda s: (s / PREWAR_PRICE - 1) * 100) if as_pct else (lambda s: s)
    fmt = "%{y:+.1f}%" if as_pct else "$%{y:.2f}"
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=b.index, y=convert(b), name="Brent", mode="lines",
                             line=dict(color=COLOURS["green"], width=3),
                             hovertemplate=f"Brent: {fmt}<extra></extra>"))
    if show_wti and not as_pct and not wti.empty:
        w = wti.loc[(wti.index >= start) & (wti.index <= last)]
        fig.add_trace(go.Scatter(x=w.index, y=w, name="WTI", mode="lines",
                                 line=dict(color=COLOURS["grey"], width=2),
                                 hovertemplate="WTI: $%{y:.2f}<extra></extra>"))
    fig.add_hline(y=0 if as_pct else PREWAR_PRICE, line=dict(color="#6b7785", dash="dash", width=1),
                  annotation_text="pre-war level", annotation_position="bottom right")
    add_war_and_events(fig, start, last)
    if not brent.empty:
        change = pct(PREWAR_PRICE, brent.iloc[-1])
        title = f"Brent is {abs(change):.0f}% {'above' if change >= 0 else 'below'} its pre-war price"
    else:
        title = "Brent futures"
    return style(fig, 420, title, xaxis=dict(range=[start, last]),
                 yaxis=dict(title="% vs pre-war" if as_pct else "USD per barrel",
                            ticksuffix="%" if as_pct else ""))

def chart_second(mode, monthly, selected, daily, brent, start, last) -> go.Figure:
    """The second chart: monthly bars, tanker share, traffic and Brent, or Brent daily change."""
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
                     hovermode="closest", xaxis=dict(tickformat="%b %y"),
                     yaxis=dict(title="Average per day"))
    if mode == SECOND_CHARTS[1]:
        d = daily.loc[(daily.index >= start) & (daily.index <= last)]
        fig = go.Figure(go.Scatter(x=d.index, y=d["share_avg7"], mode="lines", fill="tozeroy",
                                   fillcolor="rgba(124,92,214,0.12)", connectgaps=False,
                                   line=dict(color=COLOURS["purple"], width=3),
                                   hovertemplate="Tanker share: %{y:.1f}%<extra></extra>"))
        add_war_and_events(fig, start, last)
        return style(fig, 380, "Tankers as a share of all ships (7-day average)",
                     xaxis=dict(range=[start, last]), yaxis=dict(title="% of all ships", ticksuffix="%"),
                     showlegend=False)
    if mode == SECOND_CHARTS[2]:
        d = daily.loc[(daily.index >= start) & (daily.index <= last)]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=d.index, y=d["n_total_avg7"], name="Ships a day (7-day avg, left axis)",
                                 mode="lines", line=dict(color=COLOURS["navy"], width=3), connectgaps=False,
                                 hovertemplate="Ships: %{y:.1f} a day<extra></extra>"))
        b = brent.loc[(brent.index >= start) & (brent.index <= last)]
        fig.add_trace(go.Scatter(x=b.index, y=b, name="Brent (right axis)", yaxis="y2", mode="lines",
                                 line=dict(color=COLOURS["green"], width=3),
                                 hovertemplate="Brent: $%{y:.2f}<extra></extra>"))
        add_war_and_events(fig, start, last)
        return style(fig, 380, "Traffic and Brent, side by side", xaxis=dict(range=[start, last]),
                     yaxis=dict(title="Ships a day"),
                     yaxis2=dict(title="USD per barrel", overlaying="y", side="right", showgrid=False))

    change = (brent.pct_change() * 100).dropna()
    change = change.loc[(change.index >= start) & (change.index <= last)]
    fig = go.Figure(go.Bar(x=change.index, y=change,
                           marker_color=[COLOURS["red"] if v > 0 else COLOURS["green"] for v in change],
                           hovertemplate="%{y:+.2f}%<extra></extra>"))
    add_war_and_events(fig, start, last)
    return style(fig, 380, "Brent daily change (red = rise, green = fall)", xaxis=dict(range=[start, last]),
                 yaxis=dict(title="% change on the previous day", ticksuffix="%"), showlegend=False)
# LAYOUT

def last_value(prices):
    """Latest price in a Series, or None if it is empty."""
    return None if prices.empty else float(prices.iloc[-1])

def section_1_now(shipping_df, daily, base, brent, wti) -> None:
    """Section 1: where do traffic and prices stand now?"""
    st.subheader("1 · Where things stand")

    # 1-latest observations
    traffic_col, tanker_col, brent_col, wti_col = st.columns(4)
    if shipping_df is not None:
        latest = shipping_df.iloc[-1]
        previous = shipping_df.iloc[-2] if len(shipping_df) >= 2 else None

        # Only describe changes as daily when dates are consecutive.
        consecutive_days = (
            previous is not None
            and latest["date"] - previous["date"] == pd.Timedelta(days=1)
        )
        total_delta = tanker_delta = None
        if consecutive_days:
            total_delta = f"{int(latest['n_total'] - previous['n_total']):+d} vs previous day"
            tanker_delta = f"{int(latest['n_tanker'] - previous['n_tanker']):+d} vs previous day"

        traffic_col.metric("Ship transits", f"{int(latest['n_total']):,}", delta=total_delta, delta_color="off")
        traffic_col.caption(f"{latest['date']:%d %b %Y}")
        tanker_col.metric("Tanker transits", f"{int(latest['n_tanker']):,}", delta=tanker_delta, delta_color="off")
        tanker_col.caption(f"{latest['date']:%d %b %Y} · included in total")
    else:
        traffic_col.metric("Ship transits", "Unavailable")
        tanker_col.metric("Tanker transits", "Unavailable")

    for column, label, prices in [(brent_col, "BRENT", brent), (wti_col, "WTI", wti)]:
        if prices.empty:
            column.metric(f"{label} futures", "Unavailable")
        else:
            change = percentage_change(prices)
            column.metric(f"{label} futures", f"${float(prices.iloc[-1]):.2f}",
                          delta=f"{change:+.2f}%" if change is not None else None, delta_color="off")
            column.caption(f"USD/barrel · {prices.index[-1]:%d %b %Y}")

    # 2- before the war
    c1, c2, c3, c4 = st.columns(4)
    average = daily["n_total_avg7"].dropna() if daily is not None else pd.Series(dtype=float)
    if base is not None and not average.empty:
        c1.metric("Traffic vs pre-war", f"{signed(pct(base['n_total'], average.iloc[-1]))}%",
                  help=f"7-day average of ships a day, against {base['n_total']:.0f} a day on average "
                       f"between {nice_date(BASELINE_START)} and {nice_date(BASELINE_END)}.")
    else:
        c1.metric("Traffic vs pre-war", "n/a", help="The CSV does not cover the pre-war window.")
    share = daily["share_avg7"].dropna() if daily is not None else pd.Series(dtype=float)
    c2.metric("Tanker share", f"{share.iloc[-1]:.1f}%" if not share.empty else "n/a", help="7-day average.")
    b, w = last_value(brent), last_value(wti)
    c3.metric("Brent vs pre-war", f"{signed(pct(PREWAR_PRICE, b))}%" if b else "n/a",
              help=f"Against ${PREWAR_PRICE:.2f} on {nice_date(PREWAR_DATE)}.".replace("$", "\\$"))
    c4.metric("Brent–WTI gap", f"${b - w:.2f}" if b and w else "n/a", help="Latest futures prices.")
    st.caption("Market percentage changes compare the last two available observations.")

def section_2_over_time(shipping_df, daily, base, brent, wti):
    """Section 2: traffic and Brent over time. Returns the time window the charts use."""
    st.subheader("2 · Traffic and prices over time")
    c1, c2, c3 = st.columns([1.2, 1.2, 2])
    period = c1.selectbox("Time range", list(TIME_RANGES), index=list(TIME_RANGES).index(DEFAULT_RANGE),
                          key="hs_range")
    view = c2.selectbox("View", VIEWS, key="hs_view")
    with c3:
        show_tankers = st.toggle("Show tankers", value=True, key="hs_tankers")
        show_avg = st.toggle("Show 7-day averages", value=True, key="hs_avg")
        show_wti = st.toggle("Compare Brent with WTI", value=False, key="hs_wti", disabled=view == VIEWS[1],
                             help="Only in the absolute view.")
    ends = []
    if shipping_df is not None:
        ends.append(shipping_df["date"].max())
    if not brent.empty:
        ends.append(brent.index.max())
    last = max(ends)
    days = TIME_RANGES[period]
    firsts = ([shipping_df["date"].min()] if shipping_df is not None else []) + \
             ([brent.index.min()] if not brent.empty else [])
    start = last - pd.Timedelta(days=days - 1) if days else min(firsts)

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
            st.plotly_chart(chart_brent(brent, wti, start, last, view, show_wti),
                            width="stretch", theme=None, key="hs_brent_chart")
            st.caption("Daily closes of Brent futures · Yahoo Finance. Quotes may be delayed. "
                       f"Shaded: since {nice_date(WAR_START)}.")
    return start, last
    
def section_3_month(monthly, daily, brent, start, last, shipping_last) -> None:
    """Section 3: a closer look, and one month in focus."""
    st.subheader("3 · A closer look")
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
        brent_txt = "n/a" if pd.isna(row["Brent"]) else f"${row['Brent']:.2f}"
        st.caption(f"Brent monthly average: {brent_txt} · days with data: "
                   f"{int(row['Days'])} of {int(row['DaysInMonth'])}".replace("$", "\\$"))
        if row["Days"] < row["DaysInMonth"] and selected == months[-1]:
            st.caption(f"Partial month: data to {nice_date(shipping_last)}.")
        note = MONTH_NOTES.get(selected)
        if note:
            st.info(note)

    with left:
        mode = st.radio("Second chart", SECOND_CHARTS, horizontal=True, key="hs_second",
                        label_visibility="collapsed")
        if mode == SECOND_CHARTS[2] and brent.empty:
            st.info("Brent prices are temporarily unavailable.")
        else:
            st.plotly_chart(chart_second(mode, monthly, selected, daily, brent, start, last),
                            width="stretch", theme=None, key="hs_second_chart")
        st.caption("These charts show traffic and prices side by side; "
                   "they do not establish a causal relationship.")

# PANEL
def render():
    st.header("Hormuz | Shipping & Markets")

    st.caption(
        "Shipping: daily IMF PortWatch data from a local CSV. "
        "Markets: daily observations from Yahoo Finance; quotes may be delayed."
        + (f" Data shown to {nice_date(END)}." if END is not None else "")
    )
    shipping_df = None
    try:
        shipping_df = load_shipping_data()
    except Exception as error:
        st.error(f"Shipping data unavailable: {error}")
    market_data = {}
    market_errors = []
    with st.spinner("Loading market data..."):
        for label, symbol in MARKET_SYMBOLS.items():
            try:
                market_data[label] = load_market_data(symbol)
            except Exception:
                market_data[label] = pd.Series(dtype=float)

            if market_data[label].empty:
                market_errors.append(label)
    if market_errors:
        st.warning("Market data could not be retrieved for: " + ", ".join(market_errors) + ".")
    brent, wti = market_data["BRENT"], market_data["WTI"]
    daily = base = monthly = None
    if shipping_df is not None:
        daily = build_daily(shipping_df)
        base = prewar_baseline(shipping_df)
        monthly = build_monthly(shipping_df, brent, base)
    if shipping_df is None and brent.empty:
        st.stop()
    st.divider()
    section_1_now(shipping_df, daily, base, brent, wti)
    st.divider()
    start, last = section_2_over_time(shipping_df, daily, base, brent, wti)
    if shipping_df is not None:
        st.divider()
        section_3_month(monthly, daily, brent, start, last, shipping_df["date"].max())
# market indicators
    with st.expander("More market indicators"):
        vix_col, dollar_col = st.columns(2)

        for column, label in [
            (vix_col, "VIX"),
            (dollar_col, "DOLLAR INDEX"),
        ]:
            prices = market_data[label]

            with column:
                if prices.empty:
                    st.metric(label, "Unavailable")
                else:
                    change = percentage_change(prices)

                    st.metric(
                        label,
                        f"{float(prices.iloc[-1]):.2f}",
                        delta=(
                            f"{change:+.2f}%"
                            if change is not None
                            else None
                        ),
                        delta_color="off",
                    )

                    st.caption(
                        f"Observation: "
                        f"{prices.index[-1]:%d %b %Y}"
                    )

        st.caption(
            "VIX measures expected US equity market volatility. "
            "The Dollar Index tracks the US dollar against "
            "a basket of currencies."
        )

    # DATA AND SOURCES
    with st.expander("Shipping data and download"):
        if shipping_df is None:
            st.info("No shipping data available.")
        else:
            st.markdown("**Monthly summary**")
            summary = monthly[["Month", "Total", "Tankers", "Share", "vsPrewar", "Brent", "Days"]].rename(
                columns={"Total": "Ships/day", "Tankers": "Tankers/day", "Share": "Tanker share %",
                         "vsPrewar": "vs pre-war %", "Brent": "Brent avg", "Days": "Days with data"})
            st.dataframe(summary.sort_values("Month", ascending=False).round(1),
                         width="stretch", hide_index=True)

            st.markdown("**Daily records**")
            st.dataframe(
                shipping_df.sort_values("date", ascending=False),
                width="stretch",
                hide_index=True,
            )

            st.download_button(
                label="Download Hormuz data",
                data=shipping_df.to_csv(index=False).encode("utf-8"),
                file_name="hormuz_shipping.csv",
                mime="text/csv",
                key="download_hormuz_shipping",
            )

    base_note = (f" Pre-war traffic is the average of daily transits between {nice_date(BASELINE_START)} "
                 f"and {nice_date(BASELINE_END)}." if base else "")
    st.caption(
        "Sources: IMF PortWatch (Hormuz daily transits) and Yahoo Finance (market prices). "
        "Shipping data updates when the CSV is replaced. Market requests are cached for five minutes "
        "and run when the app executes. Shipping and market observations may have different dates. "
        f"The pre-war Brent reference is the {nice_date(PREWAR_DATE)} price (USD {PREWAR_PRICE:.2f})."
        + base_note
    )

if __name__ == "__main__":
    st.set_page_config(
        page_title="Hormuz | Shipping & Markets",
        layout="wide",
    )
    render()
