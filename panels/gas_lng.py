"""panels/gas_lng.py — Gas & LNG panel (Eabha Kelly). Run on its own: python3 -m streamlit run panels/gas_lng.py

Story: about a fifth of the world's LNG passes through Hormuz, almost all of it from Qatar.
This panel shows what closing the strait has done to European gas prices, LNG shipping
and Europe's winter storage.

Same layout as panels/oil.py: KPI cards, one main chart you can click, a second chart you
can switch, and a "Month in focus" card. Everything is linked: clicking a month, picking a phase
or changing the price view updates both charts and the Month in focus card.
render_card() is the small version for the home page.
Everything you're likely to change is in the EDIT HERE section. Widget keys start with "gas_".
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# =============================================================================
# EDIT HERE
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
                 "Markets start to price in the risk of war with Iran, but LNG still flows and gas prices stay low."),
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


def shade(fig, phase, faint=False):
    """Shade phases of the crisis on a chart.

    faint=True: every phase as a light band with its name on top (the background of the main chart).
    Otherwise: only the chosen phase, a little stronger, with its name.
    """
    for name, p in PHASES.items():
        chosen = name == phase
        if not (faint or chosen):
            continue
        fig.add_vrect(x0=p["start"], x1=p["end"], fillcolor=p["color"], opacity=0.18 if chosen else 0.06,
                      layer="below", line_width=0)
        if chosen or faint:
            mid = pd.Timestamp(p["start"]) + (pd.Timestamp(p["end"]) - pd.Timestamp(p["start"])) / 2
            fig.add_annotation(x=mid, yref="paper", y=1.0, yanchor="bottom", showarrow=False,
                               text=f"<b>{name}</b>" if chosen else name,
                               font=dict(color=p["color"], size=12 if chosen else 11))


def shade_months(fig, table, phase):
    """Shade a phase on a monthly chart, covering whole months so it lines up with the bars and points.

    Each month belongs to the phase its middle falls in (the same rule as the Month in focus card),
    e.g. Ceasefire = April to June and Conflict resumes = July to October.
    """
    if phase not in PHASES:
        return
    months = table.loc[table["phase"] == phase, "month"]
    if months.empty:
        return
    start = pd.Timestamp(months.iloc[0] + "-01")
    end = pd.Timestamp(months.iloc[-1] + "-01") + pd.offsets.MonthBegin(1)
    colour = PHASES[phase]["color"]
    fig.add_vrect(x0=start, x1=end, fillcolor=colour, opacity=0.15, layer="below", line_width=0,
                  annotation_text=f"<b>{phase}</b>", annotation_position="top",
                  annotation_font=dict(color=colour, size=12))


MONTH_AXIS = dict(type="date", dtick="M1", tickformat="%b %y", ticklabelmode="period")   # label in the middle of each month


def phase_colour(phase) -> str:
    """The colour of a phase (grey before the war), so every chart uses the same colours."""
    return PHASES[phase]["color"] if phase in PHASES else COLORS["grey"]


def cursor(fig, date):
    """A dotted line at the month in focus: the same marker on every chart over time."""
    fig.add_vline(x=date, line=dict(color=COLORS["navy"], dash="dot", width=1.5), layer="above")


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
    shade_months(fig, table, phase)
    fig.update_layout(**layout(430, hovermode="x unified", showlegend=show_us,
                               legend=dict(orientation="h", x=1, xanchor="right", y=1.1),
                               yaxis=dict(title="% vs pre-war" if as_pct else "$ per MMBtu", gridcolor="#edf0f3",
                                          zeroline=False, ticksuffix="%" if as_pct else ""),
                               xaxis=dict(**MONTH_AXIS,
                                          range=[table["date"].iloc[0] - pd.Timedelta(days=20),
                                                 table["date"].iloc[-1] + pd.Timedelta(days=20)])))
    fig.update_layout(margin_t=40)
    return fig


def bench_month(row: str) -> str | None:
    """'March 2026 avg' -> '2026-03' (the 2022 row has no 2026 month, so it gives None)."""
    if row.startswith("Before the war"):
        return PREWAR_MONTH
    for m in range(1, 13):
        name = pd.Timestamp(2026, m, 1)
        if row.startswith(f"{name:%B} 2026"):
            return f"{name:%Y-%m}"
    return None


def second_figure(mode, table, data, sel, phase, view):
    """Second chart: one of three views. Returns (figure, title, subtitle).

    Linked to the rest of the page: the month in focus is orange, the chosen phase is
    shaded, and "% vs pre-war" switches tankers and 2026 vs 2022 to % of their pre-war level.
    """
    month, as_pct = table.iloc[sel]["month"], view == VIEWS[1]
    if mode == SECOND[1]:                    # EU storage (already in %, so the price view doesn't change it)
        st_ = data["storage"]
        fig = go.Figure()
        # soft pastels for the comparisons; 2026 in navy with a light fill, its dots in the colour of each phase
        for name, colour, dash, width in [("5-year average", "#f2a48f", "dash", 2.5),
                                          ("2025 (same date)", "#8fbbe8", None, 2.5), ("2026", COLORS["navy"], None, 3.5)]:
            s = st_[st_["series"] == name].sort_values("date")
            is_2026 = name == "2026"
            fig.add_scatter(x=s["date"], y=s["pct_full"], name=name.replace(" (same date)", ""), mode="lines+markers",
                            line=dict(color=colour, dash=dash, width=width, shape="spline", smoothing=0.5),
                            fill="tozeroy" if is_2026 else None, fillcolor="rgba(27,42,65,0.07)",
                            marker=dict(size=10 if is_2026 else 6, line=dict(color="#fff", width=1.5),
                                        color=[PHASES[phase_for(d)]["color"] if phase_for(d) else COLORS["navy"]
                                               for d in s["date"]] if is_2026 else colour),
                            hovertemplate=f"{name.split(' (')[0]}: %{{y:.1f}}%<extra></extra>")
        fig.add_hline(y=90, line=dict(color=COLORS["teal"], dash="dot", width=1), annotation_text="EU target 90%",
                      annotation_font_color=COLORS["teal"], annotation_position="top left")
        shade(fig, phase)
        cursor(fig, table.iloc[sel]["date"])
        fig.update_layout(**layout(330, hovermode="x unified", legend=dict(orientation="h", y=1.12, x=0),
                                   yaxis=dict(title="% full", range=[0, 105], ticksuffix="%", gridcolor="#edf0f3"),
                                   xaxis=dict(type="date", range=["2026-03-20", "2026-11-20"], tickformat="%b")))
        now = storage_now(st_)
        return (fig, "EU gas storage: refilling fell short",
                f"On {now['date']:%d %b} storage was {now['pct']:.0f}% full, {abs(now['gap']):.0f} points below the "
                "5-year average. The dotted line is the month in focus.")

    if mode == SECOND[2]:                    # 2026 vs 2022
        b = data["benchmarks"]
        rows = list(b["period"])
        ttf, jkm = b["ttf_usd_per_mmbtu"], b["jkm_usd_per_mmbtu"]
        if as_pct:
            ttf, jkm = (ttf / ttf.iloc[0] - 1) * 100, (jkm / jkm.iloc[0] - 1) * 100
        fmt = "%{x:+.0f}%" if as_pct else "$%{x:.1f}"
        fig = go.Figure()
        for i, row in enumerate(rows):
            focus = bench_month(row) == month
            fig.add_scatter(x=[ttf[i], jkm[i]], y=[row, row], mode="lines", hoverinfo="skip", showlegend=False,
                            line=dict(color=phase_colour(table.iloc[sel]["phase"]) if focus else "#dfe3e8",
                                      width=9 if focus else 6))
        fig.add_scatter(x=ttf, y=rows, mode="markers", name="Europe (TTF)", selected=KEEP, unselected=KEEP,
                        marker=dict(size=15, color=COLORS["navy"]), hovertemplate=f"Europe: {fmt}<extra></extra>")
        fig.add_scatter(x=jkm, y=rows, mode="markers", name="Asia (JKM)", selected=KEEP, unselected=KEEP,
                        marker=dict(size=15, color=COLORS["purple"], symbol="diamond"),
                        hovertemplate=f"Asia: {fmt}<extra></extra>")
        fig.update_layout(**layout(330, legend=dict(orientation="h", y=1.12, x=0),
                                   xaxis=dict(title="% vs pre-war" if as_pct else "$ per MMBtu", gridcolor="#edf0f3",
                                              ticksuffix="%" if as_pct else "", zeroline=as_pct),
                                   yaxis=dict(autorange="reversed", automargin=True, fixedrange=True)))
        rise = (b["ttf_usd_per_mmbtu"].iloc[-2] / b["ttf_usd_per_mmbtu"].iloc[0] - 1) * 100
        return (fig, "How big is this shock? 2026 vs 2022",
                f"Europe's gas price is up {rise:.0f}% since before the war, but still about a third of the 2022 "
                "peak. Click a 2026 row to see that month. The coloured row is the month in focus.")

    # LNG tankers (default)
    tk = table.dropna(subset=["tankers"])
    y = tk["tanker_pct"] if as_pct else tk["tankers"]
    focus = [m == month for m in tk["month"]]
    fig = go.Figure(go.Bar(x=tk["date"], y=y,
                           marker=dict(color=[phase_colour(p) for p in tk["phase"]],
                                       opacity=[1 if f else 0.55 for f in focus],
                                       line=dict(color=COLORS["navy"], width=[2.5 if f else 0 for f in focus])),
                           text=[f"{v:.0f}%" if as_pct else f"{v:.0f}" for v in y],
                           textposition="outside", cliponaxis=False, selected=KEEP, unselected=KEEP,
                           customdata=np.stack([tk["tankers"], tk["tanker_pct"], tk["tanker_note"], tk["tracker"]], axis=1),
                           hovertemplate="<b>%{x|%b %Y}: %{customdata[0]} tankers</b> (%{customdata[1]:.0f}% of normal)"
                                         "<br>%{customdata[2]}<br><i>Counted by %{customdata[3]}</i><extra></extra>"))
    top = 100 if as_pct else tk.loc[tk["month"] == PREWAR_MONTH, "tankers"].iloc[0]
    fig.add_hline(y=top, line=dict(color=COLORS["teal"], dash="dash", width=1.5), annotation_text="Pre-war level",
                  annotation_font_color=COLORS["teal"], annotation_position="top right")
    shade_months(fig, table, phase)
    fig.update_layout(**layout(330, showlegend=False,
                               yaxis=dict(title="% of pre-war" if as_pct else "LNG tankers a month",
                                          gridcolor="#edf0f3", range=[0, top * 1.25], ticksuffix="%" if as_pct else ""),
                               xaxis=MONTH_AXIS))
    return (fig, "LNG tankers through Hormuz each month",
            "Bars are coloured by phase; the outlined bar is the month in focus. Counts from S&P Global and "
            "Kpler (hover a bar to see which). Click a bar to see that month.")


def phase_summary(table, data, phase) -> str:
    """One line on what happened during the chosen phase: price, tankers and storage, from the data."""
    p = PHASES[phase]
    rows = table[table["phase"] == phase]
    before = table[table["date"] < pd.Timestamp(p["start"])]
    start_price = before["ttf"].iloc[-1] if len(before) else rows["ttf"].iloc[0]
    change = (rows["ttf"].iloc[-1] / start_price - 1) * 100
    parts = [f"European gas {signed(change, 0)}% (&#36;{start_price:.2f} → &#36;{rows['ttf'].iloc[-1]:.2f})"]
    if rows["tankers"].notna().any():
        parts.append(f"LNG tankers {rows['tankers'].mean():.0f} a month on average "
                     f"({rows['tanker_pct'].mean():.0f}% of normal)")
    s26 = data["storage"][(data["storage"]["series"] == "2026")]
    inside = s26[(s26["date"] >= pd.Timestamp(p["start"])) & (s26["date"] <= pd.Timestamp(p["end"]))].sort_values("date")
    if len(inside) > 1:
        parts.append(f"EU storage {inside['pct_full'].iloc[0]:.0f}% → {inside['pct_full'].iloc[-1]:.0f}% full")
    dates = f"{pd.Timestamp(p['start']):%d %b} – {pd.Timestamp(p['end']):%d %b}"
    return (f'<div style="border-left:4px solid {p["color"]};background:#f7f9fb;padding:10px 14px;margin:2px 0 12px;'
            f'font-size:14px;line-height:1.5"><b style="color:{p["color"]}">{phase}</b> '
            f'<span style="color:{COLORS["muted"]}">({dates})</span>: ' + " · ".join(parts) + "</div>")


def card_figure(table):
    """Small chart for the home page card: the same filled line and phase colours as the main chart."""
    fig = go.Figure(go.Scatter(x=table["date"], y=table["ttf"], mode="lines+markers",
                               line=dict(color=COLORS["navy"], width=3, shape="spline", smoothing=0.6),
                               fill="tozeroy", fillcolor="rgba(27,42,65,0.07)",
                               marker=dict(size=8, color=[phase_colour(p) for p in table["phase"]],
                                           line=dict(color="#fff", width=1.5)),
                               hovertemplate="%{x|%b %Y}: $%{y:.2f}<extra></extra>"))
    for p in PHASES.values():
        fig.add_vrect(x0=p["start"], x1=p["end"], fillcolor=p["color"], opacity=0.06, layer="below", line_width=0)
    fig.update_layout(**layout(250, showlegend=False, yaxis=dict(title="$ per MMBtu", gridcolor="#f0f2f5"),
                               xaxis=dict(type="date", tickformat="%b", showgrid=False)))
    return fig


# ------------------------------ page pieces -------------------------------
def kpi_html(title, value, desc, color):
    """A KPI card, same style as panels/oil.py."""
    return (f'<div style="background:#fff;border-radius:6px;padding:14px 16px;border-top:4px solid {color};'
            f'box-shadow:0 1px 3px rgba(16,24,40,.12)"><div style="font-size:12px;color:{COLORS["muted"]};'
            f'text-transform:uppercase;letter-spacing:.5px">{title}</div><div style="font-size:27px;'
            f'font-weight:700;color:{COLORS["navy"]};margin:6px 0 2px">{value}</div>'
            f'<div style="font-size:12px;color:{COLORS["muted"]}">{desc}</div></div>')


def donut(value, total, colour, middle, below):
    """A small donut: how full something is (e.g. tankers as % of normal), in the phase colour."""
    empty = pd.isna(value)
    share = 0 if empty else max(0, min(value / total, 1))
    fig = go.Figure(go.Pie(values=[share, 1 - share] if not empty else [1], hole=0.72, sort=False,
                           direction="clockwise", textinfo="none", hoverinfo="skip",
                           marker=dict(colors=[colour, "#eef0f3"] if not empty else ["#eef0f3"])))
    fig.add_annotation(text=f"<b>{'n/a' if empty else middle}</b>", x=0.5, y=0.5, showarrow=False,
                       font=dict(size=20, color=COLORS["navy"]))
    fig.update_layout(height=150, margin=dict(l=5, r=5, t=5, b=5), showlegend=False,
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig, below


def focus_header_html(row):
    """Top of the Month in focus card: the month and its phase, in the phase colour."""
    colour = phase_colour(row["phase"])
    return (f'<div style="font-size:13px;color:{COLORS["muted"]};text-transform:uppercase;letter-spacing:.5px">'
            f'Month in focus</div><div style="font-size:24px;font-weight:700;color:{COLORS["navy"]}">'
            f'{row["date"]:%B %Y}</div><span style="display:inline-block;background:{colour}1f;color:{colour};'
            f'font-weight:700;font-size:12px;padding:2px 10px;border-radius:999px;margin-top:4px">'
            f'{row["phase"] or "Before the war"}</span>')


def focus_table_html(row):
    """Bottom of the Month in focus card: the price numbers and what happened."""
    def coloured(v):
        return "n/a" if pd.isna(v) else f'<span style="color:{"#c0392b" if v > 0 else "#1e8449"}">{signed(v)}%</span>'
    rows = [("European gas (TTF)", f"&#36;{row['ttf']:.2f}"),
            ("vs before the war", coloured(row["vs_prewar"])),
            ("Europe pays", "n/a" if pd.isna(row["ratio"]) else f"{row['ratio']:.1f}× the US")]
    cell = "padding:7px 0;border-bottom:1px solid #eef0f3"
    table = "".join(f'<tr><td style="{cell}">{a}</td><td style="{cell};text-align:right;font-weight:700">{b}</td></tr>'
                    for a, b in rows)
    return (f'<table style="width:100%;border-collapse:collapse;margin:0 0 10px;font-size:14px">{table}</table>'
            f'<div style="background:#f7f9fb;border-left:3px solid {phase_colour(row["phase"])};padding:10px 12px;'
            f'font-size:13px;line-height:1.5">{MONTH_NOTES.get(row["month"], "")}</div>')


def apply_click(key, months):
    """If a new point was clicked on a chart, make its month the month in focus.

    Most charts have the month on the x axis; on the 2026 vs 2022 chart the month is in the row name.
    """
    try:
        points = st.session_state[key]["selection"]["points"]
    except (KeyError, TypeError):
        return
    clicked = tuple(bench_month(p["y"]) if isinstance(p.get("y"), str) else str(p.get("x"))[:7] for p in points)
    if clicked and clicked != st.session_state.get(key + "_last") and clicked[0] in months:
        st.session_state["gas_sel"] = months.index(clicked[0])
    st.session_state[key + "_last"] = clicked


def jump_to_phase(table):
    """Phase button action: move the month in focus to the first month of the chosen phase."""
    phase = st.session_state.get("gas_phase")
    first = table.index[table["phase"] == phase]
    if len(first):
        st.session_state["gas_sel"] = int(first[0])


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
        phase = c1.pills("Highlight a phase of the crisis", list(PHASES), key="gas_phase",
                         on_change=jump_to_phase, args=(table,))
        view = c2.segmented_control("Price view", VIEWS, default=VIEWS[0], key="gas_view") or VIEWS[0]
        c3.write("")
        show_us = c3.checkbox("Compare with US gas (Henry Hub)", key="gas_us")
    if phase in PHASES:
        st.markdown(phase_summary(table, data, phase), unsafe_allow_html=True)
    with st.container(border=True):
        subtitle("European gas, monthly average", "Click any month: the second chart and Month in focus follow it. "
                 "The phase buttons and price view change both charts.")
        show_chart(main_figure(table, phase, view, show_us, sel), "gas_main_chart")

    left, right = st.columns([2, 1])
    with left.container(border=True):
        mode = st.segmented_control("Second chart", SECOND, default=SECOND[0], key="gas_second") or SECOND[0]
        fig, title, sub = second_figure(mode, table, data, sel, phase, view)
        subtitle(title, sub)
        show_chart(fig, "gas_second_chart")
    with right.container(border=True):
        row = table.iloc[sel]
        st.markdown(focus_header_html(row), unsafe_allow_html=True)
        colour = phase_colour(row["phase"])
        donuts = [donut(row["tanker_pct"], 100, colour, f"{row['tanker_pct']:.0f}%", "LNG traffic vs normal"),
                  donut(row["storage"], 100, colour, f"{row['storage']:.0f}%", "EU storage full")]
        for col, (fig, label), key in zip(st.columns(2), donuts, ["gas_donut_tankers", "gas_donut_storage"]):
            col.plotly_chart(fig, key=key, config={"displayModeBar": False, "staticPlot": True})
            col.markdown(f"<div style='text-align:center;font-size:12.5px;color:{COLORS['muted']};margin-top:-10px'>"
                         f"{label}</div>", unsafe_allow_html=True)
        st.markdown(focus_table_html(row), unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        b1.button("◀ Previous", "gas_prev", on_click=step_month, args=(-1, n), disabled=sel == 0)
        b2.button("Next ▶", "gas_next", on_click=step_month, args=(1, n), disabled=sel == n - 1)
        st.caption("Or click a point on either chart.")

    st.success("**Takeaway:** Europe's gas price is up " + f"{last['vs_prewar']:.0f}% since before the war and LNG "
               f"traffic through Hormuz is only {tk['tanker_pct']:.0f}% of normal. Europe enters winter with storage "
               f"{abs(now['gap']):.0f} points below normal, so a cold snap could push prices higher still.")
    st.caption(f"Data: {SOURCE}. Daily prices: {how}. Prices to {END:%d %B %Y}; EU storage to "
               f"{now['date']:%d %B %Y}. Sources are listed row by row in data/gas_*.csv.".replace("$", "\\$"))


if __name__ == "__main__":   # only when run on its own; inside the group app this is already set
    try:
        st.set_page_config(page_title=TITLE, layout="wide")
    except Exception:
        pass
    render()
