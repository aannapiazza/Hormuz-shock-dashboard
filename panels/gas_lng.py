"""panels/gas_lng.py — Gas & LNG panel (Eabha Kelly). Run on its own: python3 -m streamlit run panels/gas_lng.py

Story: about a fifth of the world's LNG passes through Hormuz, almost all of it from Qatar.
This panel shows what closing the strait has done to European gas prices, LNG shipping
and Europe's winter storage.

Same layout as panels/oil.py: KPI cards, one main chart you can click, a second chart you
can switch, and a "Month in focus" card. render_card() is the small version for the home page.
Everything you're likely to change is in the EDIT HERE section. Widget keys start with "gas_".
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# =============================================================================
# ✏️  EDIT HERE
# =============================================================================
END = pd.Timestamp("2026-10-31")     # cut-off: no price after this date is used (same as the other panels)
LIVE = False                         # False = use the saved copies in data/ (default)
                                     # True  = download fresh daily prices from Yahoo Finance, save them to data/
# Data files in data/. Each file has source and url columns, so every number can be traced.
FILES = {
    "prices": "gas_prices_monthly.csv",   # World Bank Pink Sheet: European gas (Dutch TTF), monthly average, $/MMBtu
    "daily": "gas_prices_daily.csv",      # Yahoo Finance: TTF=F (€/MWh), NG=F (US Henry Hub, $/MMBtu), EURUSD=X
    "tankers": "gas_tankers.csv",         # LNG tankers through Hormuz each month (S&P Global, Kpler)
    "storage": "gas_storage.csv",         # EU gas storage % full: 2026, 2025 and the 5-year average (GIE AGSI)
    "benchmarks": "gas_benchmarks.csv",   # Europe (TTF) vs Asia (JKM) before the war, in 2026 and at the 2022 peak
}
TICKERS = {"ttf_eur_mwh": "TTF=F", "hh_usd_mmbtu": "NG=F", "eurusd": "EURUSD=X"}
DAILY_START = "2025-10-01"           # first day downloaded when LIVE = True
PREWAR_MONTH = "2026-02"             # last full month before the 28 Feb strikes: the "before the war" reference
MWH_PER_MMBTU = 0.293071             # 1 MMBtu = 0.293071 MWh (to put European prices in $/MMBtu)

# Phases that shade the chart: same names, dates and colours as panels/oil.py.
EVENTS = {
    "Build-up": ("2026-01-01", "2026-02-28", "#e0a800",
                 "Prices drift up as markets price in the risk of war with Iran."),
    "War & closure": ("2026-02-28", "2026-04-08", "#d64545",
                      "The 28 Feb strikes shut Hormuz to LNG tankers, and on 19 Mar a strike on Ras Laffan "
                      "knocks out 16–17% of Qatar's export capacity for years."),
    "Ceasefire": ("2026-04-08", "2026-07-08", "#2e86de",
                  "Gas prices ease on the 8 Apr ceasefire. A few LNG cargoes start moving again in May and June."),
    "Conflict resumes": ("2026-07-08", "2026-10-31", "#8e44ad",
                         "Strikes resume on 8 Jul and LNG traffic stops again. Europe refills its storage too "
                         "slowly, and prices climb for four months."),
}
# One line per month for the "Month in focus" card (sources: the note column of the data files).
MONTH_NOTES = {
    "2026-01": "A cold start to the winter lifts prices, but LNG still flows normally.",
    "2026-02": "The last normal month: about 85 LNG tankers leave the Gulf through Hormuz.",
    "2026-03": "No LNG carrier crosses all month, and Ras Laffan is hit on 19 Mar.",
    "2026-04": "The ceasefire calms prices, but only 4 LNG carriers cross, with transponders off.",
    "2026-05": "The first Qatari cargo since the war sails for Pakistan on 9 May.",
    "2026-06": "The strait reopens for a few weeks: 40 LNG carriers cross.",
    "2026-07": "Strikes resume on 8 Jul. No LNG tanker crosses after 11 Jul.",
    "2026-08": "A Qatari LNG carrier is struck on 1 Aug. Only 3 tankers leave all month.",
    "2026-09": "Qatari tankers start sailing again, some with transponders off.",
    "2026-10": "The highest gas prices since December 2022. 31 tankers leave: still only a third of normal.",
}

TITLE = "Gas & LNG: Qatar's exports cut off"
SUBTITLE = "About a fifth of the world's LNG passes through Hormuz, almost all of it from Qatar"
SOURCE = ("World Bank Pink Sheet (monthly TTF), Yahoo Finance (daily TTF, Henry Hub, EUR/USD), S&P Global and "
          "Kpler (LNG tankers), GIE AGSI (EU storage), EIA and IEA (Asian LNG)")
COLORS = {"navy": "#1b2a41", "orange": "#f2711c", "muted": "#6b7785", "red": "#d64545", "green": "#27ae60",
          "blue": "#2e86de", "purple": "#8e44ad", "teal": "#0f9b8e", "amber": "#d48806", "grey": "#7f8c8d"}
# =============================================================================
# (You shouldn't need to change anything below this line.)
# =============================================================================

PHASES = {name: dict(start=s, end=e, color=c, text=t) for name, (s, e, c, t) in EVENTS.items()}
VIEWS = ["$ per MMBtu", "% vs pre-war"]
SECOND = ["LNG tankers", "EU storage", "2026 vs 2022"]
KEEP = dict(marker=dict(opacity=1))   # stops Plotly fading the other points after a click


# ---------------------------------- data ----------------------------------
def data_folder() -> Path:
    """The data/ folder next to panels/ (also works if the file is run from another folder)."""
    here = Path(__file__).resolve().parent
    for folder in (here.parent / "data", here / "data", Path.cwd() / "data"):
        if folder.is_dir():
            return folder
    return here.parent / "data"


def download_daily() -> pd.DataFrame:
    """Download daily closes from Yahoo Finance: one row per trading day, gaps filled with the day before."""
    import yfinance as yf   # imported here, so the panel still works without yfinance when LIVE = False
    raw = yf.download(list(TICKERS.values()), start=DAILY_START, auto_adjust=True, progress=False)["Close"]
    raw = raw.ffill().dropna()
    daily = pd.DataFrame({col: raw[ticker] for col, ticker in TICKERS.items()})
    daily.index = pd.to_datetime(daily.index).tz_localize(None)
    return daily.rename_axis("date").reset_index()


@st.cache_data
def load_data(live: bool = LIVE) -> tuple:
    """Read every CSV in FILES. Returns (dict of DataFrames, where the daily prices came from).

    LIVE: try a fresh download and save it to data/; if that fails, use the saved copy.
    Prices after END are dropped, so every panel stops on the same day.
    """
    folder = data_folder()
    data = {key: pd.read_csv(folder / name) for key, name in FILES.items()}
    how = "saved copy in data/"
    if live:
        try:
            data["daily"] = download_daily()
            data["daily"].to_csv(folder / FILES["daily"], index=False)
            how = "downloaded from Yahoo Finance"
        except Exception:
            pass   # no internet or read-only folder: keep the saved copy
    data["daily"]["date"] = pd.to_datetime(data["daily"]["date"])
    data["daily"] = data["daily"][data["daily"]["date"] <= END].reset_index(drop=True)
    data["storage"]["date"] = pd.to_datetime(data["storage"]["date"])
    data["prices"] = data["prices"][pd.to_datetime(data["prices"]["month"]) <= END]
    return data, how


def ttf_in_usd(daily: pd.DataFrame) -> pd.Series:
    """European gas from €/MWh to $/MMBtu, using each day's exchange rate, so it compares with US gas."""
    return daily["ttf_eur_mwh"] * daily["eurusd"] * MWH_PER_MMBTU


def monthly_table(data: dict) -> pd.DataFrame:
    """One row per month with everything the cards and charts need.

    Joins the World Bank monthly TTF price with the monthly average of US gas (from the
    daily file), the tanker count and end-of-month EU storage, then works out the changes.
    """
    t = data["prices"][["month", "ttf_usd_per_mmbtu"]].rename(columns={"ttf_usd_per_mmbtu": "ttf"})
    t["date"] = pd.to_datetime(t["month"]) + pd.Timedelta(days=14)          # mid-month, for plotting
    prewar = t.loc[t["month"] == PREWAR_MONTH, "ttf"].iloc[0]
    t["vs_prev"] = t["ttf"].pct_change() * 100
    t["vs_prewar"] = (t["ttf"] / prewar - 1) * 100

    daily = data["daily"].assign(month=data["daily"]["date"].dt.strftime("%Y-%m"))
    t["hh"] = t["month"].map(daily.groupby("month")["hh_usd_mmbtu"].mean())
    t["ratio"] = t["ttf"] / t["hh"]                                          # how many times more Europe pays

    tankers = data["tankers"].set_index("month")
    t["tankers"] = t["month"].map(tankers["tankers"])
    t["tracker"] = t["month"].map(tankers["tracker"])
    t["tanker_note"] = t["month"].map(tankers["note"])
    t["tanker_pct"] = t["tankers"] / tankers.loc[PREWAR_MONTH, "tankers"] * 100

    s26 = data["storage"][data["storage"]["series"] == "2026"].sort_values("date")
    month_ends = pd.to_datetime(t["month"]) + pd.offsets.MonthEnd(0)
    t["storage"] = [s26.loc[s26["date"] <= d, "pct_full"].iloc[-1] if (s26["date"] <= d).any() else np.nan
                    for d in month_ends]
    t["phase"] = [phase_for(d) for d in t["date"]]
    return t.reset_index(drop=True)


def phase_for(date) -> str | None:
    """Which phase of the crisis a date falls in (None before the build-up)."""
    for name, p in PHASES.items():
        if pd.Timestamp(p["start"]) <= date <= pd.Timestamp(p["end"]):
            return name
    return None


def storage_now(storage: pd.DataFrame) -> dict:
    """Latest EU storage reading, and how far it is from the 5-year average on that date."""
    s26 = storage[storage["series"] == "2026"].sort_values("date").iloc[-1]
    avg = storage[(storage["series"] == "5-year average") & (storage["date"] == s26["date"])]["pct_full"]
    return {"date": s26["date"], "pct": s26["pct_full"], "gap": s26["pct_full"] - avg.iloc[0] if len(avg) else np.nan}


# --------------------------------- helpers ---------------------------------
def signed(v, decimals=1):
    return f"{'+' if v > 0 else ''}{v:.{decimals}f}"


def layout(height, **kwargs):
    """The look shared by every chart (same as panels/oil.py)."""
    return dict(template="plotly_white", height=height, font=dict(size=12, color="#1f2933"),
                margin=dict(l=55, r=20, t=20, b=40), **kwargs)


def shade(fig, phase):
    """Shade one phase of the crisis on a chart, with its name on top."""
    if phase in PHASES:
        p = PHASES[phase]
        fig.add_vrect(x0=p["start"], x1=p["end"], fillcolor=p["color"], opacity=0.15, layer="below", line_width=0,
                      annotation_text=f"<b>{phase}</b>", annotation_position="top",
                      annotation_font=dict(color=p["color"], size=12))


# --------------------------------- charts ---------------------------------
def main_figure(table, phase, view, show_us, sel):
    """Main chart: European gas, monthly average, with price labels and optional US gas."""
    as_pct = view == VIEWS[1]
    def tf(values, ref):
        values = np.asarray(values, dtype=float)
        return (values / ref - 1) * 100 if as_pct else values
    prewar = table.loc[table["month"] == PREWAR_MONTH].iloc[0]
    fmt = "%{y:+.0f}%" if as_pct else "$%{y:.2f}"
    n, y = len(table), tf(table["ttf"], prewar["ttf"])
    fig = go.Figure(go.Scatter(
        x=table["date"], y=y, name="Europe (TTF)", mode="lines+markers+text",
        text=[f"{v:+.0f}%" if as_pct else f"${v:.1f}" for v in y], textposition="top center",
        textfont=dict(size=10.5, color="#475467"), line=dict(color=COLORS["navy"], width=3),
        marker=dict(size=[13 if i == sel else 7 for i in range(n)], line=dict(color="#fff", width=1.5),
                    color=[COLORS["orange"] if i == sel else COLORS["navy"] for i in range(n)]),
        selected=KEEP, unselected=KEEP, hovertemplate=f"Europe: {fmt}<extra></extra>"))
    if show_us:
        fig.add_scatter(x=table["date"], y=tf(table["hh"], prewar["hh"]), name="US gas (Henry Hub)",
                        mode="lines+markers", marker=dict(size=5), line=dict(color=COLORS["teal"], width=2),
                        selected=KEEP, unselected=KEEP, hovertemplate=f"US: {fmt}<extra></extra>")
    ref = 0 if as_pct else prewar["ttf"]
    fig.add_hline(y=ref, line=dict(dash="dash", color="#9aa5b1", width=1),
                  annotation_text="Pre-war level" if as_pct else f"Pre-war (Feb avg) ${prewar['ttf']:.2f}",
                  annotation_position="bottom right", annotation_font=dict(size=11, color=COLORS["muted"]))
    shade(fig, phase)
    fig.update_layout(**layout(430, hovermode="x unified", showlegend=show_us,
                               legend=dict(orientation="h", x=1, xanchor="right", y=1.1),
                               yaxis=dict(title="% vs pre-war" if as_pct else "$ per MMBtu", gridcolor="#edf0f3",
                                          zeroline=False, ticksuffix="%" if as_pct else ""),
                               xaxis=dict(type="date", tickformat="%b %y",
                                          range=[table["date"].iloc[0] - pd.Timedelta(days=20),
                                                 table["date"].iloc[-1] + pd.Timedelta(days=20)])))
    fig.update_layout(margin_t=40)
    return fig


def second_figure(mode, table, data, sel):
    """Second chart: one of three views. Returns (figure, title, subtitle)."""
    month = table.iloc[sel]["month"]
    if mode == SECOND[1]:                    # EU storage
        st_ = data["storage"]
        fig = go.Figure()
        for name, colour, dash, width in [("5-year average", COLORS["muted"], "dash", 2),
                                          ("2025 (same date)", COLORS["amber"], None, 2), ("2026", COLORS["red"], None, 3.5)]:
            s = st_[st_["series"] == name].sort_values("date")
            fig.add_scatter(x=s["date"], y=s["pct_full"], name=name.replace(" (same date)", ""), mode="lines+markers",
                            line=dict(color=colour, dash=dash, width=width),
                            hovertemplate=f"{name.split(' (')[0]}: %{{y:.1f}}%<extra></extra>")
        fig.add_hline(y=90, line=dict(color=COLORS["teal"], dash="dot", width=1), annotation_text="EU target 90%",
                      annotation_font_color=COLORS["teal"], annotation_position="top left")
        start = pd.Timestamp(month + "-01")
        fig.add_vrect(x0=start, x1=start + pd.offsets.MonthEnd(0), fillcolor=COLORS["orange"], opacity=0.12,
                      layer="below", line_width=0)
        fig.update_layout(**layout(330, hovermode="x unified", legend=dict(orientation="h", y=1.12, x=0),
                                   yaxis=dict(title="% full", range=[0, 100], ticksuffix="%", gridcolor="#edf0f3"),
                                   xaxis=dict(type="date", range=["2026-03-20", "2026-11-20"], tickformat="%b")))
        now = storage_now(st_)
        return (fig, "EU gas storage: refilling fell short",
                f"On {now['date']:%d %b} storage was {now['pct']:.0f}% full, {abs(now['gap']):.0f} points below the "
                "5-year average. The orange band is the month in focus.")

    if mode == SECOND[2]:                    # 2026 vs 2022
        b = data["benchmarks"]
        rows = list(b["period"])
        fig = go.Figure()
        for i, row in enumerate(rows):
            focus = row.startswith(pd.Timestamp(month + "-01").strftime("%B")) or (month == PREWAR_MONTH and i == 0)
            fig.add_scatter(x=[b["ttf_usd_per_mmbtu"][i], b["jkm_usd_per_mmbtu"][i]], y=[row, row], mode="lines",
                            hoverinfo="skip", showlegend=False,
                            line=dict(color=COLORS["orange"] if focus else "#c4cad4", width=8 if focus else 6))
        fig.add_scatter(x=b["ttf_usd_per_mmbtu"], y=rows, mode="markers", name="Europe (TTF)",
                        marker=dict(size=15, color=COLORS["navy"]), hovertemplate="Europe: $%{x:.1f}<extra></extra>")
        fig.add_scatter(x=b["jkm_usd_per_mmbtu"], y=rows, mode="markers", name="Asia (JKM)",
                        marker=dict(size=15, color=COLORS["purple"], symbol="diamond"),
                        hovertemplate="Asia: $%{x:.1f}<extra></extra>")
        fig.update_layout(**layout(330, legend=dict(orientation="h", y=1.12, x=0),
                                   xaxis=dict(title="$ per MMBtu", gridcolor="#edf0f3", rangemode="tozero"),
                                   yaxis=dict(autorange="reversed", automargin=True, fixedrange=True)))
        rise = (b["ttf_usd_per_mmbtu"].iloc[-2] / b["ttf_usd_per_mmbtu"].iloc[0] - 1) * 100
        return (fig, "How big is this shock? 2026 vs 2022",
                f"Europe's gas price is up {rise:.0f}% since before the war, but still about a third of the 2022 "
                "peak. Europe and Asia now pay about the same.")

    # LNG tankers (default)
    tk = table.dropna(subset=["tankers"])
    colours = [COLORS["orange"] if m == month else COLORS["muted"] if m == PREWAR_MONTH
               else COLORS["amber"] if tr == "Kpler" else COLORS["red"] for m, tr in zip(tk["month"], tk["tracker"])]
    fig = go.Figure(go.Bar(x=tk["date"], y=tk["tankers"], marker_color=colours, text=tk["tankers"].astype(int),
                           textposition="outside", cliponaxis=False, selected=KEEP, unselected=KEEP,
                           customdata=np.stack([tk["tanker_pct"], tk["tanker_note"]], axis=1),
                           hovertemplate="<b>%{x|%b %Y}: %{y} tankers</b> (%{customdata[0]:.0f}% of normal)"
                                         "<br>%{customdata[1]}<extra></extra>"))
    prewar = tk.loc[tk["month"] == PREWAR_MONTH, "tankers"].iloc[0]
    fig.add_hline(y=prewar, line=dict(color=COLORS["teal"], dash="dash", width=1.5), annotation_text="Pre-war level",
                  annotation_font_color=COLORS["teal"], annotation_position="top right")
    fig.update_layout(**layout(330, showlegend=False, yaxis=dict(title="LNG tankers a month", gridcolor="#edf0f3",
                                                                 range=[0, prewar * 1.2]),
                               xaxis=dict(type="date", tickformat="%b %y")))
    return (fig, "LNG tankers through Hormuz each month",
            "Red: S&P Global (laden tankers leaving). Amber: Kpler (all LNG-carrier crossings). "
            "Click a bar to see that month.")


def card_figure(table):
    """Small chart for the home page card: the monthly price with every phase shaded."""
    fig = go.Figure(go.Scatter(x=table["date"], y=table["ttf"], mode="lines+markers",
                               line=dict(color=COLORS["navy"], width=3), marker=dict(size=6),
                               hovertemplate="%{x|%b %Y}: $%{y:.2f}<extra></extra>"))
    for p in PHASES.values():
        fig.add_vrect(x0=p["start"], x1=p["end"], fillcolor=p["color"], opacity=0.12, layer="below", line_width=0)
    fig.update_layout(**layout(260, showlegend=False, yaxis=dict(title="$ per MMBtu", gridcolor="#edf0f3"),
                               xaxis=dict(type="date", tickformat="%b")))
    return fig


# ------------------------------ page pieces -------------------------------
def kpi_html(title, value, desc, color):
    """A KPI card, same style as panels/oil.py."""
    return (f'<div style="background:#fff;border-radius:6px;padding:14px 16px;border-top:4px solid {color};'
            f'box-shadow:0 1px 3px rgba(16,24,40,.12)"><div style="font-size:12px;color:{COLORS["muted"]};'
            f'text-transform:uppercase;letter-spacing:.5px">{title}</div><div style="font-size:27px;'
            f'font-weight:700;color:{COLORS["navy"]};margin:6px 0 2px">{value}</div>'
            f'<div style="font-size:12px;color:{COLORS["muted"]}">{desc}</div></div>')


def detail_html(row):
    """The Month in focus card: the numbers for one month and what happened."""
    def coloured(v):
        return "n/a" if pd.isna(v) else f'<span style="color:{"#c0392b" if v > 0 else "#1e8449"}">{signed(v)}%</span>'
    rows = [("European gas (TTF)", f"&#36;{row['ttf']:.2f}"),
            ("vs before the war", coloured(row["vs_prewar"])),
            ("Europe pays", "n/a" if pd.isna(row["ratio"]) else f"{row['ratio']:.1f}× the US"),
            ("LNG tankers via Hormuz", "n/a" if pd.isna(row["tankers"])
             else f"{row['tankers']:.0f} ({row['tanker_pct']:.0f}% of normal)"),
            ("EU storage", "n/a" if pd.isna(row["storage"]) else f"{row['storage']:.0f}% full")]
    cell = "padding:7px 0;border-bottom:1px solid #eef0f3"
    table = "".join(f'<tr><td style="{cell}">{a}</td><td style="{cell};text-align:right;font-weight:700">{b}</td></tr>'
                    for a, b in rows)
    phase = row["phase"]
    heading = f'<b style="color:{PHASES[phase]["color"]}">{phase}.</b>' if phase else "<b>Before the war.</b>"
    return (f'<div style="font-size:16px;font-weight:700;color:{COLORS["navy"]}">Month in focus</div>'
            f'<div style="font-size:22px;font-weight:700;color:{COLORS["navy"]}">{row["date"]:%B %Y}</div>'
            f'<table style="width:100%;border-collapse:collapse;margin:10px 0;font-size:14px">{table}</table>'
            f'<div style="background:#f7f9fb;border-left:3px solid {COLORS["orange"]};padding:10px 12px;'
            f'font-size:13px;line-height:1.5">{heading} {MONTH_NOTES.get(row["month"], "")}</div>')


def apply_click(key, months):
    """If a new point was clicked on a chart, make its month the month in focus."""
    try:
        clicked = tuple(str(p["x"])[:7] for p in st.session_state[key]["selection"]["points"])
    except (KeyError, TypeError):
        return
    if clicked and clicked != st.session_state.get(key + "_last") and clicked[0] in months:
        st.session_state["gas_sel"] = months.index(clicked[0])
    st.session_state[key + "_last"] = clicked


def show_chart(fig, key):
    st.plotly_chart(fig, key=key, on_select="rerun", selection_mode="points", config={"displayModeBar": False})


def step_month(delta, n):
    st.session_state["gas_sel"] = max(0, min(n - 1, st.session_state["gas_sel"] + delta))


def subtitle(title, text):
    st.markdown(f"**{title}**  \n<span style='font-size:12.5px;color:{COLORS['muted']}'>{text}</span>"
                .replace("$", "&#36;"), unsafe_allow_html=True)


# ---------------------------------- page ----------------------------------
def render_card():
    """The small version for the home page: two numbers and one chart."""
    data, _ = load_data()
    table = monthly_table(data)
    last, tk = table.iloc[-1], table.dropna(subset=["tankers"]).iloc[-1]
    c1, c2 = st.columns(2)
    c1.metric(f"European gas, {last['date']:%b}", f"${last['ttf']:.2f}", f"{signed(last['vs_prewar'], 0)}% since pre-war",
              delta_color="inverse")
    c2.metric(f"LNG tankers via Hormuz, {tk['date']:%b}", f"{tk['tankers']:.0f}",
              f"{tk['tanker_pct'] - 100:.0f}% vs pre-war")
    st.plotly_chart(card_figure(table), key="gas_card_chart", config={"displayModeBar": False})


def render():
    """Draw the whole panel. app.py runs this file, which calls render() at the bottom."""
    data, how = load_data()
    table = monthly_table(data)
    months, n = table["month"].tolist(), len(table)
    st.session_state["gas_sel"] = min(st.session_state.get("gas_sel", n - 1), n - 1)
    apply_click("gas_main_chart", months)
    apply_click("gas_second_chart", months)
    sel = st.session_state["gas_sel"]

    st.markdown(f'<div style="background:{COLORS["navy"]};color:#fff;padding:18px 24px;border-radius:8px;'
                f'display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;margin-bottom:14px">'
                f'<div><div style="font-size:22px;font-weight:700">{TITLE}</div><div style="color:#b8c4d3;'
                f'font-size:13px">{SUBTITLE}</div></div><span style="background:{COLORS["orange"]};font-weight:700;'
                f'font-size:12px;padding:6px 10px;border-radius:4px">TTF · DATA TO {f"{END:%d %b %Y}".upper()}</span>'
                f'</div>', unsafe_allow_html=True)

    last, tk, now = table.iloc[-1], table.dropna(subset=["tankers"]).iloc[-1], storage_now(data["storage"])
    kpis = [("European gas (TTF)", f"&#36;{last['ttf']:.2f}", f"{signed(last['vs_prewar'], 0)}% since before the war",
             "blue"),
            ("Europe pays vs the US", f"{last['ratio']:.1f}×", f"{last['date']:%B} averages", "red"),
            (f"LNG tankers via Hormuz, {tk['date']:%b}", f"{tk['tankers']:.0f}", f"{tk['tanker_pct']:.0f}% of normal",
             "orange"),
            (f"EU gas storage, {now['date']:%d %b}", f"{now['pct']:.1f}%", f"{signed(now['gap'], 0)} pts vs normal",
             "purple")]
    for col, (title, value, desc, colour) in zip(st.columns(4), kpis):
        col.markdown(kpi_html(title, value, desc, COLORS[colour]), unsafe_allow_html=True)
    st.write("")

    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 1.4, 1.4])
        phase = c1.pills("Highlight a phase of the crisis", list(PHASES), key="gas_phase")
        view = c2.segmented_control("Price view", VIEWS, default=VIEWS[0], key="gas_view") or VIEWS[0]
        c3.write("")
        show_us = c3.checkbox("Compare with US gas (Henry Hub)", key="gas_us")
    with st.container(border=True):
        subtitle("European gas, monthly average", "Click any month to see its details below.")
        show_chart(main_figure(table, phase, view, show_us, sel), "gas_main_chart")

    left, right = st.columns([2, 1])
    with left.container(border=True):
        mode = st.segmented_control("Second chart", SECOND, default=SECOND[0], key="gas_second") or SECOND[0]
        fig, title, sub = second_figure(mode, table, data, sel)
        subtitle(title, sub)
        show_chart(fig, "gas_second_chart")
    with right.container(border=True):
        st.markdown(detail_html(table.iloc[sel]), unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        b1.button("◀ Previous", "gas_prev", on_click=step_month, args=(-1, n), disabled=sel == 0)
        b2.button("Next ▶", "gas_next", on_click=step_month, args=(1, n), disabled=sel == n - 1)
        st.caption("Or click a point on either chart.")

    st.caption(f"Data: {SOURCE}. Daily prices: {how}. Prices to {END:%d %B %Y}; EU storage to "
               f"{now['date']:%d %B %Y}. Sources are listed row by row in data/gas_*.csv.".replace("$", "\\$"))


if __name__ == "__main__":   # only when run on its own; inside the group app this is already set
    try:
        st.set_page_config(page_title=TITLE, layout="wide")
    except Exception:
        pass
    render()
