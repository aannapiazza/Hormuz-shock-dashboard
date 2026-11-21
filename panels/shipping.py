"""
hormuz_dashboard.py — Hormuz | Shipping & Markets (Streamlit)

Traffic through the Strait of Hormuz (IMF PortWatch, local CSV) next to Brent / WTI
futures (Yahoo Finance), laid out like the oil-prices panel: header, KPI cards,
phase buttons, interactive Plotly charts and a "Month in focus" box.

HOW TO USE
  • In the group app: the main app imports this file and calls render().
  • On its own, for testing:   streamlit run hormuz_dashboard.py

HOW TO CHANGE IT
  Everything you're likely to edit is in the "EDIT HERE" section just below
  (titles, phases, notes, colours, symbols). The rest updates automatically.

Requires: streamlit (1.35+ for clickable charts, 1.40+ for pill buttons), plotly,
pandas, numpy, yfinance. Older Streamlit versions still work, with radio buttons.
All widget keys start with "hs_" so they can't clash with the other panels.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf


# =============================================================================
# ✏️  EDIT HERE
# =============================================================================

# 1) TEXT
TITLE = "Hormuz | Shipping & Markets"
SUBTITLE = "Daily ship traffic through the Strait of Hormuz, next to Brent and WTI futures"

# 2) MARKET SYMBOLS (Yahoo Finance)
MARKET_SYMBOLS = {
    "BRENT": "BZ=F",
    "WTI": "CL=F",
    "VIX": "^VIX",
    "DOLLAR INDEX": "DX-Y.NYB",
}
MARKET_HISTORY = "2y"        # how much price history to download

# 3) PRE-WAR REFERENCE — everything is compared against these
PREWAR_DATE = "2026-02-27"
PREWAR_PRICE = 71.32                       # Brent settlement on PREWAR_DATE, USD per barrel
BASELINE_START = "2026-01-01"              # "normal traffic" = average daily transits
BASELINE_END = "2026-02-27"                # in this window (needs at least 14 days of data)

# 4) TIME RANGES — label: number of days (None = everything available)
TIME_RANGES = {"30D": 30, "90D": 90, "180D": 180, "1Y": 365, "All": None}
DEFAULT_RANGE = "1Y"
MONTHS_SHOWN = 18          # bars in the monthly chart

# 5) EVENTS — the phase buttons that shade the charts.
#    "Button name": ("start YYYY-MM-DD", "end YYYY-MM-DD", "colour", "description")
EVENTS = {
    "Build-up": ("2026-01-01", "2026-02-28", "#e0a800",
                 "Markets price in the risk of war with Iran."),
    "War & closure": ("2026-02-28", "2026-04-08", "#d64545",
                      "The US–Israel strikes on 28 Feb trigger the near-closure of Hormuz."),
    "Ceasefire": ("2026-04-08", "2026-07-07", "#2e86de",
                  "Ceasefire on 8 Apr and the 17 Jun US–Iran MOU."),
    "Conflict resumes": ("2026-07-07", "2026-11-19", "#8e44ad",
                         "Strikes resume on 7 Jul and Iran declares the strait closed on 12 Jul."),
}

# 6) MONTH NOTES — shown in the "Month in focus" box. "YYYY-MM": "note".
#    Months without a note show their phase's description instead.
MONTH_NOTES = {
    "2026-03": "War begins on 28 Feb.",
    "2026-04": "Brent hit 138 USD on 7 Apr, before the next day's ceasefire.",
    "2026-05": "Talks stall and the strait stays effectively shut.",
    "2026-06": "The 17 Jun MOU raises hopes that the strait will reopen.",
    "2026-07": "Strikes resume on 7 Jul, and Iran declares the strait closed on 12 Jul.",
    "2026-09": "Prices rebound as global inventories keep falling.",
    "2026-10": "37 ships attacked in the month.",
}
BEFORE_EVENTS_NOTE = ("Before the war.", "Reference period for normal traffic.")

# 7) COLOURS
COLORS = {"navy": "#1b2a41", "orange": "#f2711c", "muted": "#6b7785",
          "red": "#d64545", "green": "#27ae60", "blue": "#2e86de",
          "purple": "#8e44ad", "grey": "#7f8c8d"}

# =============================================================================
# (You shouldn't need to change anything below this line.)
# =============================================================================

PHASES = {name: {"start": s, "end": e, "color": c, "text": t} for name, (s, e, c, t) in EVENTS.items()}
VIEW_OPTIONS = ["Absolute", "% vs pre-war"]
SECOND_OPTIONS = ["Monthly traffic", "Tanker share", "Traffic vs Brent", "Brent daily change"]


# ------------------------------ DATA LOADING --------------------------------
def load_shipping_data():
    script_folder = Path(__file__).resolve().parent

    possible_paths = [
        script_folder / "Daily_Chokepoints_Data.csv",
        script_folder.parent / "Daily_Chokepoints_Data.csv",
        script_folder.parent / "data" / "Daily_Chokepoints_Data.csv",
    ]

    csv_path = next(
        (path for path in possible_paths if path.is_file()),
        None,
    )

    if csv_path is None:
        raise FileNotFoundError(
            "Cannot find Daily_Chokepoints_Data.csv. "
            "Place it in the panel folder, the project root "
            "or the project's data folder."
        )

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

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
        )

    df = df.loc[
        df["portname"]
        .astype("string")
        .str.contains("Hormuz", case=False, na=False)
    ].copy()

    if df.empty:
        raise ValueError(
            "No Hormuz records were found in the CSV."
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
        utc=True,
    ).dt.tz_convert(None).dt.normalize()

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
    ).dropna()

    prices = prices.loc[np.isfinite(prices.to_numpy())]

    # Drop the time zone so market dates line up with the shipping dates.
    index = pd.DatetimeIndex(prices.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    prices.index = index.normalize()

    return prices.sort_index()


# --------------------------- NUMPY / PANDAS CALCULATIONS ---------------------
def percentage_change(prices):
    """Percentage change between the last two observations."""
    if len(prices) < 2:
        return None

    values = prices.iloc[-2:].to_numpy(dtype=float)

    if not np.all(np.isfinite(values)) or values[0] <= 0:
        return None

    return float(np.diff(values)[0] / values[0] * 100)


def pct(old, new):
    return (new / old - 1) * 100


def build_daily(shipping_df):
    """Daily table with gaps kept as NaN, plus 7-day averages (7 consecutive observations needed)."""
    daily = shipping_df.set_index("date")[["n_total", "n_tanker"]].asfreq("D")
    averages = daily.rolling(window=7, min_periods=7).mean().add_suffix("_avg7")
    out = daily.join(averages)
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
    month_start = shipping_df["date"].dt.to_period("M").dt.to_timestamp()
    m = (shipping_df.assign(Start=month_start)
         .groupby("Start")
         .agg(Total=("n_total", "mean"), Tankers=("n_tanker", "mean"), Days=("date", "count"))
         .reset_index())
    m["Share"] = m["Tankers"] / m["Total"] * 100
    m["MoM"] = (m["Total"] / m["Total"].shift(1) - 1) * 100
    m["vsPrewar"] = (m["Total"] / base["n_total"] - 1) * 100 if base else np.nan
    if brent is not None and not brent.empty:
        m["Brent"] = m["Start"].map(brent.resample("MS").mean())
    else:
        m["Brent"] = np.nan
    m["DaysInMonth"] = m["Start"].dt.days_in_month
    m["DateStr"] = m["Start"].dt.strftime("%Y-%m-%d")
    m["Month"] = m["Start"].dt.strftime("%Y-%m")
    return m


# ------------------------------ small formatters -----------------------------
def signed(v, decimals=1):
    return f"{'+' if v > 0 else ''}{v:.{decimals}f}"


def usd(v):
    """Dollar amount for HTML blocks (&#36; stops Streamlit reading $...$ as maths)."""
    return "n/a" if v is None or pd.isna(v) else f"&#36;{v:,.2f}"


def nice_date(ts):
    ts = pd.Timestamp(ts)
    return f"{ts.day} {ts.strftime('%b %Y')}"


def month_label(ts):
    return pd.Timestamp(ts).strftime("%B %Y")


def phase_for(date_str):
    for name, p in PHASES.items():
        start_month = p["start"][:8] + "01"
        if start_month <= date_str <= p["end"]:
            return name
    return None


# --------------------------------- figures -----------------------------------
def base_layout(**kwargs):
    layout = dict(template="plotly_white", font=dict(size=12, color="#1f2933"),
                  margin=dict(l=55, r=20, t=30, b=40))
    layout.update(kwargs)
    return layout


def shading(phase, sel_start):
    """Shaded rectangles: the chosen crisis phase and the month in focus."""
    shapes, annotations = [], []
    if phase and phase in PHASES:
        p = PHASES[phase]
        shapes.append(dict(type="rect", xref="x", yref="paper", x0=p["start"], x1=p["end"],
                           y0=0, y1=1, fillcolor=p["color"], opacity=0.15,
                           layer="below", line=dict(width=0)))
        mid = pd.Timestamp(p["start"]) + (pd.Timestamp(p["end"]) - pd.Timestamp(p["start"])) / 2
        annotations.append(dict(x=mid.strftime("%Y-%m-%d"), yref="paper", y=1, yanchor="bottom",
                                showarrow=False, text=f"<b>{phase}</b>",
                                font=dict(color=p["color"], size=12)))
    if sel_start is not None:
        s = pd.Timestamp(sel_start)
        shapes.append(dict(type="rect", xref="x", yref="paper", x0=s, x1=s + pd.offsets.MonthBegin(1),
                           y0=0, y1=1, fillcolor=COLORS["orange"], opacity=0.12,
                           layer="below", line=dict(width=0)))
    return shapes, annotations


def hline(y, text):
    shape = dict(type="line", xref="paper", x0=0, x1=1, y0=y, y1=y,
                 line=dict(dash="dash", color="#9aa5b1", width=1))
    note = dict(xref="paper", x=0.005, y=y, xanchor="left", yshift=10, showarrow=False,
                font=dict(size=11, color=COLORS["muted"]), text=text)
    return shape, note


def build_traffic_figure(daily, start, end, view, show_tankers, show_avg, phase, sel_start, base):
    as_pct = view == VIEW_OPTIONS[1] and base is not None
    d = daily.loc[(daily.index >= start) & (daily.index <= end)]
    fig = go.Figure()

    def add(col, name, color, width, dash=None):
        if as_pct:
            y = (d[col] / base[col.replace("_avg7", "")] - 1) * 100
            hover = f"{name}: %{{y:+.1f}}%<extra></extra>"
        else:
            y = d[col]
            hover = f"{name}: %{{y:.1f}}<extra></extra>"
        fig.add_trace(go.Scatter(x=d.index, y=y, name=name, mode="lines", connectgaps=False,
                                 line=dict(color=color, width=width, dash=dash), hovertemplate=hover))

    if as_pct:          # daily counts are too noisy as percentages, so show the averages only
        add("n_total_avg7", "All ships · 7-day avg", COLORS["navy"], 3)
        if show_tankers:
            add("n_tanker_avg7", "Tankers · 7-day avg", COLORS["blue"], 3)
    else:
        add("n_total", "All ships", "rgba(27,42,65,.35)", 1.2)
        if show_avg:
            add("n_total_avg7", "All ships · 7-day avg", COLORS["navy"], 3)
        if show_tankers:
            add("n_tanker", "Tankers", "rgba(46,134,222,.40)", 1.2)
            if show_avg:
                add("n_tanker_avg7", "Tankers · 7-day avg", COLORS["blue"], 3)

    shapes, annotations = shading(phase, sel_start)
    if base is not None:
        ref = 0 if as_pct else base["n_total"]
        s, a = hline(ref, "Pre-war average" if as_pct else f"Pre-war average {base['n_total']:.0f}/day")
        shapes.append(s)
        annotations.append(a)

    fig.update_layout(**base_layout(
        height=380, hovermode="x unified", showlegend=True,
        legend=dict(orientation="h", x=1, xanchor="right", y=1.12),
        margin=dict(l=55, r=20, t=40, b=40),
        yaxis=dict(title="% vs pre-war average" if as_pct else "vessels per day",
                   gridcolor="#edf0f3", zeroline=False, ticksuffix="%" if as_pct else ""),
        xaxis=dict(type="date", range=[start, end]),
        shapes=shapes, annotations=annotations))
    return fig


def build_brent_figure(brent, wti, start, end, view, show_wti, phase, sel_start):
    as_pct = view == VIEW_OPTIONS[1]
    b = brent.loc[(brent.index >= start) & (brent.index <= end)]
    transform = (lambda s: (s / PREWAR_PRICE - 1) * 100) if as_pct else (lambda s: s)
    fmt = "%{y:+.1f}%" if as_pct else "$%{y:.2f}"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=b.index, y=transform(b), name="Brent", mode="lines",
                             line=dict(color=COLORS["navy"], width=2.5),
                             hovertemplate=f"Brent: {fmt}<extra></extra>"))
    if not b.empty:     # marker on the latest observation
        fig.add_trace(go.Scatter(x=[b.index[-1]], y=transform(b.iloc[[-1]]), mode="markers", showlegend=False,
                                 marker=dict(size=10, symbol="diamond", color=COLORS["orange"],
                                             line=dict(color="#fff", width=1.5)),
                                 hovertemplate=f"{nice_date(b.index[-1])}: {fmt}<extra></extra>"))
    if show_wti and not as_pct and wti is not None and not wti.empty:
        w = wti.loc[(wti.index >= start) & (wti.index <= end)]
        fig.add_trace(go.Scatter(x=w.index, y=w, name="WTI", mode="lines",
                                 line=dict(color=COLORS["grey"], width=2),
                                 hovertemplate="WTI: $%{y:.2f}<extra></extra>"))

    shapes, annotations = shading(phase, sel_start)
    ref = 0 if as_pct else PREWAR_PRICE
    s, a = hline(ref, "Pre-war level" if as_pct else f"Pre-war ${PREWAR_PRICE:.2f}")
    shapes.append(s)
    annotations.append(a)

    fig.update_layout(**base_layout(
        height=380, hovermode="x unified", showlegend=bool(show_wti and not as_pct),
        legend=dict(orientation="h", x=1, xanchor="right", y=1.12),
        margin=dict(l=55, r=20, t=40, b=40),
        yaxis=dict(title="% vs pre-war" if as_pct else "USD per barrel", gridcolor="#edf0f3",
                   zeroline=False, ticksuffix="%" if as_pct else ""),
        xaxis=dict(type="date", range=[start, end]),
        shapes=shapes, annotations=annotations))
    return fig


def build_second_figure(mode, sel, monthly, daily, brent, start, end, phase):
    keep = dict(marker=dict(opacity=1))      # stops Plotly fading points after a click
    sel_start = monthly["Start"].iloc[sel]
    sel_date = monthly["DateStr"].iloc[sel]
    shapes, annotations = [], []
    yaxis2 = None
    xaxis = dict(type="date", range=[start, end])

    if mode == SECOND_OPTIONS[0]:
        title = "Average daily transits per month"
        sub = ("Light bars are all ships and dark bars are tankers (tankers are included in the total). "
               "The last month may be partial. Click a bar to select a month.")
        m = monthly.tail(MONTHS_SHOWN)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=m["DateStr"], y=m["Total"], name="All ships",
            marker_color=[COLORS["orange"] if d == sel_date else "#9db4d1" for d in m["DateStr"]],
            text=[f"{v:.0f}" for v in m["Total"]], textposition="outside", cliponaxis=False,
            selected=keep, unselected=keep,
            hovertemplate="%{x|%b %Y}: %{y:.1f} ships/day<extra></extra>"))
        fig.add_trace(go.Bar(
            x=m["DateStr"], y=m["Tankers"], name="Tankers", marker_color=COLORS["navy"],
            selected=keep, unselected=keep,
            hovertemplate="%{x|%b %Y}: %{y:.1f} tankers/day<extra></extra>"))
        fig.update_layout(barmode="overlay")
        yaxis = dict(gridcolor="#edf0f3", title="avg per day")
        xaxis = dict(type="date", tickformat="%b %y",
                     range=[m["Start"].iloc[0] - pd.Timedelta(days=17), m["Start"].iloc[-1] + pd.Timedelta(days=48)])
    elif mode == SECOND_OPTIONS[1]:
        title = "Tanker share of traffic"
        sub = "Tankers as a % of all ships, 7-day averages."
        d = daily.loc[(daily.index >= start) & (daily.index <= end)]
        fig = go.Figure(go.Scatter(
            x=d.index, y=d["share_avg7"], mode="lines", fill="tozeroy", fillcolor="rgba(142,68,173,.12)",
            line=dict(color=COLORS["purple"], width=2.5), connectgaps=False,
            hovertemplate="%{x|%d %b %Y}: %{y:.1f}%<extra></extra>"))
        yaxis = dict(gridcolor="#edf0f3", ticksuffix="%")
        shapes, annotations = shading(phase, sel_start)
    elif mode == SECOND_OPTIONS[2]:
        title = "Traffic and Brent, side by side"
        sub = "7-day average of ships per day (left) and Brent futures (right). Shown together, not as cause and effect."
        d = daily.loc[(daily.index >= start) & (daily.index <= end)]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=d.index, y=d["n_total_avg7"], name="Ships · 7-day avg", mode="lines",
                                 line=dict(color=COLORS["navy"], width=2.5), connectgaps=False,
                                 hovertemplate="Ships: %{y:.1f}/day<extra></extra>"))
        if brent is not None and not brent.empty:
            b = brent.loc[(brent.index >= start) & (brent.index <= end)]
            fig.add_trace(go.Scatter(x=b.index, y=b, name="Brent", mode="lines", yaxis="y2",
                                     line=dict(color=COLORS["purple"], width=2.5),
                                     hovertemplate="Brent: $%{y:.2f}<extra></extra>"))
        yaxis = dict(gridcolor="#edf0f3", title="ships per day")
        yaxis2 = dict(overlaying="y", side="right", showgrid=False, title="USD per barrel")
        shapes, annotations = shading(phase, sel_start)
    else:
        title = "Brent daily change"
        sub = "% change from the previous trading day. Red bars are rises and green bars are falls."
        if brent is None or brent.empty:
            chg = pd.Series(dtype=float)
        else:
            chg = (brent.pct_change() * 100).dropna()
            chg = chg.loc[(chg.index >= start) & (chg.index <= end)]
        fig = go.Figure(go.Bar(
            x=chg.index, y=chg, marker_color=[COLORS["red"] if v > 0 else COLORS["green"] for v in chg],
            hovertemplate="%{x|%d %b %Y}: %{y:+.2f}%<extra></extra>"))
        yaxis = dict(gridcolor="#edf0f3", ticksuffix="%", zeroline=True, zerolinecolor="#9aa5b1")
        shapes, annotations = shading(phase, sel_start)

    layout = base_layout(height=330, hovermode="x unified" if mode != SECOND_OPTIONS[0] else "closest",
                         showlegend=mode in (SECOND_OPTIONS[0], SECOND_OPTIONS[2]),
                         legend=dict(orientation="h", x=1, xanchor="right", y=1.12),
                         yaxis=yaxis, xaxis=xaxis, shapes=shapes, annotations=annotations)
    if yaxis2:
        layout["yaxis2"] = yaxis2
        layout["margin"] = dict(l=55, r=60, t=30, b=40)
    fig.update_layout(**layout)
    return fig, title, sub


# ------------------------------- HTML snippets -------------------------------
def header_html(ship_date, market_date):
    badge = f"SHIPPING TO {nice_date(ship_date).upper()}" if ship_date is not None else "SHIPPING UNAVAILABLE"
    if market_date is not None:
        badge += f" · MARKETS TO {nice_date(market_date).upper()}"
    return f"""
<div style="background:{COLORS['navy']};color:#fff;padding:18px 24px;border-radius:8px;
            display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:14px">
  <div>
    <div style="font-size:22px;font-weight:700">🚢 {TITLE}</div>
    <div style="color:#b8c4d3;font-size:13px;margin-top:3px">{SUBTITLE}</div>
  </div>
  <span style="background:{COLORS['orange']};color:#fff;font-weight:700;font-size:12px;padding:6px 10px;
               border-radius:4px;letter-spacing:.5px">{badge}</span>
</div>"""


def kpi_html(title, value, description, color):
    return f"""
<div style="background:#fff;border-radius:6px;padding:14px 16px;border-top:4px solid {color};
            box-shadow:0 1px 3px rgba(16,24,40,.12);height:100%">
  <div style="font-size:12px;color:{COLORS['muted']};font-weight:500;text-transform:uppercase;letter-spacing:.5px">{title}</div>
  <div style="font-size:27px;font-weight:700;color:{COLORS['navy']};margin:6px 0 2px">{value}</div>
  <div style="font-size:12px;color:{COLORS['muted']}">{description}</div>
</div>"""


def detail_html(row, is_last_month, last_date):
    d, month = row["DateStr"], row["Month"]

    def coloured(v):
        if pd.isna(v):
            return "n/a"
        colour = "#1e8449" if v > 0 else "#c0392b"      # less traffic = red
        return f'<span style="color:{colour}">{signed(v)}%</span>'

    days_txt = f"{int(row['Days'])} of {int(row['DaysInMonth'])}"
    rows = [("Ships per day (avg)", f"{row['Total']:.1f}"),
            ("Tankers per day (avg)", f"{row['Tankers']:.1f}"),
            ("Tanker share", f"{row['Share']:.1f}%"),
            ("vs previous month", coloured(row["MoM"])),
            ("vs pre-war traffic", coloured(row["vsPrewar"])),
            ("Brent average", usd(row["Brent"])),
            ("Days with data", days_txt)]
    table = "".join(
        f'<tr><td style="padding:7px 0;border-bottom:1px solid #eef0f3">{label}</td>'
        f'<td style="padding:7px 0;border-bottom:1px solid #eef0f3;text-align:right;font-weight:700">{value}</td></tr>'
        for label, value in rows)

    phase = phase_for(d)
    if phase:
        heading = f'<b style="color:{PHASES[phase]["color"]}">{phase}.</b> '
        text = MONTH_NOTES.get(month, PHASES[phase]["text"])
    else:
        heading = f"<b>{BEFORE_EVENTS_NOTE[0]}</b> "
        text = MONTH_NOTES.get(month, BEFORE_EVENTS_NOTE[1])
    if is_last_month and row["Days"] < row["DaysInMonth"]:
        text += f" <i>Partial month, data to {nice_date(last_date)}.</i>"

    return f"""
<div style="font-size:16px;font-weight:700;color:{COLORS['navy']}">Month in focus</div>
<div style="font-size:22px;font-weight:700;color:{COLORS['navy']}">{month_label(d)}</div>
<table style="width:100%;border-collapse:collapse;margin:10px 0;font-size:14px">{table}</table>
<div style="background:#f7f9fb;border-left:3px solid {COLORS['orange']};padding:10px 12px;font-size:13px;
            line-height:1.5;border-radius:0 4px 4px 0">{heading}{text}</div>"""


# ----------------------------- Streamlit helpers -----------------------------
def choice(label, options, default, key, style="segmented"):
    """Pills / segmented control on Streamlit 1.40+, radio buttons on older versions."""
    widget = getattr(st, "pills" if style == "pills" else "segmented_control", None)
    if widget is not None:
        value = widget(label, options, default=default, key=key)
        if value is None and style != "pills":   # a segmented control can be clicked off
            return default
        return value
    radio_options = options if style != "pills" else ["None"] + options
    index = radio_options.index(default) if default in radio_options else 0
    value = st.radio(label, radio_options, index=index, horizontal=True, key=key)
    return None if value == "None" else value


def apply_chart_click(chart_key, month_dates):
    """If the user clicked a point or bar on a chart, select that month."""
    state = st.session_state.get(chart_key)
    if not state:
        return
    try:
        points = state["selection"]["points"]
    except (KeyError, TypeError):
        return
    signature = tuple(str(p.get("x", ""))[:10] for p in points)
    last_key = f"{chart_key}_last"
    if signature and signature != st.session_state.get(last_key):
        x = signature[0][:7] + "-01"
        if x in month_dates:
            st.session_state["hs_sel"] = month_dates.index(x)
    st.session_state[last_key] = signature


def show_chart(fig, key):
    """Clickable chart on Streamlit 1.35+, normal chart on older versions."""
    try:
        st.plotly_chart(fig, use_container_width=True, key=key,
                        on_select="rerun", selection_mode="points",
                        config={"displayModeBar": False})
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=key,
                        config={"displayModeBar": False})


def step_month(delta, n):
    st.session_state["hs_sel"] = max(0, min(n - 1, st.session_state["hs_sel"] + delta))


def last_market_value(prices):
    return None if prices is None or prices.empty else float(prices.iloc[-1])


# ----------------------------------- PANEL ----------------------------------
def render():
    # ---- load data (same logic as before) ----
    shipping_df = None
    try:
        shipping_df = load_shipping_data()
    except Exception as error:
        st.error(f"Shipping data unavailable: {error}")

    market_data, market_errors = {}, []
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

    # ---- derived tables ----
    daily = base = monthly = None
    latest = previous = None
    if shipping_df is not None:
        daily = build_daily(shipping_df)
        base = prewar_baseline(shipping_df)
        monthly = build_monthly(shipping_df, brent, base)
        latest = shipping_df.iloc[-1]
        previous = shipping_df.iloc[-2] if len(shipping_df) >= 2 else None

    month_dates = monthly["DateStr"].tolist() if monthly is not None else []
    n_months = len(month_dates)
    st.session_state.setdefault("hs_sel", max(n_months - 1, 0))
    st.session_state["hs_sel"] = min(st.session_state["hs_sel"], max(n_months - 1, 0))
    apply_chart_click("hs_second_chart", month_dates)
    apply_chart_click("hs_traffic_chart", month_dates)
    apply_chart_click("hs_brent_chart", month_dates)
    sel = st.session_state["hs_sel"]

    ship_date = latest["date"] if latest is not None else None
    market_date = brent.index[-1] if not brent.empty else None
    st.markdown(header_html(ship_date, market_date), unsafe_allow_html=True)

    # ---- KPI cards ----
    def day_delta(col):
        # Only describe changes as daily when dates are consecutive.
        if previous is not None and latest["date"] - previous["date"] == pd.Timedelta(days=1):
            return f"{int(latest[col] - previous[col]):+d} vs previous day · "
        return ""

    def market_kpi(label, prices):
        if prices.empty:
            return (f"{label} futures", "n/a", "Unavailable", COLORS["grey"])
        change = percentage_change(prices)
        return (f"{label} futures", usd(float(prices.iloc[-1])),
                (f"{change:+.2f}% · " if change is not None else "") + f"{nice_date(prices.index[-1])}",
                COLORS["green"] if label == "BRENT" else COLORS["grey"])

    if latest is not None:
        total_kpi = ("Ship transits", f"{int(latest['n_total']):,}",
                     day_delta("n_total") + nice_date(latest["date"]), COLORS["navy"])
        tanker_kpi = ("Tanker transits", f"{int(latest['n_tanker']):,}",
                      day_delta("n_tanker") + nice_date(latest["date"]), COLORS["blue"])
        avg_now = daily["n_total_avg7"].dropna()
        share_now = daily["share_avg7"].dropna()
        if base and not avg_now.empty:
            traffic_kpi = ("Traffic vs pre-war", f"{signed(pct(base['n_total'], avg_now.iloc[-1]))}%",
                           f"7-day avg vs {base['n_total']:.0f}/day before the war", COLORS["red"])
        else:
            traffic_kpi = ("Traffic vs pre-war", "n/a", "Needs CSV data from the pre-war window", COLORS["red"])
        share_kpi = ("Tanker share", f"{share_now.iloc[-1]:.1f}%" if not share_now.empty else "n/a",
                     "7-day average", COLORS["purple"])
    else:
        total_kpi = ("Ship transits", "n/a", "Unavailable", COLORS["navy"])
        tanker_kpi = ("Tanker transits", "n/a", "Unavailable", COLORS["blue"])
        traffic_kpi = ("Traffic vs pre-war", "n/a", "Unavailable", COLORS["red"])
        share_kpi = ("Tanker share", "n/a", "Unavailable", COLORS["purple"])

    b_last, w_last = last_market_value(brent), last_market_value(wti)
    brent_war_kpi = ("Brent vs pre-war",
                     f"{signed(pct(PREWAR_PRICE, b_last))}%" if b_last else "n/a",
                     f"vs {usd(PREWAR_PRICE)} on {nice_date(PREWAR_DATE)}", COLORS["orange"])
    gap_kpi = ("Brent–WTI gap", usd(b_last - w_last) if b_last and w_last else "n/a",
               "Latest futures prices", COLORS["blue"])

    row1 = [total_kpi, tanker_kpi, market_kpi("BRENT", brent), market_kpi("WTI", wti)]
    row2 = [traffic_kpi, share_kpi, brent_war_kpi, gap_kpi]
    for row in (row1, row2):
        for col, (title, value, desc, colour) in zip(st.columns(4), row):
            col.markdown(kpi_html(title, value, desc, colour), unsafe_allow_html=True)
        st.write("")

    # ---- controls ----
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 1.5, 1.5])
        with c1:
            phase = choice("Highlight a phase of the crisis", list(PHASES), None,
                           key="hs_phase", style="pills")
            time_label = choice("Time range", list(TIME_RANGES), DEFAULT_RANGE, key="hs_range")
        with c2:
            view = choice("View", VIEW_OPTIONS, VIEW_OPTIONS[0], key="hs_view")
        with c3:
            show_tankers = st.checkbox("Show tankers", value=True, key="hs_tankers")
            show_avg = st.checkbox("Show 7-day averages", value=True, key="hs_avg")
            show_wti = st.checkbox("Compare Brent with WTI", key="hs_wti", disabled=view == VIEW_OPTIONS[1])

    # ---- chart time window ----
    days = TIME_RANGES[time_label]
    last_dates = [d for d in [ship_date, market_date] if d is not None]
    if last_dates:
        end = max(last_dates)
        first_dates = []
        if shipping_df is not None:
            first_dates.append(shipping_df["date"].min())
        if not brent.empty:
            first_dates.append(brent.index.min())
        start = end - pd.Timedelta(days=days - 1) if days else min(first_dates)
        end = end + pd.Timedelta(days=2)
    else:
        start = end = None

    sel_start = monthly["Start"].iloc[sel] if monthly is not None else None

    # ---- the two main charts, side by side ----
    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True):
            st.markdown(f"**Traffic through Hormuz**  \n<span style='font-size:12.5px;color:{COLORS['muted']}'>"
                        f"Daily vessel counts · IMF PortWatch. Tankers are included in all ships. "
                        f"The shaded month is the one in focus.</span>", unsafe_allow_html=True)
            if shipping_df is None:
                st.info("Shipping data is unavailable.")
            else:
                if view == VIEW_OPTIONS[1] and base is None:
                    st.caption("The CSV does not cover the pre-war window, so counts are shown instead of % changes.")
                show_chart(build_traffic_figure(daily, start, end, view, show_tankers, show_avg,
                                                phase, sel_start, base), key="hs_traffic_chart")
    with right:
        with st.container(border=True):
            st.markdown(f"**Brent futures**  \n<span style='font-size:12.5px;color:{COLORS['muted']}'>"
                        f"USD per barrel · Yahoo Finance. Daily closes; quotes may be delayed.</span>",
                        unsafe_allow_html=True)
            if brent.empty:
                st.info("Brent prices are temporarily unavailable.")
            else:
                show_chart(build_brent_figure(brent, wti, start, end, view, show_wti, phase, sel_start),
                           key="hs_brent_chart")

    # ---- second chart + month in focus ----
    if shipping_df is not None:
        left2, right2 = st.columns([2, 1])
        with left2:
            with st.container(border=True):
                mode = choice("Second chart", SECOND_OPTIONS, SECOND_OPTIONS[0], key="hs_second")
                fig, title, sub = build_second_figure(mode, sel, monthly, daily, brent, start, end, phase)
                st.markdown(f"**{title}**  \n<span style='font-size:12.5px;color:{COLORS['muted']}'>{sub}</span>",
                            unsafe_allow_html=True)
                show_chart(fig, key="hs_second_chart")
        with right2:
            with st.container(border=True):
                st.markdown(detail_html(monthly.iloc[sel], sel == n_months - 1, latest["date"]),
                            unsafe_allow_html=True)
                b1, b2 = st.columns(2)
                b1.button("◀ Previous", key="hs_prev", on_click=step_month, args=(-1, n_months),
                          use_container_width=True, disabled=sel == 0)
                b2.button("Next ▶", key="hs_next", on_click=step_month, args=(1, n_months),
                          use_container_width=True, disabled=sel == n_months - 1)
                st.caption("Or click a bar in the monthly chart.")

    # ---- additional market indicators ----
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

    # ---- data and download ----
    with st.expander("Shipping data and download"):
        if shipping_df is None:
            st.info("No shipping data available.")
        else:
            st.markdown("**Monthly summary**")
            summary = monthly[["Month", "Total", "Tankers", "Share", "vsPrewar", "Brent", "Days"]].rename(
                columns={"Total": "Ships/day", "Tankers": "Tankers/day", "Share": "Tanker share %",
                         "vsPrewar": "vs pre-war %", "Brent": "Brent avg", "Days": "Days with data"})
            st.dataframe(summary.sort_values("Month", ascending=False).round(1),
                         use_container_width=True, hide_index=True)

            st.markdown("**Daily records**")
            st.dataframe(
                shipping_df.sort_values("date", ascending=False),
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                label="Download Hormuz data",
                data=shipping_df.to_csv(index=False).encode("utf-8"),
                file_name="hormuz_shipping.csv",
                mime="text/csv",
                key="download_hormuz_shipping",
            )

    # ---- sources ----
    base_txt = (f" Pre-war traffic is the average of daily transits between {nice_date(BASELINE_START)} "
                f"and {nice_date(BASELINE_END)}." if base else "")
    st.caption(
        "Sources: IMF PortWatch (Hormuz daily transits) and Yahoo Finance (market prices). "
        "Shipping data updates when the CSV is replaced. Market requests are cached for five minutes "
        "and run when the app executes. Shipping and market observations may have different dates. "
        f"The pre-war Brent reference is the {nice_date(PREWAR_DATE)} price (USD {PREWAR_PRICE:.2f})."
        + base_txt
    )
    st.caption(
        "These charts show traffic and prices separately; "
        "they do not establish a causal relationship."
    )


# Allows this file to run independently.
# When imported by app.py, the main dashboard calls render().
if __name__ == "__main__":
    st.set_page_config(
        page_title=TITLE,
        layout="wide",
    )
    render()
