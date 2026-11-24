"""
Inflation and households - panel 4 of the Hormuz Shock dashboard
Author: Eleena Golchin

How far has the Hormuz oil shock pushed up consumer prices, and what would a
new oil price mean for a household's energy bill? One time slider controls
the whole panel: the chart, the three numbers and the bill calculator.

Run on its own:   python3 -m streamlit run panels/inflation.py
The data downloads are in panels/inflation_data.py.
"""

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:                                        # when app.py runs this file from the repo folder
    from panels.inflation_data import END, START, MEASURES, all_countries, load_data
except ModuleNotFoundError:                 # when it is run on its own from inside panels/
    from inflation_data import END, START, MEASURES, all_countries, load_data

# =============================================================================
# 1. SETTINGS (the data sources are in inflation_data.py)
# =============================================================================

# Story dates (the same events as the other three panels)
WAR_START = pd.Timestamp("2026-02-28")    # US-Israel strikes on Iran
TARGET = 2.0                              # central banks' inflation target, %
PHASES = [   # the same phases, dates and colours as the oil and gas panels: (name, start, end, colour)
    ("Build-up", "2026-01-01", "2026-02-28", "#e0a800"),
    ("War & closure", "2026-02-28", "2026-04-08", "#d64545"),
    ("Ceasefire", "2026-04-08", "2026-07-08", "#2e86de"),
    ("Conflict resumes", "2026-07-08", "2026-10-31", "#8e44ad"),
]

# The time slider at the top of the panel links both sections: Section 1 shows
# only these months, and Section 2 starts its scenario from the last of them.
DEFAULT_PERIOD = (date(2025, 1, 1), END.date())

PREWAR_MONTHS = ("2026-01-01", "2026-02-01")   # pre-war traffic = Jan-Feb 2026, the same window as the shipping panel
CURRENCY = {"United Kingdom": "GBP", "United States": "USD", "South Korea": "KRW",
            "China": "CNY", "India": "INR"}               # everyone else pays in euros
SYMBOL = {"EUR": "€", "GBP": "£", "USD": "$", "KRW": "₩", "CNY": "¥", "INR": "₹"}
TYPICAL_BILL = {"EUR": 200, "GBP": 170, "USD": 220, "KRW": 150000, "CNY": 600, "INR": 3000}

MAX_LAG_MONTHS = 6             # longest oil -> bills delay tested
COLOURS = ["#2e6fd8", "#c2410c", "#0f9b8e", "#7c5cd6", "#d48806", "#2e9b57",
           "#d23f3f", "#1b2a41", "#98a2b3", "#e377c2", "#17becf"]


# =============================================================================
# 2. ANALYSIS
# =============================================================================

def series_for(inflation: pd.DataFrame, country: str, measure: str) -> pd.Series:
    """One country's inflation for one measure, as a monthly Series."""
    rows = inflation[(inflation["country"] == country) & (inflation["measure"] == measure)]
    return rows.set_index("date")["value"].sort_index()


def chosen_period() -> tuple[pd.Timestamp, pd.Timestamp]:
    """Draw the panel's time slider and return (first month, last day) of the period picked.

    The start is moved back to the 1st of its month, because the data is
    monthly (each month is dated on the 1st).
    """
    st.session_state.setdefault("infl_period", DEFAULT_PERIOD)      # first visit: Jan 2025 to Oct 2026
    start, end = st.slider("Period", min_value=date(START.year + 1, 1, 1), max_value=END.date(),
                           format="MMM YYYY", key="infl_period",
                           help="The chart shows these months. The numbers and the bill use the last one.")
    return pd.Timestamp(start).to_period("M").to_timestamp(), pd.Timestamp(end)


def in_period(s: pd.Series | pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp):
    """Only the rows dated from start to end (both included)."""
    return s[(s.index >= start) & (s.index <= end)]


def change_since_war(s: pd.Series) -> tuple[float, float] | None:
    """Latest value and its change since February 2026, the last month before the war.

    Returns None if there is no data from both before and after the war.
    """
    before, after = s[s.index < WAR_START], s[s.index >= WAR_START]
    if before.empty or after.empty:
        return None
    return s.iloc[-1], s.iloc[-1] - before.iloc[-1]


def traffic_vs_normal(hormuz: pd.DataFrame, column: str = "capacity_tanker") -> pd.Series:
    """Monthly Hormuz tanker capacity as a % of the pre-war average (100 = pre-war level)."""
    normal = hormuz.loc[PREWAR_MONTHS[0]:PREWAR_MONTHS[1], column].mean()
    return hormuz[column] / normal * 100


def currency_of(country: str) -> str:
    """The currency a country's households pay in."""
    return CURRENCY.get(country, "EUR")


def oil_change_yoy(oil: pd.DataFrame, currency: str) -> pd.Series:
    """Percentage change in the local-currency price of Brent vs 12 months earlier."""
    return (oil[currency].pct_change(12) * 100).dropna()


def fit_passthrough(energy: pd.Series, oil_change: pd.Series) -> dict:
    """How strongly, and how fast, oil prices feed into energy inflation.

    Step 1: for each delay of 0 to MAX_LAG_MONTHS months, correlate energy
            inflation with the oil-price change that many months earlier.
    Step 2: keep the delay with the highest correlation.
    Step 3: fit a straight line (least squares, np.polyfit):
                energy inflation = intercept + slope x oil change
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
            "r2": correlations[best_lag] ** 2, "points": pair, "correlations": correlations}


def new_bill(model: dict, brent_now: float, brent_future: float, bill: float) -> dict:
    """Energy inflation and the monthly bill a year from now, if Brent moves from brent_now to brent_future."""
    oil_change = (brent_future / brent_now - 1) * 100
    energy = model["intercept"] + model["slope"] * oil_change
    return {"oil_change": oil_change, "energy": energy, "bill": bill * (1 + energy / 100)}



def story_numbers(inflation: pd.DataFrame, traffic: pd.Series | None, end: pd.Timestamp = END) -> list[dict]:
    """The three numbers at the top of Section 1, as of the end of the time period, each with a note.

    Each card: label, value, delta (change since February 2026, the last month
    before the war; none if the period ends before then), delta_color, note.
    A card is left out if its data is missing.
    """
    feb = pd.Timestamp("2026-02-01")
    cards = []
    others = []                                  # food and services, to compare with energy in its note
    for measure in ("Food", "Services"):
        o = series_for(inflation, "Euro area", measure).loc[:end]
        if not o.empty:
            moved = change_since_war(o)
            others.append(f"{measure.lower()} {o.iloc[-1]:.1f}%" + (f" ({moved[1]:+.1f} pts)" if moved else ""))
    energy_note = "Energy is the direct link from oil to prices."
    if others:
        energy_note += " Same month: " + ", ".join(others) + "."
    for measure, label, note in [
            ("Headline", "Euro-area inflation", "All prices, average of the euro countries. The ECB aims for 2%."),
            ("Energy", "Euro-area energy inflation", energy_note)]:
        s = series_for(inflation, "Euro area", measure).loc[:end]
        if s.empty:
            continue
        result = change_since_war(s)
        cards.append(dict(label=f"{label}, {s.index[-1]:%b %Y}", value=f"{s.iloc[-1]:.1f}%",
                          delta=f"{result[1]:+.1f} pts since pre-war" if result else None,
                          delta_color="inverse", note=note))
    if traffic is not None and not traffic.loc[:end].empty:
        t = traffic.loc[:end]
        delta = f"{t.iloc[-1] - 100:+.0f} pts vs pre-war" if t.index[-1] > feb else None
        cards.append(dict(label=f"Tankers through Hormuz, {t.index[-1]:%b %Y}", value=f"{t.iloc[-1]:.1f}%",
                          delta=delta, delta_color="normal",
                          note="Oil-tanker capacity through the strait, as a % of Jan-Feb 2026 (IMF PortWatch)."))
        return cards

def key_takeaway(inflation: pd.DataFrame, end: pd.Timestamp = END) -> str:
    """The panel's main point in two sentences, as of the end of the period, counting every country."""
    if end < WAR_START:
        return "This period ends before the war started. Drag the end past February 2026 to see what changed."
    rises = [r[1] for r in (change_since_war(series_for(inflation, c, "Energy").loc[:end]) for c in all_countries()) if r]
    energy = change_since_war(series_for(inflation, "Euro area", "Energy").loc[:end])
    headline = change_since_war(series_for(inflation, "Euro area", "Headline").loc[:end])
    if not rises or not energy or not headline:
        return ""
    up = sum(r > 0 for r in rises)
    which = "all" if up == len(rises) else f"{up} of the"
    return (f"Energy prices have risen faster since the war started in {which} {len(rises)} countries that publish "
            f"them. In the euro area, energy inflation is up {energy[1]:.0f} points, but overall inflation is up "
            f"only {headline[1]:.1f}.")


def months_word(n: int) -> str:
    """'1 month' or '2 months'."""
    return f"{n} month{'s' if n != 1 else ''}"
# =============================================================================
# 3. CHARTS - Plotly
# =============================================================================

def style(fig: go.Figure, height: int, title: str, title_size: int = 16, **layout) -> go.Figure:
    """The look shared by both charts: white background, dark text, title on the left.

    The charts are drawn with theme=None, so Streamlit keeps this white look
    even when the computer is in dark mode.
    """
    settings = dict(template="plotly_white", height=height, hovermode="x unified",
                    paper_bgcolor="white", plot_bgcolor="white", font=dict(color="#17202e"),
                    title=dict(text=f"<b>{title}</b>", x=0, xanchor="left", font=dict(size=title_size)),
                    margin=dict(l=10, r=20, t=50, b=40), legend=dict(orientation="h", y=-0.15, x=0))
    settings.update(layout)          # anything passed in replaces the default
    fig.update_layout(**settings)
    return fig


def add_war_and_events(fig: go.Figure, start: pd.Timestamp, end: pd.Timestamp = END,
                       label: bool = True) -> go.Figure:
    """Shade each phase of the war in its own light colour, with its name at the top.

    Only the part of each phase inside the chosen period is shaded. Names sit at
    two heights in turn, so a short phase's name doesn't run into the next one.
    """
    for i, (name, p_start, p_end, colour) in enumerate(PHASES):
        x0, x1 = max(pd.Timestamp(p_start), start), min(pd.Timestamp(p_end), end)
        if x0 >= x1:                                 # phase outside the chosen period
            continue
        fig.add_vrect(x0=x0, x1=x1, fillcolor=colour, opacity=0.09, line_width=0, layer="below")
        if label:
            fig.add_annotation(x=x0, y=1 if i % 2 == 0 else 0.93, yref="paper", text=name, showarrow=False,
                               xanchor="left", yanchor="top", xshift=3, font=dict(size=11, color=colour),
                               bgcolor="rgba(255,255,255,0.8)")
    return fig


def chart_inflation(inflation, countries, measure, start, end, traffic=None) -> go.Figure:
    """The panel's one chart: inflation by country, with the war's phases shaded and
    tanker traffic through Hormuz as a light grey area on the right-hand axis."""
    fig = go.Figure()
    if traffic is not None:
        t = in_period(traffic, start, end)
        fig.add_trace(go.Scatter(x=t.index, y=t.values, name="Tankers through Hormuz (% of pre-war, right axis)",
                                 yaxis="y2", mode="lines", fill="tozeroy", line=dict(color="rgba(27,42,65,0.35)", width=1),
                                 fillcolor="rgba(27,42,65,0.07)", hovertemplate="Tankers: %{y:.0f}% of pre-war<extra></extra>"))
    for colour, country in zip(COLOURS, countries):
        s = in_period(series_for(inflation, country, measure), start, end)
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=country, mode="lines",
                                 line=dict(color=colour, width=3 if country == countries[0] else 2),
                                 hovertemplate=f"{country}: %{{y:.1f}}%<extra></extra>"))
    fig.add_hline(y=TARGET, line=dict(color="#98a2b3", dash="dash", width=1),
                  annotation_text="2% target", annotation_position="bottom left")
    add_war_and_events(fig, start, end)
    return style(fig, 450, f"{measure} inflation since the war started", margin=dict(l=10, r=50, t=50, b=40),
                 yaxis=dict(title=f"{measure} inflation, % a year", ticksuffix="%"),
                 yaxis2=dict(overlaying="y", side="right", range=[0, 300], tickvals=[0, 50, 100], ticksuffix="%",
                             showgrid=False, tickfont=dict(size=10, color="#98a2b3")),
                 xaxis=month_axis(start, end))


def chart_by_country(inflation: pd.DataFrame, measure: str, end: pd.Timestamp, highlight: list) -> go.Figure:
    """Bar chart: how far each country's inflation has moved since February 2026, biggest at the top.

    The countries ticked in the Countries box are orange; the rest are grey.
    """
    changes = {}
    for country in all_countries():
        moved = change_since_war(series_for(inflation, country, measure).loc[:end])
        if moved:
            changes[country] = moved[1]
    ranked = sorted(changes, key=changes.get)              # smallest first = drawn at the bottom
    fig = go.Figure(go.Bar(x=[changes[c] for c in ranked], y=ranked, orientation="h",
                           marker_color=["#c2410c" if c in highlight else "#c9ced6" for c in ranked],
                           text=[f"{changes[c]:+.1f} pts" for c in ranked], textposition="outside",
                           hovertemplate="%{y}: %{x:+.1f} points<extra></extra>"))
    return style(fig, 450, f"{measure} inflation: change since the war started, {min(end, END):%b %Y}",
                 showlegend=False, hovermode="closest",
                 xaxis=dict(title="Change since February 2026 (percentage points)", zeroline=True))
    
    
def month_axis(start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """An x-axis from start to end whose ticks count back from the LAST month, so it is always labelled."""
    months = (end.year - start.year) * 12 + end.month - start.month
    step = 1 if months <= 12 else 2 if months <= 24 else 3 if months <= 48 else 6 if months <= 96 else 12
    return dict(range=[start, end], tick0=end.to_period("M").to_timestamp(), dtick=f"M{step}", tickformat="%b %Y")






# =============================================================================
# 4. LAYOUT
# =============================================================================

def story_card(col, card: dict) -> None:
    """One small number above the chart. Its note shows when you hover over the (?) icon."""
    note = card.get("note")
    col.metric(card["label"], card["value"], card.get("delta"), delta_color=card.get("delta_color", "normal"),
               help=note.replace("$", "\\$") if note else None)      # \\$ stops Streamlit reading $...$ as maths
        
    

def chart_sensitivity(model: dict, brent_now: float, brent_future: float, bill: float, symbol: str) -> go.Figure:
    """Sensitivity analysis: the new monthly bill at every oil price from $40 to $200, with your pick marked."""
    prices = np.arange(40, 205, 5)
    bills = [new_bill(model, brent_now, p, bill)["bill"] for p in prices]
    fig = go.Figure(go.Scatter(x=prices, y=bills, mode="lines", line=dict(color="#c2410c", width=2),
                               hovertemplate=f"Oil $%{{x}}: {symbol}%{{y:,.0f}} a month<extra></extra>"))
    fig.add_trace(go.Scatter(x=[brent_future], y=[new_bill(model, brent_now, brent_future, bill)["bill"]],
                             mode="markers", marker=dict(size=10, color="#c2410c"), hoverinfo="skip"))
    fig.add_hline(y=bill, line=dict(color="#98a2b3", dash="dash", width=1),
                  annotation_text="today's bill", annotation_position="bottom right")
    return style(fig, 200, "Your bill at other oil prices", title_size=12, showlegend=False, hovermode="closest",
                 margin=dict(l=10, r=10, t=30, b=30), xaxis=dict(tickprefix="$", dtick=40),
                 yaxis=dict(tickprefix=symbol))
    
    
def bill_calculator(inflation: pd.DataFrame, oil: pd.DataFrame, end: pd.Timestamp) -> None:
    """The small 'Your energy bill' box: pick a country, an oil price and today's bill."""
    st.markdown("**Your energy bill**")   
    st.caption("What a new oil price would mean for you")
    options = [c for c in all_countries() if currency_of(c) in oil and not series_for(inflation, c, "Energy").empty]
    country = st.selectbox("Country", options, key="infl_hh_country",
                           index=options.index("Ireland") if "Ireland" in options else 0)
    currency = currency_of(country)
    symbol = SYMBOL[currency]
    brent_future = st.slider("Oil price in a year ($ a barrel)", 40, 200, 120, step=5, key="infl_brent")
    typical = TYPICAL_BILL[currency]
    bill = st.number_input(f"Monthly bill today ({symbol})", 0, typical * 10, typical,
                           step=max(10, typical // 20), key=f"infl_bill_{currency}")
    base = oil.index[oil.index <= end][-1]                  # the last month of the time period
    brent_now = float(oil.loc[base, "USD"])
    model = fit_passthrough(series_for(inflation, country, "Energy"), oil_change_yoy(oil, currency))
    result = new_bill(model, brent_now, brent_future, bill)
    extra = 12 * (result["bill"] - bill)
    st.metric("New monthly bill", f"{symbol}{result['bill']:,.0f}",
              f"{'+' if extra >= 0 else '-'}{symbol}{abs(extra):,.0f} a year", delta_color="inverse")
    st.caption(f"From {base:%b %Y}, when oil was \\${brent_now:.0f} a barrel. Energy inflation would be "
               f"{result['energy']:.1f}%. Bills usually follow oil about {months_word(model['lag'])} later.")
    st.plotly_chart(chart_sensitivity(model, brent_now, brent_future, bill, symbol),
                    width="stretch", theme=None, key="infl_sensitivity")
    


# =============================================================================
# PANEL
# =============================================================================

def render() -> None:
    """Draw the whole panel. app.py runs this file, which calls render() at the bottom."""
    data = load_data()
    problems = {k: v for k, v in data["status"].items() if not v.startswith(("saved", "live"))}
    if problems:
        st.warning("Some data could not be loaded: " + " · ".join(f"{k}: {v}" for k, v in problems.items()))
    if data["inflation"] is None:
        st.error("No inflation data. Check the inflation_*.csv files in the data folder.")
        return
    inflation, oil = data["inflation"], data["oil"]
    traffic = traffic_vs_normal(data["hormuz"]) if data["hormuz"] is not None else None
    takeaway = st.empty()                            # filled in once the period is known

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        start, end = chosen_period()
    countries = c2.multiselect("Countries", all_countries(), key="infl_countries",
                               default=["Euro area", "United Kingdom", "United States"])
    measure = c3.selectbox("Measure", MEASURES, index=1, key="infl_measure")
    takeaway.success("**Key takeaway**  \n" + key_takeaway(inflation, end))

    st.subheader("Inflation since the war")
    chart_col, calc_col = st.columns([3, 1], gap="medium")
    with chart_col.container(border=True):
        for col, card in zip(st.columns(3), story_numbers(inflation, traffic, end)):
            story_card(col, card)
        view = st.radio("View", ["Over time", "By country"], horizontal=True, key="infl_view")
        have = [c for c in countries if not series_for(inflation, c, measure).empty]
        if view == "By country" and end >= WAR_START:
            st.plotly_chart(chart_by_country(inflation, measure, end, have), width="stretch", theme=None,
                            key="infl_bars")
        elif view == "By country":
            st.info("The period ends before the war, so there is no change to compare yet.")
        elif have:
            st.plotly_chart(chart_inflation(inflation, have, measure, start, end, traffic),
                            width="stretch", theme=None, key="infl_chart")
        else:
            st.info("Pick at least one country that publishes this measure.")
    if oil is not None:
        with calc_col.container(border=True):
            bill_calculator(inflation, oil, end)
    method_and_sources(data["status"])


def method_and_sources(status: dict) -> None:
    """A closed box at the bottom with the method and the sources."""
    with st.expander("Method and sources"):
        st.markdown(
            "**The bill calculator** looks at how energy prices have followed oil prices since 2016. It tries delays "
            f"of 0 to {MAX_LAG_MONTHS} months, keeps the one that fits best, and draws a straight line through the "
            "result. Your bill is read off that line. It ignores wages and exchange-rate changes, so treat it as a "
            "rough estimate.\n\n"
            "**Data**, monthly to October 2026: Eurostat HICP for the euro countries; OECD CPI for the UK, South "
            "Korea, China and India; the US Bureau of Labor Statistics for the USA (to September 2026, and October "
            "2025 was never published because of the government shutdown); Brent and exchange rates from Yahoo "
            "Finance; oil tankers through Hormuz from IMF PortWatch, against Jan-Feb 2026. China has no energy "
            "figures and India only headline.\n\n"
            "Loaded from: " + ", ".join(f"{k}: {v}" for k, v in status.items()) + ".")
        
        
def render_card() -> None:
    """The small version for the home page: two numbers and one chart, like the other panels' cards."""
    data = load_data()
    inflation = data["inflation"]
    if inflation is None:
        st.error("No inflation data available.")
        return
    traffic = traffic_vs_normal(data["hormuz"]) if data["hormuz"] is not None else None

    c1, c2 = st.columns(2)
    for col, card in zip((c1, c2), story_numbers(inflation, traffic, END)[1:]):
        col.metric(card["label"], card["value"], card["delta"], delta_color=card["delta_color"])

    fig = chart_inflation(inflation, ["Euro area", "United Kingdom", "United States"], "Energy",
                          pd.Timestamp("2025-09-01"), END, traffic)
    fig.update_layout(height=270, title_text="", showlegend=False, margin=dict(l=10, r=40, t=10, b=30))
    st.plotly_chart(fig, width="stretch", theme=None, key="infl_card_chart", config={"displayModeBar": False})
    
    
if __name__ == "__main__":
    # Runs when you start this file directly, and when app.py runs it inside its tab.
    st.set_page_config(page_title="Inflation & households", layout="wide")
    render()
