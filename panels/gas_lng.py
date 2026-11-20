"""
Panel 3 - Gas & LNG
Author: Eabha Kelly

Story: Hormuz carries about a fifth of the world's LNG, nearly all of it from
Qatar. This panel shows what closing it has done to gas prices, LNG shipping,
the countries that depend on Qatari gas, and Europe's winter storage.

Run on its own:  python3 -m streamlit run panels/gas_lng.py
Use in app.py:   from panels import gas_lng   then   gas_lng.render()

Every number comes from a named source (see the Sources line at the bottom).
Interactive charts use Plotly.
"""
import plotly.graph_objects as go
import streamlit as st

# ---------- colours (same as the design) ----------
RED, AMBER, TEAL, BLUE, VIOLET, MUTED = "#ff5a4e", "#ffb020", "#2dd4bf", "#5aa9ff", "#a78bfa", "#8fa0bb"
GRID, INK, DARK = "#22314a", "#e8edf5", "#0b1320"
CFG = {"displayModeBar": False}

# ======================================================================
# DATA
# ======================================================================

# --- Key events (marked on the price chart) ---
EVENTS = [
    ("2026-02-28", "War begins"),
    ("2026-03-19", "Ras Laffan hit"),
    ("2026-04-08", "Ceasefire"),
    ("2026-06-17", "US–Iran MOU"),
    ("2026-07-07", "Strikes resume"),
    ("2026-08-01", "LNG tanker struck"),
]

# --- 1. Price path: World Bank monthly average of Dutch TTF, $/MMBtu (one consistent series) ---
WB_TTF = [("2026-01-15", 11.76), ("2026-02-15", 11.24), ("2026-03-15", 17.91), ("2026-04-15", 15.41),
          ("2026-05-15", 16.17), ("2026-06-15", 15.17), ("2026-07-15", 18.06), ("2026-08-15", 21.11),
          ("2026-09-15", 25.42), ("2026-10-15", 28.50)]
TTF_2025_AVG = 11.96
DATA_AS_OF = "Data as of 15 November 2026 · monthly prices to October 2026"

# --- 2. Dumbbell: monthly averages vs 2022 ---
ROWS = ["Before the war (Feb 2026 avg)", "March 2026 avg", "October 2026 avg", "2022 crisis peak (approx.)"]
TTF = [11.24, 17.91, 28.50, 90]   # World Bank monthly averages (2022: approx.)
JKM = [10.82, 21.0, 28.59, 70]
USD_PER_EUR_MWH = 0.346  # 1 €/MWh ≈ 0.346 $/MMBtu (approximate FX)
ROW_NOTES = [
    "Both benchmarks were around $11/MMBtu in February, before the 28 February strikes.",
    "Prices jumped to their highest monthly average since January 2023. Asia rose more, because most Hormuz LNG normally goes there.",
    "The highest level since December 2022. The Europe–Asia gap has almost closed, because both regions are competing for the same US cargoes.",
    "For comparison: after Russia invaded Ukraine, TTF hit about $90 and Europe paid far more than Asia.",
]

# --- 3. Hormuz LNG tanker traffic by month ---
# Two trackers count differently: Kpler counts all LNG-carrier transits, S&P counts laden tankers exiting.
TRANSITS = [  # month, count, source, note
    ("Feb", 85, "S&P Global", "Pre-war month: roughly 85 LNG ships exited"),
    ("Mar", 0, "Kpler", "No LNG carriers crossed"),
    ("Apr", 4, "Kpler", "UAE-linked ships, transponders off"),
    ("May", 8, "Kpler", "First Qatari cargo since the war (to Pakistan, 9 May)"),
    ("Jun", 40, "Kpler", "Reopening after the 17 June MOU"),
    ("Jul", 18, "S&P Global", "None after 11 July, when strikes resumed"),
    ("Aug", 3, "S&P Global", "No transits after 17 August"),
    ("Sep", 23, "S&P Global", "Qatari tankers resume, some with transponders off"),
    ("Oct", 31, "S&P Global", "Highest since the war began, still about a third of normal"),
]
PREWAR_MONTHLY = 85

# --- 4. Who depends on Qatari LNG (2024, Bcf/d) ---
EXPOSURE = [  # country, region, total LNG imports, from Qatar, Qatar share %
    ("Pakistan", "Asia", 1.1, 0.9, 89.3), ("Italy", "Europe", 1.4, 0.6, 45.6),
    ("Belgium", "Europe", 0.7, 0.3, 40.6), ("India", "Asia", 3.7, 1.5, 40.3),
    ("Singapore", "Asia", 0.8, 0.2, 27.6), ("Taiwan", "Asia", 2.8, 0.7, 25.3),
    ("China", "Asia", 10.2, 2.4, 24.0), ("Thailand", "Asia", 1.5, 0.3, 19.9),
    ("South Korea", "Asia", 6.1, 1.2, 19.2), ("United Kingdom", "Europe", 0.9, 0.1, 8.4),
    ("Spain", "Europe", 1.8, 0.1, 5.5), ("Japan", "Asia", 8.6, 0.4, 4.4),
    ("France", "Europe", 2.5, 0.0, 1.6),
]

# --- 5. EU gas storage, % full ---
STORE_2026 = [  # date, % full
    ("2026-04-01", 27.7), ("2026-06-09", 42.8), ("2026-07-26", 55.4), ("2026-08-15", 60.8),
    ("2026-08-27", 63.3), ("2026-09-23", 70.4), ("2026-09-30", 71.5), ("2026-10-06", 73.0),
    ("2026-10-27", 75.0), ("2026-11-01", 74.6), ("2026-11-15", 70.4),
]
STORE_2025 = [  # same calendar dates, one year earlier
    ("2026-04-01", 34.1), ("2026-06-09", 51.4), ("2026-08-27", 76.0), ("2026-09-30", 82.5),
    ("2026-10-06", 82.9), ("2026-10-27", 82.9), ("2026-11-15", 82.0),
]
STORE_5YR = [  # five-year average for the date, derived from the reported gap
    ("2026-08-27", 80.5), ("2026-09-30", 87.2), ("2026-10-06", 88.1), ("2026-11-15", 88.4),
]



# ======================================================================
# CHART HELPERS
# ======================================================================
def _layout(fig, **kw):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color=INK, size=13),
        hoverlabel=dict(bgcolor=DARK, bordercolor="#26354f"), **kw)
    return fig


def _add_events(fig, y_top):
    for d, label in EVENTS:
        fig.add_vline(x=d, line=dict(color="#33445f", width=1, dash="dot"))
        fig.add_annotation(x=d, y=y_top, text=label, showarrow=False, textangle=-90,
                           xanchor="right", yanchor="top", font=dict(size=10, color=MUTED))


def price_path_chart(show_events):
    x = [p[0] for p in WB_TTF]; y = [p[1] for p in WB_TTF]
    chg = [None] + [(y[i] / y[i - 1] - 1) * 100 for i in range(1, len(y))]
    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="lines+markers+text", line=dict(color=BLUE, width=3, shape="spline", smoothing=0.6),
        marker=dict(size=10, color=[TEAL if c is not None and c < 0 else BLUE for c in chg], line=dict(color=DARK, width=1.5)),
        fill="tozeroy", fillcolor="rgba(90,169,255,.10)",
        text=[f"${v:.1f}" for v in y], textposition="top center", textfont=dict(size=11, color="#c7d2e3"),
        customdata=["—" if c is None else (f"▲ +{c:.1f}%" if c >= 0 else f"▼ {c:.1f}%") + " vs previous month" for c in chg],
        hovertemplate="<b>%{x|%B %Y}: $%{y:.2f}/MMBtu</b><br>%{customdata}<extra></extra>"))
    fig.add_hline(y=TTF_2025_AVG, line=dict(color=TEAL, dash="dash", width=1.5),
                  annotation_text=f"2025 average ${TTF_2025_AVG}", annotation_font_color=TEAL, annotation_position="bottom left")
    if show_events:
        _add_events(fig, 34)
    return _layout(fig, height=430, margin=dict(l=10, r=20, t=20, b=30), hovermode="x", showlegend=False,
                   xaxis=dict(type="date", range=["2026-01-01", "2026-11-01"], gridcolor=GRID, tickformat="%b", dtick="M1",
                              rangeslider=dict(visible=True, thickness=0.06, bgcolor="#121c2d")),
                   yaxis=dict(title="$ per MMBtu", gridcolor=GRID, range=[0, 35], fixedrange=True))


def _convert(values, unit):
    if unit == "€/MWh":
        return [v / USD_PER_EUR_MWH for v in values]
    if unit == "% vs pre-war":
        return [(v / values[0] - 1) * 100 for v in values]
    return list(values)


def _selected_row():
    try:
        pts = st.session_state["gas_dumb"]["selection"]["points"]
        if pts:
            return ROWS.index(pts[0]["y"])
    except (KeyError, TypeError, ValueError, IndexError):
        pass
    return None


def dumbbell_chart(unit, highlight):
    ttf, jkm = _convert(TTF, unit), _convert(JKM, unit)
    fig = go.Figure()
    for i, row in enumerate(ROWS):
        fig.add_trace(go.Scatter(x=[ttf[i], jkm[i]], y=[row, row], mode="lines", hoverinfo="skip", showlegend=False,
                                 line=dict(color=MUTED if i == highlight else "#33445f", width=9 if i == highlight else 6)))
    opac = [1 if highlight is None or i == highlight else 0.35 for i in range(len(ROWS))]
    fmt = "%{x:+.0f}%" if unit == "% vs pre-war" else "%{x:.1f} " + unit
    fig.add_trace(go.Scatter(x=ttf, y=ROWS, mode="markers", name="Europe (TTF)", hovertemplate="TTF: " + fmt + "<extra></extra>",
                             marker=dict(size=16, color=BLUE, opacity=opac, line=dict(color=DARK, width=2))))
    fig.add_trace(go.Scatter(x=jkm, y=ROWS, mode="markers", name="Asia (JKM)", hovertemplate="JKM: " + fmt + "<extra></extra>",
                             marker=dict(size=16, color=VIOLET, symbol="diamond", opacity=opac, line=dict(color=DARK, width=2))))
    fig.add_shape(type="rect", xref="paper", yref="y", x0=0, x1=1, y0=2.5, y1=3.5,
                  fillcolor="rgba(255,255,255,.03)", line_width=0)
    return _layout(fig, height=380, margin=dict(l=10, r=20, t=10, b=60), clickmode="event+select",
                   xaxis=dict(title=unit, gridcolor=GRID, rangemode="tozero", ticksuffix="%" if unit == "% vs pre-war" else ""),
                   yaxis=dict(autorange="reversed", fixedrange=True, automargin=True), legend=dict(orientation="h", y=-0.22, x=0))


def transits_chart(as_pct):
    vals = [t[1] / PREWAR_MONTHLY * 100 if as_pct else t[1] for t in TRANSITS]
    colours = [MUTED if t[0] == "Feb" else (AMBER if t[2] == "Kpler" else RED) for t in TRANSITS]
    fig = go.Figure(go.Bar(
        x=[t[0] for t in TRANSITS], y=vals, marker_color=colours, showlegend=False,
        text=[f"{v:.0f}%" if as_pct else str(t[1]) for v, t in zip(vals, TRANSITS)], textposition="outside",
        customdata=[[t[2], t[3]] for t in TRANSITS],
        hovertemplate="<b>%{x}: %{text}</b><br>%{customdata[1]}<br><i>Source: %{customdata[0]}</i><extra></extra>"))
    ref = 100 if as_pct else PREWAR_MONTHLY
    fig.add_hline(y=ref, line=dict(color=TEAL, dash="dash", width=1.5),
                  annotation_text="Pre-war level", annotation_font_color=TEAL, annotation_position="top right")
    for name, c in [("Kpler (all LNG-carrier transits)", AMBER), ("S&P Global (laden tankers exiting)", RED)]:
        fig.add_trace(go.Bar(x=[None], y=[None], name=name, marker_color=c, showlegend=True))
    return _layout(fig, height=400, margin=dict(l=10, r=20, t=30, b=40), showlegend=True, barmode="overlay",
                   legend=dict(orientation="h", y=-0.15, x=0),
                   yaxis=dict(title="% of pre-war" if as_pct else "LNG tankers per month", gridcolor=GRID,
                              range=[0, 115 if as_pct else 98], ticksuffix="%" if as_pct else ""),
                   xaxis=dict(fixedrange=True))


def exposure_chart(view, regions, metric):
    rows = [r for r in EXPOSURE if r[1] in regions]
    colour = {"Asia": VIOLET, "Europe": BLUE}
    if view == "Ranking":
        key = 4 if metric == "Share of LNG imports from Qatar" else 3
        rows = sorted(rows, key=lambda r: r[key])
        fig = go.Figure(go.Bar(
            y=[r[0] for r in rows], x=[r[key] for r in rows], orientation="h",
            marker_color=[colour[r[1]] for r in rows],
            text=[f"{r[key]:.0f}%" if key == 4 else f"{r[key]:.1f}" for r in rows], textposition="outside",
            customdata=[[r[1], r[2], r[3], r[4]] for r in rows],
            hovertemplate="<b>%{y}</b> (%{customdata[0]})<br>Qatar share: %{customdata[3]:.1f}%<br>"
                          "From Qatar: %{customdata[2]:.1f} Bcf/d of %{customdata[1]:.1f} Bcf/d total<extra></extra>"))
        return _layout(fig, height=440, margin=dict(l=10, r=40, t=10, b=40),
                       xaxis=dict(title="% of LNG imports from Qatar" if key == 4 else "Bcf/d from Qatar",
                                  gridcolor=GRID, ticksuffix="%" if key == 4 else ""),
                       yaxis=dict(fixedrange=True, automargin=True, ticksuffix="  "))
    # Bubble view: x = how big an LNG buyer, y = how dependent on Qatar, size = volume at risk
    fig = go.Figure()
    for reg in regions:
        rr = [r for r in rows if r[1] == reg]
        fig.add_trace(go.Scatter(
            x=[r[2] for r in rr], y=[r[4] for r in rr], mode="markers+text", name=reg,
            text=[r[0] for r in rr], textposition="top center", textfont=dict(size=11, color="#c7d2e3"),
            marker=dict(size=[max(10, r[3] * 38) for r in rr], color=colour[reg], opacity=0.75,
                        line=dict(color=DARK, width=1.5)),
            customdata=[[r[3]] for r in rr],
            hovertemplate="<b>%{text}</b><br>Total LNG imports: %{x:.1f} Bcf/d<br>Qatar share: %{y:.1f}%<br>"
                          "At risk: %{customdata[0]:.1f} Bcf/d<extra></extra>"))
    fig.add_hline(y=19.6, line=dict(color=MUTED, dash="dot"), annotation_text="World average 19.6%",
                  annotation_font_color=MUTED, annotation_position="bottom right")
    return _layout(fig, height=440, margin=dict(l=10, r=20, t=10, b=40), legend=dict(orientation="h", y=1.06, x=0),
                   xaxis=dict(title="Total LNG imports (Bcf/d) – how big a buyer", type="log", gridcolor=GRID),
                   yaxis=dict(title="% from Qatar – how exposed", gridcolor=GRID, range=[-5, 100], ticksuffix="%"))


def storage_chart(show_2025, show_5yr, show_targets):
    fig = go.Figure()
    if show_5yr:
        fig.add_trace(go.Scatter(x=[p[0] for p in STORE_5YR], y=[p[1] for p in STORE_5YR], name="5-year average",
                                 mode="lines+markers", line=dict(color=MUTED, dash="dash", width=2), marker=dict(size=7),
                                 hovertemplate="5-yr avg: %{y:.1f}%<extra></extra>"))
    if show_2025:
        fig.add_trace(go.Scatter(x=[p[0] for p in STORE_2025], y=[p[1] for p in STORE_2025], name="Same date in 2025",
                                 mode="lines+markers", line=dict(color=AMBER, width=2), marker=dict(size=7),
                                 hovertemplate="2025: %{y:.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=[p[0] for p in STORE_2026], y=[p[1] for p in STORE_2026], name="2026",
                             mode="lines+markers", line=dict(color=RED, width=3.5), marker=dict(size=9),
                             fill="tozeroy", fillcolor="rgba(255,90,78,.08)",
                             hovertemplate="<b>2026: %{y:.1f}%</b><extra></extra>"))
    if show_targets:
        fig.add_hline(y=90, line=dict(color=TEAL, dash="dot"), annotation_text="EU target 90%",
                      annotation_font_color=TEAL, annotation_position="top left")
        fig.add_hline(y=80, line=dict(color=TEAL, dash="dot", width=1), annotation_text="Flexible target 80%",
                      annotation_font_color=TEAL, annotation_position="bottom left")
    fig.add_annotation(x="2026-10-27", y=75.0, text="Peak 75% (27 Oct)", showarrow=True, arrowcolor=MUTED,
                       ax=-60, ay=-35, font=dict(size=11, color=INK))
    fig.add_annotation(x="2026-04-01", y=27.7, text="Summer starts at 28%", showarrow=True, arrowcolor=MUTED,
                       ax=50, ay=-40, font=dict(size=11, color=INK))
    return _layout(fig, height=420, margin=dict(l=10, r=20, t=10, b=40), hovermode="x unified",
                   xaxis=dict(type="date", range=["2026-03-20", "2026-11-25"], tickformat="%b", gridcolor=GRID),
                   yaxis=dict(title="% full", range=[0, 100], ticksuffix="%", gridcolor=GRID),
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


# ======================================================================
# PAGE
# ======================================================================
def render() -> None:
    """Draw the whole panel. app.py calls this inside the panel's tab."""
    st.header("🔥 Gas & LNG: Qatar's exports cut off")
    st.caption("Nearly all of Qatar's LNG, about a fifth of world supply, has to pass through Hormuz. "
               "Then the 19 March strike on Ras Laffan knocked out part of its capacity for years.")
    st.markdown(f"`{DATA_AS_OF}`")

    # ---- KPI tiles ----
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Qatari LNG capacity offline", "16–17%",
              help="After the 19 March strike on Ras Laffan. This damage lasts even if the strait reopens. Sources: S&P Global, IEA.")
    k1.caption("For about 4 years")
    k2.metric("Hormuz LNG tankers, Oct", "31",
              help="Laden LNG tankers exiting in October, the most since the war began (pre-war ≈ 85 a month). Source: S&P Global.")
    k2.caption("About a third of the pre-war ~85 a month")
    k3.metric("Asian LNG (JKM), Oct avg", "$28.59", delta="+164% vs Feb", delta_color="inverse",
              help="Per MMBtu, near-month, October average vs $10.82 in February. Source: EIA, citing Bloomberg.")
    k4.metric("EU gas storage, 15 Nov", "70.4%", delta="-18 pts vs 5-yr avg", delta_color="normal",
              help="Lowest for the date since records began in 2011. Source: GIE data, via TASS.")

    tab1, tab2, tab3, tab4 = st.tabs(["📈 Prices", "🚢 Supply & shipping", "🌍 Who's exposed", "🏭 Europe's winter"])

    # ================= TAB 1: PRICES =================
    with tab1:
        st.subheader("European gas prices through the war")
        show_ev = st.toggle("Show key events", value=True, key="gas_ev")
        st.plotly_chart(price_path_chart(show_ev), width="stretch", theme=None, config=CFG)
        st.caption("Monthly average of the European benchmark (Dutch TTF), from the World Bank. Hover a month for the price and "
                   "the change from the month before; drag the slider under the chart to zoom in. For contrast, US gas (Henry Hub) "
                   "averaged about $3/MMBtu from August to October: the shock is in Europe and Asia. The chart below compares the two.")

        st.subheader("How big is this gas shock? 2026 vs 2022")
        unit = st.radio("Units", ["$/MMBtu", "€/MWh", "% vs pre-war"], horizontal=True, key="gas_unit")
        row = _selected_row()
        st.plotly_chart(dumbbell_chart(unit, row), width="stretch", theme=None,
                        on_select="rerun", selection_mode="points", key="gas_dumb", config=CFG)
        if row is None:
            st.caption("👆 Click a dot to compare Europe and Asia at that moment.")
        else:
            gap = JKM[row] - TTF[row]
            who = "Asia paid more" if gap > 0.05 else "Europe paid more" if gap < -0.05 else "About level"
            st.info(f"**{ROWS[row]}**: TTF ${TTF[row]}/MMBtu · JKM ${JKM[row]}/MMBtu · **{who}**"
                    f"{f' (${abs(gap):.2f})' if abs(gap) > 0.05 else ''}\n\n{ROW_NOTES[row]}")

    # ================= TAB 2: SUPPLY & SHIPPING =================
    with tab2:
        left, right = st.columns([3, 2])
        with left:
            st.subheader("LNG tankers through Hormuz each month")
            as_pct = st.toggle("Show as % of pre-war traffic", key="gas_pct")
            st.plotly_chart(transits_chart(as_pct), width="stretch", theme=None, config=CFG)
            st.caption("Hover a bar for what happened that month. Two trackers are used: Kpler counts every LNG-carrier "
                       "transit and S&P Global counts laden tankers leaving, so the bars aren't strictly like-for-like. "
                       "Some ships cross with transponders off, so true numbers may be a little higher.")
        with right:
            st.subheader("Where the world's LNG comes from, and where Hormuz LNG goes")
            st.caption("Click a segment to zoom in, and click the centre to zoom back out. EIA estimates for 2024.")
            st.plotly_chart(sunburst_chart(), width="stretch", theme=None, config=CFG)


    # ================= TAB 3: WHO'S EXPOSED =================
    with tab3:
        st.subheader("Which countries depend most on Qatari LNG?")
        c1, c2, c3 = st.columns([1.2, 1.2, 1.6])
        view = c1.radio("View", ["Ranking", "Bubble map"], horizontal=True, key="gas_view")
        regions = c2.multiselect("Regions", ["Asia", "Europe"], default=["Asia", "Europe"], key="gas_reg")
        metric = c3.radio("Rank by", ["Share of LNG imports from Qatar", "Volume from Qatar (Bcf/d)"],
                          horizontal=True, key="gas_metric", disabled=(view != "Ranking"))
        if regions:
            st.plotly_chart(exposure_chart(view, regions, metric), width="stretch", theme=None, config=CFG)
        else:
            st.warning("Pick at least one region.")
        st.caption("2024 annual averages (Energy Institute, via EPRINC). In the bubble map, further right means a bigger "
                   "LNG buyer, higher up means more dependent on Qatar, and a bigger bubble means more gas at risk. "
                   "Pakistan is the most exposed. China has the most gas at risk. Japan buys a lot of LNG but little of it from Qatar.")

    # ================= TAB 4: EUROPE'S WINTER =================
    with tab4:
        st.subheader("EU gas storage: refilling fell short")
        c1, c2, c3 = st.columns(3)
        s25 = c1.checkbox("Compare with 2025", value=True, key="gas_s25")
        s5 = c2.checkbox("Show 5-year average", value=True, key="gas_s5")
        tg = c3.checkbox("Show EU targets", value=True, key="gas_tg")
        st.plotly_chart(storage_chart(s25, s5, tg), width="stretch", theme=None, config=CFG)
        st.caption("Hover anywhere to compare years on the same date. 2026 values are GIE AGSI data as reported by Argus, "
                   "S&P Global, GMK Center and TASS. The 5-year average is derived from the reported gap to it. "
                   "Europe started summer at only 28%, never reached the 80% flexible target, and by mid-November "
                   "was drawing down faster than usual.")

    # ---- Takeaway + sources ----
    st.success("**Takeaway:** gas prices are at their highest since 2022, and LNG traffic through Hormuz is only a third "
               "of normal. Europe enters winter with record-low storage, so a cold snap could push prices higher still.")
    st.caption(
        "Sources: World Bank [Pink Sheet](https://www.worldbank.org/en/research/commodity-markets) (monthly TTF, US gas); [EIA Today in Energy](https://www.eia.gov/todayinenergy/detail.php?id=67604) and November 2026 STEO (via "
        "[Energy News Beat](https://theenergynewsbeat.substack.com/p/two-gas-markets-this-winter-about)); "
        "[IEA Gas Market Report Q2-2026](https://www.iea.org/reports/gas-market-report-q2-2026/executive-summary); "
        "[Kpler](https://www.kpler.com/blog/hormuz-strait-disruptions-trigger-a-price-spike-in-ttf-and-asian-lng-while-middle-east-exports-come-to-a-halt); "
        "[Platts JKM](https://www.spglobal.com/energy/en/news-research/latest-news/lng/090326-jkm-soars-to-highest-since-december-2022-as-middle-east-war-shuts-arbitrage-window); "
        "[World Bank via natgaschart](https://natgaschart.com/education/ttf-gas-price); "
        "[AGA](https://www.aga.org/research-policy/resource-library/natural-gas-market-indicators-october-1-2026/); "
        "[Kpler monthly transits](https://www.kpler.com/zh-tw/blog/no-lng-tankers-cross-strait-of-hormuz-since-july-11-amid-escalating-us-iran-conflict); "
        "S&P Global via [Beinsure](https://beinsure.com/news/strait-of-hormuz-lng-traffic-reaches-highest-level-since-iran-war-began/); "
        "[EPRINC / Energy Institute](https://eprinc.org/wp-content/uploads/2026/03/Chart2026-11-HormuzLNGExports.pdf); "
        "GIE storage data via [TASS](https://tass.com/economy/2219477), [Argus](https://www.argusmedia.com/news-and-insights/latest-market-news/2810699-europe-faces-challenging-gas-restocking-season), "
        "[S&P Global](https://www.spglobal.com/energy/en/news-research/latest-news/electric-power/081726-eu-gas-storage-passes-60-full-but-still-lags-recent-years-gie) "
        "and [oEnergetice](https://oenergetice.cz/en/natural-gas/eu-gas-storage-is-less-than-three-quarters-full-how-much-will-be-left-after-winter).")


if __name__ == "__main__":
    # Run this panel on its own:  python3 -m streamlit run panels/gas_lng.py
    st.set_page_config(page_title="Hormuz Shock – Gas & LNG", layout="wide")
    render()
