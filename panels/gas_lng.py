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

DATA_AS_OF = "Data as of 15 November 2026 · monthly prices to October 2026"

# --- 1. Dumbbell: monthly averages vs 2022 ---
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


HORMUZ_BCM, HORMUZ_SHARE = 110, 0.20  # LNG via Hormuz per year (2025), share of world LNG trade


# ======================================================================
# CHART HELPERS
# ======================================================================
def _layout(fig, **kw):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color=INK, size=13),
        hoverlabel=dict(bgcolor=DARK, bordercolor="#26354f"), **kw)
    return fig


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
                   yaxis=dict(autorange="reversed", fixedrange=True), legend=dict(orientation="h", y=-0.22, x=0))


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
    k1.metric("Qatari LNG capacity offline", "16–17%", delta="for about 4 years", delta_color="off",
              help="After the 19 March strike on Ras Laffan. This damage lasts even if the strait reopens. Sources: S&P Global, IEA.")
    k2.metric("Hormuz LNG tankers, Oct", "31", delta="≈ a third of pre-war", delta_color="off",
              help="Laden LNG tankers exiting in October, the most since the war began (pre-war ≈ 85 a month). Source: S&P Global.")
    k3.metric("Asian LNG (JKM), Oct avg", "$28.59", delta="+164% vs Feb", delta_color="inverse",
              help="Per MMBtu, near-month, October average vs $10.82 in February. Source: EIA, citing Bloomberg.")
    k4.metric("EU gas storage, 15 Nov", "70.4%", delta="−18 pts vs 5-yr avg", delta_color="normal",
              help="Lowest for the date since records began in 2011. Source: GIE data, via TASS.")

    tab1, tab2 = st.tabs(["📈 Prices", "🚢 Supply & shipping"])

    # ================= TAB 1: PRICES =================
    with tab1:
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
        st.subheader("Where the world's LNG comes from, and where Hormuz LNG goes")
        st.caption("Click a segment to zoom in, and click the centre to zoom back out. EIA estimates for 2024.")
        st.plotly_chart(sunburst_chart(), width="stretch", theme=None, config=CFG)

        st.subheader("LNG supply-gap calculator")
        c1, c2 = st.columns([1, 1.3])
        with c1:
            blocked = st.slider("Share of Hormuz LNG blocked (%)", 0, 100, 70, key="gas_blk") / 100
            months = st.slider("Months of disruption", 1, 24, 8, key="gas_mo")
            st.caption(f"Uses {HORMUZ_BCM} bcm a year through Hormuz, about 20% of world LNG trade "
                       f"(so world trade ≈ {HORMUZ_BCM / HORMUZ_SHARE:.0f} bcm).")
        with c2:
            lost = HORMUZ_BCM * blocked * months / 12
            st.metric("LNG lost", f"{lost:.0f} bcm",
                      help="For comparison, the IEA estimated more than 50 bcm of Gulf LNG lost from March to August.")
            st.write(f"That's **{blocked * 20:.0f}%** of world LNG trade cut off while it lasts, "
                     f"or about **{HORMUZ_BCM * blocked / 12:.1f} bcm a month**.")
            st.progress(min(1.0, lost / HORMUZ_BCM), text="Scale: one full year of Hormuz LNG (110 bcm)")

    # ---- Takeaway + sources ----
    st.success("**Takeaway:** gas prices are at their highest since 2022: TTF and JKM both averaged about $28.5/MMBtu "
               "in October, still well below the 2022 peak. LNG traffic through Hormuz is only slowly recovering.")
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
