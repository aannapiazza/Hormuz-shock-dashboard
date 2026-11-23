"""
panels/oil.py — Oil prices panel (Erin)
Hormuz Oil Shock Dashboard (Streamlit)

How the 2026 Iran war and the near-closure of the Strait of Hormuz moved the
price of crude oil.

HOW TO USE
  • In the group app: listed in PANELS as ("🛢️ Oil prices", "panels/oil.py", "Erin").
    The main app runs this file, and the dashboard draws itself.
  • On its own, for testing:   streamlit run panels/oil.py

HOW TO CHANGE IT
  Everything you're likely to edit is in the "EDIT HERE" section just below.
  The KPI cards, charts, labels and dates all update from it automatically,
  so you shouldn't need to touch anything further down.

Requires: streamlit (1.35+ for clickable charts, 1.40+ for pill buttons), plotly,
pandas, numpy. Older Streamlit versions still work, with radio buttons instead.
All widget keys start with "ho_" so they can't clash with the other panels.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# =============================================================================
# ✏️  EDIT HERE
# =============================================================================

# 0) DATA SETTINGS
END = pd.Timestamp("2026-10-31")     # cut-off: nothing after this date is used anywhere
START = pd.Timestamp("2025-09-01")   # first month shown on the charts
LIVE = False                         # False = use the saved copies in data/ (default)
                                     # True  = download fresh data from FRED, cut it at END, save it to data/
# Data files: (FRED series ID, file name in data/)
BRENT_MONTHLY = ("MCOILBRENTEU", "oil_monthly_brent_data.csv")   # Brent - Europe, monthly average
WTI_MONTHLY = ("MCOILWTICO", "oil_monthly_wti_data.csv")         # WTI - Cushing, Oklahoma, monthly average
BRENT_DAILY = ("DCOILBRENTEU", "oil_daily_brent_data.csv")       # Brent - Europe, daily

# 1) LATEST PRICE AND PRE-WAR REFERENCE
#    Both are read from the daily file: the latest price is the last one on or before END,
#    and the pre-war price is the last one on or before PREWAR_DATE.
PREWAR_DATE = "2026-02-27"           # last trading day before the war (our choice)
LATEST_LABEL = "Daily spot"

# 2) ESTIMATED FIGURES — months marked with * on the page.
#    Delete a line once you have the real figure.
ESTIMATED_MONTHS = {
    # "YYYY-MM": "note explaining the estimate",
}

# 3) EVENTS — the phase buttons that shade the chart.
#    "Button name": ("start YYYY-MM-DD", "end YYYY-MM-DD", "colour", "description")
#    Build-up start (1 Jan) is our choice. Prices and "highest since" come from the FRED data.
#    Sources for the dates (also in data/oil_event_sources.csv):
#      28 Feb war: S&P Global, 28 Feb 2026, "Iran claims Hormuz is shut down after IRGC threat to shipping"
#      8 Apr ceasefire: ING Think, 8 Apr 2026, "Oil slumps below $100 after US, Iran agree to two-week ceasefire"
#      8 Jul US strikes: Reuters photo caption via Al-Monitor, 12 Jul 2026,
#        "Iran's IRGC navy says Strait of Hormuz closed until further notice, state media"
EVENTS = {
    "Build-up": ("2026-01-01", "2026-02-28", "#e0a800",
                 "Brent's monthly average climbs from $62.54 in December to $70.89 in February."),
    "War & closure": ("2026-02-28", "2026-04-08", "#d64545",
                      "US–Israel strikes on 28 Feb, and Iran says it has shut the strait. Brent's March "
                      "average jumps 45%, the biggest rise since 2020."),
    "Ceasefire": ("2026-04-08", "2026-07-08", "#2e86de",
                  "Brent falls as much as 16% on the 8 Apr ceasefire, and the monthly average drops to "
                  "$83.76 by July."),
    "Conflict resumes": ("2026-07-08", "2026-10-31", "#8e44ad",
                         "US strikes resume on 8 Jul. Brent rises to a $124 average in October, the highest "
                         "since March 2012."),
}

# 4) MONTH NOTES — shown in the "Month in focus" panel. "YYYY-MM": "note".
#    Months without a note show their event's description instead. Add a source for any note you add.
MONTH_NOTES = {}
BEFORE_EVENTS_NOTE = ("Before the war.", "Brent averages $62–68 a month, its lowest level since early 2021.")

# 5) TEXT
TITLE = "Hormuz Oil Shock Dashboard"
SUBTITLE = "How the 2026 Iran war and the near-closure of the Strait of Hormuz have moved the price of crude"
SOURCE_FRED = ("U.S. Energy Information Administration via FRED: Europe Brent (MCOILBRENTEU, DCOILBRENTEU) "
               "and Cushing WTI (MCOILWTICO) spot prices")

# 6) COLOURS
COLORS = {"navy": "#1b2a41", "orange": "#f2711c", "muted": "#6b7785",
          "red": "#d64545", "green": "#27ae60", "blue": "#2e86de",
          "purple": "#8e44ad", "grey": "#7f8c8d"}

# =============================================================================
# (You shouldn't need to change anything below this line.)
# =============================================================================


# ----------------------------- data preparation -----------------------------
def data_folder():
    """The repo's data/ folder (this file lives in panels/, one level down)."""
    here = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    for folder in (here.parent / "data", here / "data", Path.cwd() / "data"):
        if folder.is_dir():
            return folder
    return here.parent / "data"


def up_to_end(series):
    """Throw away anything after the END cut-off date."""
    return series[series.index <= END]


def read_fred_csv(source, monthly=True):
    """Read a FRED CSV (file or URL) into a Series (one value per month if monthly=True).
    Handles both FRED layouts and '.' or blank for missing values."""
    raw = pd.read_csv(source)
    values = pd.to_numeric(raw.iloc[:, 1], errors="coerce").values
    series = pd.Series(values, index=pd.to_datetime(raw.iloc[:, 0], errors="coerce"))
    series = series[series.index.notna()].dropna()
    if not monthly:
        return series.sort_index()
    series.index = series.index.to_period("M").to_timestamp()   # first of the month
    return series.groupby(level=0).mean().sort_index()


def download(series, monthly=True):
    """Fresh copy from FRED, cut at END, then saved over the copy in data/."""
    series_id, file_name = series
    data = up_to_end(read_fred_csv(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", monthly))
    try:
        data.rename(series_id).rename_axis("observation_date").to_csv(data_folder() / file_name)
    except OSError:
        pass   # e.g. a read-only server: still use the download, just don't save it
    return data


def load_series(series, monthly=True):
    """LIVE = True: download (falling back to the saved copy if that fails).
    LIVE = False: the saved copy. Either way it's cut at END again, just in case."""
    if LIVE:
        try:
            return up_to_end(download(series, monthly)), "downloaded from FRED"
        except Exception:
            pass
    return up_to_end(read_fred_csv(data_folder() / series[1], monthly)), "saved copy in data/"


# The latest and pre-war prices come from the daily file
DAILY = load_series(BRENT_DAILY, monthly=False)[0]
LATEST_DATE, LATEST_PRICE = DAILY.index[-1].strftime("%Y-%m-%d"), DAILY.iloc[-1]
PREWAR_DATE, PREWAR_PRICE = DAILY[:PREWAR_DATE].index[-1].strftime("%Y-%m-%d"), DAILY[:PREWAR_DATE].iloc[-1]
LATEST_NOTE = f"The latest price is the daily spot price on {LATEST_DATE[8:].lstrip('0')} {pd.Timestamp(LATEST_DATE):%b %Y}."


def add_metrics(df):
    df = df.sort_values("Date").reset_index(drop=True)
    df["Month"] = df["Date"].dt.strftime("%Y-%m")
    df["MoM"] = (df["Brent"] / df["Brent"].shift(1) - 1) * 100
    df["Volatility"] = df["MoM"].rolling(window=3).std() * np.sqrt(12)
    df["Spread"] = df["Brent"] - df["WTI"]
    df["YoY"] = (df["Brent"] / df["Brent"].shift(12) - 1) * 100
    df["vsPrewar"] = (df["Brent"] / PREWAR_PRICE - 1) * 100
    df["DateStr"] = df["Date"].dt.strftime("%Y-%m-%d")
    return df


def build_data():
    """Returns (data, source description, warning or None)."""
    brent, how = load_series(BRENT_MONTHLY)
    try:
        wti, _ = load_series(WTI_MONTHLY)
    except Exception:
        wti = pd.Series(dtype=float)
    df = pd.DataFrame({"Brent": brent})
    df["WTI"] = wti.reindex(df.index)
    df = add_metrics(df.rename_axis("Date").reset_index())   # full history, so YoY works
    df = df[(df["Date"] >= START) & (df["Date"] <= END)].reset_index(drop=True)
    return df, f"{SOURCE_FRED} ({how})", None


OIL, DATA_SOURCE, DATA_WARNING = build_data()
N = len(OIL)
DATES = OIL["DateStr"].tolist()
PHASES = {name: {"start": s, "end": e, "color": c, "text": t} for name, (s, e, c, t) in EVENTS.items()}

VIEW_OPTIONS = ["$ per barrel", "% vs pre-war"]
SECOND_OPTIONS = ["Monthly change", "3-month volatility", "Brent–WTI gap"]


def shift_days(date_str, days):
    return (pd.Timestamp(date_str) + pd.Timedelta(days=days)).strftime("%Y-%m-%d")


CHART_START = shift_days(DATES[0], -17)
MAIN_CHART_END = shift_days(max(LATEST_DATE, DATES[-1]), 11)
SECOND_CHART_END = shift_days(DATES[-1], 19)


def pct(old, new):
    return (new / old - 1) * 100


def signed(v, decimals=1):
    return f"{'+' if v > 0 else ''}{v:.{decimals}f}"


def month_label(date_str):
    return pd.Timestamp(date_str).strftime("%B %Y")


def nice_date(date_str):
    ts = pd.Timestamp(date_str)
    return f"{ts.day} {ts.strftime('%b %Y')}"


# --------------------------------- figures ----------------------------------
def base_layout(**kwargs):
    layout = dict(template="plotly_white", font=dict(size=12, color="#1f2933"),
                  margin=dict(l=55, r=20, t=20, b=40))
    layout.update(kwargs)
    return layout


def build_main_figure(phase, view, show_wti, sel):
    as_pct = view == VIEW_OPTIONS[1]

    def transform(values):
        values = np.array(values, dtype=float)
        return pct(PREWAR_PRICE, values) if as_pct else values

    unit = "% vs pre-war" if as_pct else "$/bbl"
    fmt = "%{y:+.1f}%" if as_pct else "$%{y:.2f}"
    keep_visible = dict(marker=dict(opacity=1))   # stops Plotly fading points after a click

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=DATES, y=transform(OIL["Brent"]), name="Brent", mode="lines+markers",
        line=dict(color=COLORS["navy"], width=3),
        marker=dict(size=[13 if i == sel else 7 for i in range(N)],
                    color=[COLORS["orange"] if i == sel else COLORS["navy"] for i in range(N)],
                    line=dict(color="#ffffff", width=1.5)),
        selected=keep_visible, unselected=keep_visible,
        hovertemplate=f"Brent: {fmt}<extra></extra>",
    ))
    if LATEST_DATE > DATES[-1]:   # dotted extension to the latest daily price
        fig.add_trace(go.Scatter(
            x=[DATES[-1], LATEST_DATE], y=transform([OIL["Brent"].iloc[-1], LATEST_PRICE]),
            name="Latest", mode="lines+markers", showlegend=False,
            line=dict(color=COLORS["navy"], width=2, dash="dot"),
            marker=dict(size=[0, 9], symbol="diamond", color=COLORS["orange"]),
            selected=keep_visible, unselected=keep_visible,
            hovertemplate=f"{nice_date(LATEST_DATE)} {LATEST_LABEL.lower()}: {fmt}<extra></extra>",
        ))
    if show_wti:
        fig.add_trace(go.Scatter(
            x=DATES, y=transform(OIL["WTI"]), name="WTI", mode="lines+markers",
            line=dict(color=COLORS["grey"], width=2), marker=dict(size=5),
            selected=keep_visible, unselected=keep_visible,
            connectgaps=False, hovertemplate=f"WTI: {fmt}<extra></extra>",
        ))

    ref = 0 if as_pct else PREWAR_PRICE
    shapes = [dict(type="line", xref="paper", x0=0, x1=1, y0=ref, y1=ref,
                   line=dict(dash="dash", color="#9aa5b1", width=1))]
    annotations = [dict(xref="paper", x=0.005, y=ref, xanchor="left", yshift=10,
                        showarrow=False, font=dict(size=11, color=COLORS["muted"]),
                        text="Pre-war level" if as_pct else f"Pre-war ${PREWAR_PRICE:.2f}")]

    if phase and phase in PHASES:
        p = PHASES[phase]
        shapes.append(dict(type="rect", xref="x", yref="paper", x0=p["start"], x1=p["end"],
                           y0=0, y1=1, fillcolor=p["color"], opacity=0.15,
                           layer="below", line=dict(width=0)))
        mid = pd.Timestamp(p["start"]) + (pd.Timestamp(p["end"]) - pd.Timestamp(p["start"])) / 2
        annotations.append(dict(x=mid.strftime("%Y-%m-%d"), yref="paper", y=1, yanchor="bottom",
                                showarrow=False, text=f"<b>{phase}</b>",
                                font=dict(color=p["color"], size=12)))

    fig.update_layout(**base_layout(
        height=430, hovermode="x unified", showlegend=bool(show_wti),
        legend=dict(orientation="h", x=1, xanchor="right", y=1.12),
        margin=dict(l=55, r=20, t=40, b=40),
        yaxis=dict(title=unit, gridcolor="#edf0f3", zeroline=False),
        xaxis=dict(type="date", range=[CHART_START, MAIN_CHART_END],
                   rangeselector=dict(
                       x=0, y=1.1, bgcolor="#f2f4f7", activecolor="#d6dde6",
                       buttons=[dict(count=3, label="3M", step="month", stepmode="backward"),
                                dict(count=6, label="6M", step="month", stepmode="backward"),
                                dict(step="all", label="All")])),
        shapes=shapes, annotations=annotations,
    ))
    return fig


def build_second_figure(mode, sel):
    def highlight(i, normal):
        return COLORS["orange"] if i == sel else normal

    keep_visible = dict(marker=dict(opacity=1))

    if mode == SECOND_OPTIONS[1]:
        title = "Rolling 3-month volatility"
        sub = "Annualised standard deviation of monthly % changes. Higher means a more erratic market."
        fig = go.Figure(go.Scatter(
            x=DATES, y=OIL["Volatility"], mode="lines+markers", fill="tozeroy",
            fillcolor="rgba(142,68,173,.12)",
            line=dict(color=COLORS["purple"], width=2.5, shape="spline"),
            marker=dict(size=[11 if i == sel else 6 for i in range(N)],
                        color=[highlight(i, COLORS["purple"]) for i in range(N)]),
            selected=keep_visible, unselected=keep_visible,
            hovertemplate="%{x|%b %Y}: %{y:.1f}<extra></extra>",
        ))
        yaxis = dict(gridcolor="#edf0f3")
    elif mode == SECOND_OPTIONS[2]:
        title = "Brent–WTI price gap"
        sub = "$ per barrel. The gap widens when Middle East supply is cut and the US is relatively insulated."
        spread = OIL["Spread"]
        fig = go.Figure(go.Bar(
            x=DATES, y=spread,
            marker_color=[highlight(i, COLORS["blue"]) for i in range(N)],
            text=["" if pd.isna(v) else f"${v:.1f}" for v in spread],
            textposition="outside", cliponaxis=False,
            selected=keep_visible, unselected=keep_visible,
            hovertemplate="%{x|%b %Y}: $%{y:.2f}<extra></extra>",
        ))
        yaxis = dict(gridcolor="#edf0f3", tickprefix="$")
    else:
        title = "Month-on-month change"
        sub = "% change in the monthly average. Red bars are rises and green bars are falls."
        mom = OIL["MoM"]
        colors = ["#cccccc" if pd.isna(v) else highlight(i, COLORS["red"] if v > 0 else COLORS["green"])
                  for i, v in enumerate(mom)]
        fig = go.Figure(go.Bar(
            x=DATES, y=mom, marker_color=colors,
            text=["" if pd.isna(v) else f"{signed(v)}%" for v in mom],
            textposition="outside", cliponaxis=False,
            selected=keep_visible, unselected=keep_visible,
            hovertemplate="%{x|%b %Y}: %{y:+.1f}%<extra></extra>",
        ))
        yaxis = dict(gridcolor="#edf0f3", ticksuffix="%", zeroline=True, zerolinecolor="#9aa5b1")

    fig.update_layout(**base_layout(
        height=330, showlegend=False, yaxis=yaxis,
        xaxis=dict(type="date", tickformat="%b %y", range=[CHART_START, SECOND_CHART_END]),
    ))
    return fig, title, sub


def phase_for(date_str):
    for name, p in PHASES.items():
        start_month = p["start"][:8] + "01"
        if start_month <= date_str <= p["end"]:
            return name
    return None


# ------------------------------- HTML snippets -------------------------------
def header_html():
    return f"""
<div style="color:{COLORS['navy']};padding:6px 0 10px;
            display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:14px">
  <div>
    <div style="font-size:22px;font-weight:700">{TITLE}</div>
    <div style="color:{COLORS['muted']};font-size:13px;margin-top:3px">{SUBTITLE}</div>
  </div>
  <span style="background:{COLORS['orange']};color:#fff;font-weight:700;font-size:12px;padding:6px 10px;
               border-radius:4px;letter-spacing:.5px">BRENT · DATA TO {nice_date(END).upper()}</span>
</div>"""


def kpi_html(title, value, description, color):
    return f"""
<div style="background:#fff;border-radius:6px;padding:14px 16px;border-top:4px solid {color};
            box-shadow:0 1px 3px rgba(16,24,40,.12);height:100%">
  <div style="font-size:12px;color:{COLORS['muted']};font-weight:500;text-transform:uppercase;letter-spacing:.5px">{title}</div>
  <div style="font-size:27px;font-weight:700;color:{COLORS['navy']};margin:6px 0 2px">{value}</div>
  <div style="font-size:12px;color:{COLORS['muted']}">{description}</div>
</div>"""


def detail_html(sel):
    row = OIL.iloc[sel]
    d, month = row["DateStr"], row["Month"]

    def coloured(v):
        if pd.isna(v):
            return "n/a"
        colour = "#c0392b" if v > 0 else "#1e8449"
        return f'<span style="color:{colour}">{signed(v)}%</span>'

    estimated = month in ESTIMATED_MONTHS
    brent_txt = f"${row['Brent']:.2f}" + ("*" if estimated else "")
    wti_txt = "n/a" if pd.isna(row["WTI"]) else f"${row['WTI']:.2f}"
    rows = [("Brent average", brent_txt), ("WTI average", wti_txt),
            ("vs previous month", coloured(row["MoM"])),
            ("vs same month last year", coloured(row["YoY"])),
            ("vs pre-war price", coloured(row["vsPrewar"]))]
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
    if estimated:
        text += f" <i>*{ESTIMATED_MONTHS[month]}</i>"

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


def apply_chart_click(chart_key):
    """If the user clicked a new point on a chart, select that month."""
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
        if x in DATES:
            st.session_state["ho_sel"] = DATES.index(x)
    st.session_state[last_key] = signature


def show_chart(fig, key):
    """Clickable chart on Streamlit 1.35+, normal chart on older versions."""
    try:
        st.plotly_chart(fig, key=key,
                        on_select="rerun", selection_mode="points",
                        config={"displayModeBar": False})
    except TypeError:
        st.plotly_chart(fig, key=key,
                        config={"displayModeBar": False})


def step_month(delta):
    st.session_state["ho_sel"] = max(0, min(N - 1, st.session_state["ho_sel"] + delta))


# ----------------------------------- page ------------------------------------
def render():
    """Draw the oil prices panel."""
    st.session_state.setdefault("ho_sel", N - 1)
    st.session_state["ho_sel"] = min(st.session_state["ho_sel"], N - 1)
    apply_chart_click("ho_main_chart")
    apply_chart_click("ho_second_chart")
    sel = st.session_state["ho_sel"]

    st.markdown(header_html(), unsafe_allow_html=True)
    if DATA_WARNING:
        st.warning(DATA_WARNING, icon="⚠️")

    # KPI row
    peak_idx = OIL["Brent"].idxmax()
    spread_rows = OIL.dropna(subset=["Spread"])
    kpis = [
        ("Latest Brent price", f"${LATEST_PRICE:.2f}", f"{LATEST_LABEL}, {nice_date(LATEST_DATE)}", COLORS["blue"]),
        ("Change since pre-war", f"{signed(pct(PREWAR_PRICE, LATEST_PRICE))}%",
         f"vs ${PREWAR_PRICE:.2f} on {nice_date(PREWAR_DATE)}", COLORS["red"]),
        ("Highest monthly average", f"${OIL.loc[peak_idx, 'Brent']:.2f}",
         month_label(OIL.loc[peak_idx, "DateStr"]), COLORS["orange"]),
        ("Brent–WTI gap",
         f"${spread_rows['Spread'].iloc[-1]:.2f}" if not spread_rows.empty else "n/a",
         f"{month_label(spread_rows['DateStr'].iloc[-1])} average" if not spread_rows.empty else "",
         COLORS["purple"]),
    ]
    for col, (title, value, desc, colour) in zip(st.columns(4), kpis):
        col.markdown(kpi_html(title, value, desc, colour), unsafe_allow_html=True)
    st.write("")

    # controls
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 1.4, 1.4])
        with c1:
            phase = choice("Highlight a phase of the crisis", list(PHASES), None,
                           key="ho_phase", style="pills")
        with c2:
            view = choice("Price view", VIEW_OPTIONS, VIEW_OPTIONS[0], key="ho_view")
        with c3:
            st.write("")
            show_wti = st.checkbox("Compare with WTI (US benchmark)", key="ho_wti")

    # main chart
    with st.container(border=True):
        st.markdown(f"**Brent crude, monthly average**  \n"
                    f"<span style='font-size:12.5px;color:{COLORS['muted']}'>Click any month to see its "
                    f"details below. Use the buttons on the chart to zoom to the last 3 or 6 months.</span>",
                    unsafe_allow_html=True)
        show_chart(build_main_figure(phase, view, show_wti, sel), key="ho_main_chart")

    # second chart + month in focus
    left, right = st.columns([2, 1])
    with left:
        with st.container(border=True):
            mode = choice("Second chart", SECOND_OPTIONS, SECOND_OPTIONS[0], key="ho_second")
            fig, title, sub = build_second_figure(mode, sel)
            st.markdown(f"**{title}**  \n<span style='font-size:12.5px;color:{COLORS['muted']}'>{sub}</span>",
                        unsafe_allow_html=True)
            show_chart(fig, key="ho_second_chart")
    with right:
        with st.container(border=True):
            st.markdown(detail_html(sel), unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            b1.button("◀ Previous", key="ho_prev", on_click=step_month, args=(-1,),
                      disabled=sel == 0)
            b2.button("Next ▶", key="ho_next", on_click=step_month, args=(1,),
                      disabled=sel == N - 1)
            st.caption("Or click a point on either chart.")

    notes = " ".join(f"*{text}" for text in ESTIMATED_MONTHS.values())
    footer = (f"Data: {DATA_SOURCE}. {LATEST_NOTE} {notes} The pre-war reference is the {nice_date(PREWAR_DATE)} price "
              f"(${PREWAR_PRICE:.2f}).")
    st.caption(footer.replace("$", "\\$"))   # escape $ so Streamlit doesn't treat it as maths


# -----------------------------------------------------------------------------
# The group app runs this file directly (see PANELS in the main app), so the
# dashboard draws as soon as the file is run. set_page_config is only for
# testing on its own (streamlit run panels/oil.py). Inside the group app the
# main app has already set it, so any error from a second call is ignored.
# -----------------------------------------------------------------------------
def render_card():
    """Small summary for the home page (app.py calls this)."""
    a, b = st.columns(2)
    a.metric("Brent crude, 30 Oct", f"${LATEST_PRICE:.2f}",
             f"{signed(pct(PREWAR_PRICE, LATEST_PRICE))}% since pre-war", delta_color="inverse")
    b.metric("Brent–WTI gap, Oct", f"${OIL['Spread'].iloc[-1]:.2f}",
             f"{OIL['Spread'].iloc[-1] - OIL['Spread'].iloc[0]:+.2f} vs Sep 2025", delta_color="inverse")


if __name__ == "__main__":
    # Run this panel on its own:  python3 -m streamlit run panels/oil.py
    try:
        st.set_page_config(page_title=TITLE, layout="wide")
    except Exception:
        pass
    render()
