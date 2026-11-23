"""panels/oil.py — Hormuz Oil Shock Dashboard (Erin). Run on its own: python3 -m streamlit run panels/oil.py
Everything you're likely to change is in the EDIT HERE section. Widget keys start with "ho_"."""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# =============================================================================
# ✏️  EDIT HERE
# =============================================================================
END = pd.Timestamp("2026-10-31")     # cut-off: nothing after this date is used anywhere
START = pd.Timestamp("2025-09-01")   # first month shown on the charts
LIVE = False                         # False = use the saved copies in data/ (default)
                                     # True  = download fresh data from FRED, cut it at END, save it to data/
# Data files: (FRED series ID, file name in data/)
BRENT_MONTHLY = ("MCOILBRENTEU", "oil_monthly_brent_data.csv")   # Brent - Europe, monthly average
WTI_MONTHLY = ("MCOILWTICO", "oil_monthly_wti_data.csv")         # WTI - Cushing, Oklahoma, monthly average
BRENT_DAILY = ("DCOILBRENTEU", "oil_daily_brent_data.csv")       # Brent - Europe, daily
PREWAR_DATE = "2026-02-27"           # last trading day before the war. The latest and pre-war prices are both
                                     # read from the daily file (the last price on or before END / PREWAR_DATE).
# Sources for the events and notes below: S&P Global (28 Feb 2026, "Iran claims Hormuz is shut down"),
# ING Think (8 Apr 2026, "Oil slumps below $100 after US, Iran agree to two-week ceasefire"),
# Al Jazeera (30 Oct 2026, "Oil flows are up as Iran war turmoil eases. Why do prices keep rising?").

# Phase buttons that shade the chart: "Name": ("start", "end", "colour", "description")
EVENTS = {
    "Build-up": ("2026-01-01", "2026-02-28", "#e0a800",
                 "Prices drift up as markets price in the risk of war with Iran."),
    "War & closure": ("2026-02-28", "2026-04-08", "#d64545",
                      "The US–Israel strikes on 28 Feb trigger the near-closure of Hormuz. The IEA calls it "
                      "the largest supply disruption in history, and Brent peaks near $138 on 7 Apr."),
    "Ceasefire": ("2026-04-08", "2026-07-07", "#2e86de",
                  "Brent drops about 16% on the 8 Apr ceasefire and falls again after the 17 Jun US–Iran "
                  "MOU, but tanker traffic barely recovers."),
    "Conflict resumes": ("2026-07-07", "2026-10-31", "#8e44ad",
                         "Strikes resume on 7 Jul. With inventories falling, Brent rises for three months "
                         "to a $124 average in October, the highest since mid-2022."),
}
# Notes for the "Month in focus" panel. Months without a note show their phase's description.
MONTH_NOTES = {
    "2026-03": "War begins on 28 Feb. This is the biggest one-month jump in the series.",
    "2026-04": "The peak month. Brent hit $138 on 7 Apr, before the next day's ceasefire.",
    "2026-05": "Talks stall and the strait stays effectively shut.",
    "2026-06": "The 17 Jun MOU raises hopes that the strait will reopen.",
    "2026-07": "Strikes resume on 7 Jul, and Iran declares the strait closed on 12 Jul.",
    "2026-09": "Prices rebound as global inventories keep falling.",
    "2026-10": "The highest monthly average since July 2022, and the worst month yet for attacks on ships.",
}
BEFORE_EVENTS_NOTE = ("Before the war.", "Prices sit in the low-to-mid $60s on oversupply, the lowest since 2021.")

TITLE = "Hormuz Oil Shock Dashboard"
SUBTITLE = "How the 2026 Iran war and the near-closure of the Strait of Hormuz have moved the price of crude"
SOURCE = ("U.S. Energy Information Administration via FRED: Europe Brent (MCOILBRENTEU, DCOILBRENTEU) and "
          "Cushing WTI (MCOILWTICO) spot prices")
COLORS = {"navy": "#1b2a41", "orange": "#f2711c", "muted": "#6b7785", "red": "#d64545",
          "green": "#27ae60", "blue": "#2e86de", "purple": "#8e44ad", "grey": "#7f8c8d"}
# =============================================================================
# (You shouldn't need to change anything below this line.)
# =============================================================================

# ---------------------------------- data ----------------------------------
def data_folder():
    here = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    for folder in (here.parent / "data", here / "data", Path.cwd() / "data"):
        if folder.is_dir():
            return folder
    return here.parent / "data"

def up_to_end(series):
    """Throw away anything after the END cut-off date."""
    return series[series.index <= END]

def read_fred_csv(source, monthly=True):
    """Read a FRED CSV (file or URL) into a Series (one value per month if monthly=True)."""
    raw = pd.read_csv(source)
    series = pd.Series(pd.to_numeric(raw.iloc[:, 1], errors="coerce").values,
                       index=pd.to_datetime(raw.iloc[:, 0], errors="coerce")).dropna()
    if not monthly:
        return series.sort_index()
    series.index = series.index.to_period("M").to_timestamp()
    return series.groupby(level=0).mean().sort_index()

def load_series(series, monthly=True):
    """LIVE: download from FRED, cut at END and save to data/. Otherwise read the saved copy."""
    series_id, file_name = series
    path = data_folder() / file_name
    if LIVE:
        try:
            series = up_to_end(read_fred_csv(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", monthly))
            series.rename(series_id).rename_axis("observation_date").to_csv(path)
            return series, "downloaded from FRED"
        except Exception:
            pass   # no internet or read-only folder: fall back to the saved copy
    return up_to_end(read_fred_csv(path, monthly)), "saved copy in data/"

brent, HOW = load_series(BRENT_MONTHLY)
daily = load_series(BRENT_DAILY, monthly=False)[0]
LATEST_DATE, LATEST_PRICE = daily.index[-1].strftime("%Y-%m-%d"), daily.iloc[-1]
PREWAR_DATE, PREWAR_PRICE = daily[:PREWAR_DATE].index[-1].strftime("%Y-%m-%d"), daily[:PREWAR_DATE].iloc[-1]
OIL = pd.DataFrame({"Brent": brent, "WTI": load_series(WTI_MONTHLY)[0]}).rename_axis("Date").reset_index()
OIL["MoM"] = OIL["Brent"].pct_change() * 100
OIL["Volatility"] = OIL["MoM"].rolling(3).std() * np.sqrt(12)
OIL["Spread"] = OIL["Brent"] - OIL["WTI"]
OIL["YoY"] = OIL["Brent"].pct_change(12) * 100      # worked out on the full history, then trimmed
OIL["vsPrewar"] = (OIL["Brent"] / PREWAR_PRICE - 1) * 100
OIL = OIL[(OIL["Date"] >= START) & (OIL["Date"] <= END)].reset_index(drop=True)
OIL["Month"], OIL["DateStr"] = OIL["Date"].dt.strftime("%Y-%m"), OIL["Date"].dt.strftime("%Y-%m-%d")

N, DATES = len(OIL), OIL["DateStr"].tolist()
PHASES = {name: dict(start=s, end=e, color=c, text=t) for name, (s, e, c, t) in EVENTS.items()}
VIEWS = ["$ per barrel", "% vs pre-war"]
SECOND = ["Monthly change", "3-month volatility", "Brent–WTI gap"]
KEEP = dict(marker=dict(opacity=1))   # stops Plotly fading the other points after a click

def shift(date_str, days):
    return (pd.Timestamp(date_str) + pd.Timedelta(days=days)).strftime("%Y-%m-%d")
def pct(old, new):
    return (new / old - 1) * 100
def signed(v):
    return f"{'+' if v > 0 else ''}{v:.1f}"
def month_label(d):
    return pd.Timestamp(d).strftime("%B %Y")
def nice_date(d):
    return f"{pd.Timestamp(d).day} {pd.Timestamp(d).strftime('%b %Y')}"

def layout(height, **kwargs):
    return dict(template="plotly_white", height=height, font=dict(size=12, color="#1f2933"),
                margin=dict(l=55, r=20, t=20, b=40), **kwargs)

# --------------------------------- charts ---------------------------------
def main_figure(phase, view, show_wti, sel):
    as_pct = view == VIEWS[1]
    tf = (lambda v: pct(PREWAR_PRICE, np.array(v, dtype=float))) if as_pct else (lambda v: v)
    fmt = "%{y:+.1f}%" if as_pct else "$%{y:.2f}"
    fig = go.Figure(go.Scatter(
        x=DATES, y=tf(OIL["Brent"]), name="Brent", mode="lines+markers",
        line=dict(color=COLORS["navy"], width=3), selected=KEEP, unselected=KEEP,
        marker=dict(size=[13 if i == sel else 7 for i in range(N)], line=dict(color="#fff", width=1.5),
                    color=[COLORS["orange"] if i == sel else COLORS["navy"] for i in range(N)]),
        hovertemplate=f"Brent: {fmt}<extra></extra>"))
    if LATEST_DATE > DATES[-1]:   # dotted line out to the latest daily price
        fig.add_scatter(x=[DATES[-1], LATEST_DATE], y=tf([OIL["Brent"].iloc[-1], LATEST_PRICE]),
                        mode="lines+markers", showlegend=False, selected=KEEP, unselected=KEEP,
                        line=dict(color=COLORS["navy"], width=2, dash="dot"),
                        marker=dict(size=[0, 9], symbol="diamond", color=COLORS["orange"]),
                        hovertemplate=f"{nice_date(LATEST_DATE)} spot: {fmt}<extra></extra>")
    if show_wti:
        fig.add_scatter(x=DATES, y=tf(OIL["WTI"]), name="WTI", mode="lines+markers", marker=dict(size=5),
                        line=dict(color=COLORS["grey"], width=2), selected=KEEP, unselected=KEEP,
                        hovertemplate=f"WTI: {fmt}<extra></extra>")
    ref = 0 if as_pct else PREWAR_PRICE
    fig.add_hline(y=ref, line=dict(dash="dash", color="#9aa5b1", width=1),
                  annotation_text="Pre-war level" if as_pct else f"Pre-war ${PREWAR_PRICE:.2f}",
                  annotation_position="top left", annotation_font=dict(size=11, color=COLORS["muted"]))
    if phase in PHASES:
        p = PHASES[phase]
        fig.add_vrect(x0=p["start"], x1=p["end"], fillcolor=p["color"], opacity=0.15, layer="below",
                      line_width=0, annotation_text=f"<b>{phase}</b>", annotation_position="top",
                      annotation_font=dict(color=p["color"], size=12))
    zoom = [dict(count=3, label="3M", step="month", stepmode="backward"),
            dict(count=6, label="6M", step="month", stepmode="backward"), dict(step="all", label="All")]
    fig.update_layout(**layout(430, hovermode="x unified", showlegend=show_wti,
                               legend=dict(orientation="h", x=1, xanchor="right", y=1.12),
                               yaxis=dict(title="% vs pre-war" if as_pct else "$/bbl", gridcolor="#edf0f3",
                                          zeroline=False),
                               xaxis=dict(type="date", range=[shift(DATES[0], -17), shift(LATEST_DATE, 11)],
                                          rangeselector=dict(x=0, y=1.1, buttons=zoom, bgcolor="#f2f4f7",
                                                             activecolor="#d6dde6"))))
    fig.update_layout(margin_t=40)
    return fig

def second_figure(mode, sel):
    def colour(i, normal):
        return COLORS["orange"] if i == sel else normal
    if mode == SECOND[1]:
        title, sub = ("Rolling 3-month volatility", "Annualised standard deviation of monthly % changes. "
                      "Higher means a more erratic market.")
        trace = go.Scatter(y=OIL["Volatility"], mode="lines+markers", fill="tozeroy",
                           fillcolor="rgba(142,68,173,.12)",
                           line=dict(color=COLORS["purple"], width=2.5, shape="spline"),
                           marker=dict(size=[11 if i == sel else 6 for i in range(N)],
                                       color=[colour(i, COLORS["purple"]) for i in range(N)]),
                           hovertemplate="%{x|%b %Y}: %{y:.1f}<extra></extra>")
        yaxis = {}
    elif mode == SECOND[2]:
        title, sub = ("Brent–WTI price gap", "$ per barrel. The gap widens when Middle East supply is cut "
                      "and the US is relatively insulated.")
        trace = go.Bar(y=OIL["Spread"], marker_color=[colour(i, COLORS["blue"]) for i in range(N)],
                       text=["" if pd.isna(v) else f"${v:.1f}" for v in OIL["Spread"]],
                       hovertemplate="%{x|%b %Y}: $%{y:.2f}<extra></extra>")
        yaxis = dict(tickprefix="$")
    else:
        title, sub = "Month-on-month change", "% change in the monthly average. Red bars are rises and green are falls."
        mom = OIL["MoM"]
        trace = go.Bar(y=mom, marker_color=["#ccc" if pd.isna(v) else colour(i, COLORS["red"] if v > 0
                                            else COLORS["green"]) for i, v in enumerate(mom)],
                       text=["" if pd.isna(v) else f"{signed(v)}%" for v in mom],
                       hovertemplate="%{x|%b %Y}: %{y:+.1f}%<extra></extra>")
        yaxis = dict(ticksuffix="%", zeroline=True, zerolinecolor="#9aa5b1")
    fig = go.Figure(trace.update(x=DATES, selected=KEEP, unselected=KEEP))
    fig.update_traces(textposition="outside", cliponaxis=False, selector=dict(type="bar"))
    fig.update_layout(**layout(330, showlegend=False, yaxis=dict(gridcolor="#edf0f3", **yaxis),
                               xaxis=dict(type="date", tickformat="%b %y",
                                          range=[shift(DATES[0], -17), shift(DATES[-1], 19)])))
    return fig, title, sub

# ------------------------------ page pieces -------------------------------
def kpi_html(title, value, desc, color):
    return (f'<div style="background:#fff;border-radius:6px;padding:14px 16px;border-top:4px solid {color};'
            f'box-shadow:0 1px 3px rgba(16,24,40,.12)"><div style="font-size:12px;color:{COLORS["muted"]};'
            f'text-transform:uppercase;letter-spacing:.5px">{title}</div><div style="font-size:27px;'
            f'font-weight:700;color:{COLORS["navy"]};margin:6px 0 2px">{value}</div>'
            f'<div style="font-size:12px;color:{COLORS["muted"]}">{desc}</div></div>')

def detail_html(sel):
    row = OIL.iloc[sel]
    def coloured(v):
        return "n/a" if pd.isna(v) else f'<span style="color:{"#c0392b" if v > 0 else "#1e8449"}">{signed(v)}%</span>'
    rows = [("Brent average", f"${row['Brent']:.2f}"),
            ("WTI average", "n/a" if pd.isna(row["WTI"]) else f"${row['WTI']:.2f}"),
            ("vs previous month", coloured(row["MoM"])), ("vs same month last year", coloured(row["YoY"])),
            ("vs pre-war price", coloured(row["vsPrewar"]))]
    cell = "padding:7px 0;border-bottom:1px solid #eef0f3"
    table = "".join(f'<tr><td style="{cell}">{a}</td><td style="{cell};text-align:right;font-weight:700">{b}</td></tr>'
                    for a, b in rows)
    phase = next((n for n, p in PHASES.items() if p["start"][:8] + "01" <= row["DateStr"] <= p["end"]), None)
    heading = f'<b style="color:{PHASES[phase]["color"]}">{phase}.</b>' if phase else f"<b>{BEFORE_EVENTS_NOTE[0]}</b>"
    text = MONTH_NOTES.get(row["Month"], PHASES[phase]["text"] if phase else BEFORE_EVENTS_NOTE[1])
    return (f'<div style="font-size:16px;font-weight:700;color:{COLORS["navy"]}">Month in focus</div>'
            f'<div style="font-size:22px;font-weight:700;color:{COLORS["navy"]}">{month_label(row["Date"])}</div>'
            f'<table style="width:100%;border-collapse:collapse;margin:10px 0;font-size:14px">{table}</table>'
            f'<div style="background:#f7f9fb;border-left:3px solid {COLORS["orange"]};padding:10px 12px;'
            f'font-size:13px;line-height:1.5">{heading} {text}</div>')

def apply_click(key):
    """If a new point was clicked on a chart, select that month."""
    try:
        clicked = tuple(str(p["x"])[:7] + "-01" for p in st.session_state[key]["selection"]["points"])
    except (KeyError, TypeError):
        return
    if clicked and clicked != st.session_state.get(key + "_last") and clicked[0] in DATES:
        st.session_state["ho_sel"] = DATES.index(clicked[0])
    st.session_state[key + "_last"] = clicked

def show_chart(fig, key):
    st.plotly_chart(fig, use_container_width=True, key=key, on_select="rerun",
                    selection_mode="points", config={"displayModeBar": False})

def step_month(delta):
    st.session_state["ho_sel"] = max(0, min(N - 1, st.session_state["ho_sel"] + delta))

def subtitle(title, text):
    st.markdown(f"**{title}**  \n<span style='font-size:12.5px;color:{COLORS['muted']}'>{text}</span>",
                unsafe_allow_html=True)

# ---------------------------------- page ----------------------------------
def render():
    st.session_state["ho_sel"] = min(st.session_state.get("ho_sel", N - 1), N - 1)
    apply_click("ho_main_chart")
    apply_click("ho_second_chart")
    sel = st.session_state["ho_sel"]
    st.markdown(f'<div style="background:{COLORS["navy"]};color:#fff;padding:18px 24px;border-radius:8px;'
                f'display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;margin-bottom:14px">'
                f'<div><div style="font-size:22px;font-weight:700">{TITLE}</div><div style="color:#b8c4d3;'
                f'font-size:13px">{SUBTITLE}</div></div><span style="background:{COLORS["orange"]};font-weight:700;'
                f'font-size:12px;padding:6px 10px;border-radius:4px">BRENT · DATA TO {nice_date(END).upper()}</span>'
                f'</div>', unsafe_allow_html=True)
    peak, gap = OIL["Brent"].idxmax(), OIL.dropna(subset=["Spread"]).iloc[-1]
    kpis = [("Latest Brent price", f"${LATEST_PRICE:.2f}", f"Daily spot, {nice_date(LATEST_DATE)}", "blue"),
            ("Change since pre-war", f"{signed(pct(PREWAR_PRICE, LATEST_PRICE))}%",
             f"vs ${PREWAR_PRICE:.2f} on {nice_date(PREWAR_DATE)}", "red"),
            ("Highest monthly average", f"${OIL.loc[peak, 'Brent']:.2f}", month_label(OIL.loc[peak, "Date"]), "orange"),
            ("Brent–WTI gap", f"${gap['Spread']:.2f}", f"{month_label(gap['Date'])} average", "purple")]
    for col, (title, value, desc, colour) in zip(st.columns(4), kpis):
        col.markdown(kpi_html(title, value, desc, COLORS[colour]), unsafe_allow_html=True)
    st.write("")
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 1.4, 1.4])
        phase = c1.pills("Highlight a phase of the crisis", list(PHASES), key="ho_phase")
        view = c2.segmented_control("Price view", VIEWS, default=VIEWS[0], key="ho_view") or VIEWS[0]
        c3.write("")
        show_wti = c3.checkbox("Compare with WTI (US benchmark)", key="ho_wti")
    with st.container(border=True):
        subtitle("Brent crude, monthly average", "Click any month to see its details below. "
                 "Use the buttons on the chart to zoom to the last 3 or 6 months.")
        show_chart(main_figure(phase, view, show_wti, sel), "ho_main_chart")
    left, right = st.columns([2, 1])
    with left.container(border=True):
        mode = st.segmented_control("Second chart", SECOND, default=SECOND[0], key="ho_second") or SECOND[0]
        fig, title, sub = second_figure(mode, sel)
        subtitle(title, sub)
        show_chart(fig, "ho_second_chart")
    with right.container(border=True):
        st.markdown(detail_html(sel), unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        b1.button("◀ Previous", "ho_prev", on_click=step_month, args=(-1,), use_container_width=True, disabled=sel == 0)
        b2.button("Next ▶", "ho_next", on_click=step_month, args=(1,), use_container_width=True, disabled=sel == N - 1)
        st.caption("Or click a point on either chart.")
    st.caption(f"Data: {SOURCE} ({HOW}). The latest price is the daily spot price on {nice_date(LATEST_DATE)}, "
               f"and the pre-war reference is the {nice_date(PREWAR_DATE)} price (${PREWAR_PRICE:.2f}).".replace("$", "\\$"))   # escape $ so Streamlit doesn't treat it as maths

if __name__ == "__main__":   # only when run on its own; inside the group app this is already set
    try:
        st.set_page_config(page_title=TITLE, layout="wide")
    except Exception:
        pass

render()
