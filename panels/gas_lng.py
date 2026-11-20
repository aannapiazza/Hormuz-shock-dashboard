"""
Panel 3 - Gas & LNG
Author: Eabha Kelly

Run on its own:  python3 -m streamlit run panels/gas_lng.py
Use in app.py:   from panels import gas_lng   then   gas_lng.render()
"""
import plotly.graph_objects as go
import streamlit as st

# ---------- colours (same as the design) ----------
RED, AMBER, TEAL, BLUE, VIOLET, MUTED = "#ff5a4e", "#ffb020", "#2dd4bf", "#5aa9ff", "#a78bfa", "#8fa0bb"
GRID, INK = "#22314a", "#e8edf5"

# ---------- data (from the design's sources: EIA, IEA, Platts, S&P Global) ----------
ROWS = ["Before the war (late Feb 2026)", "Mar–Aug 2026 average", "2026 peak", "2022 crisis peak"]
TTF = [11, 17.3, 21, 90]     # Europe, $/MMBtu
JKM = [11, 19, 25.9, 70]     # Asia, $/MMBtu
USD_PER_EUR_MWH = 0.346      # 1 €/MWh ≈ 0.346 $/MMBtu (approximate FX)
ROW_NOTES = [
    "Both benchmarks were around $11/MMBtu just before the 28 February strikes.",
    "Six-month average after Qatari exports were cut off. Asia paid a small premium, because most Hormuz LNG normally goes there.",
    "JKM hit $25.9 on 2 September. TTF peaked around $21, and in mid-October it reached its highest level since December 2022.",
    "For comparison: after Russia invaded Ukraine, TTF hit about $90 and Europe paid far more than Asia. That is the reverse of 2026.",
]
SUN_NOTES = {
    "Via Hormuz (~20%)": "About a fifth of world LNG has to leave the Gulf through the strait. There is no pipeline bypass for LNG, unlike oil.",
    "Not via Hormuz (~80%)": "Mainly the US, Australia, Russia and Africa. These suppliers are now the swing source that Europe and Asia are bidding for.",
    "To Asia (83% of Hormuz LNG)": "China, India, Japan, South Korea, Pakistan and others. This is why JKM rose more than TTF.",
    "Europe & other (17%)": "Europe is hit less directly, but it pays through competition for US cargoes.",
}
HORMUZ_BCM = 110             # LNG through Hormuz per year (2025)
HORMUZ_SHARE = 0.20          # share of world LNG trade


def _layout(fig, **kw):
    """Dark, transparent layout shared by both charts."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color=INK, size=13),
        hoverlabel=dict(bgcolor="#0b1320", bordercolor="#26354f"),
        **kw,
    )
    return fig


def _convert(values, unit):
    if unit == "€/MWh":
        return [v / USD_PER_EUR_MWH for v in values]
    if unit == "% vs pre-war":
        return [(v / values[0] - 1) * 100 for v in values]
    return list(values)


def _selected_row():
    """Read which row was clicked last time (Streamlit stores chart selections in session_state)."""
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
    for i, row in enumerate(ROWS):  # grey connector bars
        fig.add_trace(go.Scatter(
            x=[ttf[i], jkm[i]], y=[row, row], mode="lines", hoverinfo="skip", showlegend=False,
            line=dict(color=MUTED if i == highlight else "#33445f", width=9 if i == highlight else 6)))
    opac = [1 if highlight is None or i == highlight else 0.35 for i in range(len(ROWS))]
    fmt = "%{x:+.0f}%" if unit == "% vs pre-war" else "%{x:.1f} " + unit
    fig.add_trace(go.Scatter(x=ttf, y=ROWS, mode="markers", name="Europe (TTF)",
                             marker=dict(size=16, color=BLUE, opacity=opac, line=dict(color="#0b1320", width=2)),
                             hovertemplate="TTF: " + fmt + "<extra></extra>"))
    fig.add_trace(go.Scatter(x=jkm, y=ROWS, mode="markers", name="Asia (JKM)",
                             marker=dict(size=16, color=VIOLET, symbol="diamond", opacity=opac,
                                         line=dict(color="#0b1320", width=2)),
                             hovertemplate="JKM: " + fmt + "<extra></extra>"))
    if unit != "% vs pre-war":  # pre-war dots overlap, so say so
        fig.add_annotation(x=ttf[0], y=ROWS[0], text=f"TTF & JKM both ≈{ttf[0]:.0f}", showarrow=False,
                           xanchor="left", xshift=16, font=dict(size=11, color=MUTED))
    fig.add_shape(type="rect", xref="paper", yref="y", x0=0, x1=1, y0=2.5, y1=3.5,
                  fillcolor="rgba(255,255,255,.03)", line_width=0)
    return _layout(fig, height=400, margin=dict(l=10, r=20, t=10, b=60),
                   xaxis=dict(title=unit, gridcolor=GRID, rangemode="tozero",
                              ticksuffix="%" if unit == "% vs pre-war" else ""),
                   yaxis=dict(autorange="reversed", fixedrange=True),
                   legend=dict(orientation="h", y=-0.2, x=0), clickmode="event+select")


def sunburst_chart():
    fig = go.Figure(go.Sunburst(
        ids=["all", "hz", "nh", "asia", "oth"],
        labels=["World LNG trade", "Via Hormuz<br>~20%", "Not via Hormuz<br>~80%", "To Asia<br>83%", "Europe &<br>other 17%"],
        parents=["", "all", "all", "hz", "hz"],
        values=[100, 20, 80, 16.6, 3.4], branchvalues="total",
        marker=dict(colors=["#18243a", RED, "#2a3a57", BLUE, MUTED], line=dict(color="#0b1320", width=2)),
        textfont=dict(size=13, color=INK), insidetextorientation="horizontal",
        hovertemplate="<b>%{label}</b><br>%{value:.1f}% of world LNG trade<extra></extra>",
    ))
    return _layout(fig, height=400, margin=dict(l=4, r=4, t=4, b=4), uniformtext=dict(minsize=10, mode="show"))


def render() -> None:
    """Draw the whole panel. app.py calls this inside the panel's tab."""
    st.header("🔥 Gas & LNG: Qatar's exports cut off")
    st.caption("Nearly all of Qatar's LNG, about a fifth of world supply, has to pass through Hormuz. "
               "Then the 19 March strike on Ras Laffan knocked out part of its capacity for years.")

    # ---- 1. KPI tiles (hover the ⓘ for the source) ----
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Global LNG via Hormuz", "~20%", help="≈81 Mt (110 bcm) in 2025, mostly Qatar. Source: EIA.")
    k2.metric("Qatari capacity offline", "16–17%",
              help="After the 19 March Ras Laffan attack, for about 4 years. Sources: S&P Global, IEA.")
    k3.metric("Asian LNG (JKM) peak", "$25.9", delta="+135% vs pre-war ~$11", delta_color="inverse",
              help="Per MMBtu, 2 September. Source: Platts.")
    k4.metric("Lost Gulf LNG, Mar–Aug", ">50 bcm",
              help="Year on year: more than 80% of Italy's annual gas use. Source: IEA.")

    left, right = st.columns([3, 2])

    # ---- 2. Dumbbell chart: unit switch + click a row ----
    with left:
        st.subheader("How big is this gas shock? 2026 vs 2022")
        unit = st.radio("Units", ["$/MMBtu", "€/MWh", "% vs pre-war"], horizontal=True, key="gas_unit")
        row = _selected_row()
        st.plotly_chart(dumbbell_chart(unit, row), width="stretch", theme=None,
                        on_select="rerun", selection_mode="points", key="gas_dumb",
                        config={"displayModeBar": False})
        if row is None:
            st.caption("👆 Click a dot to compare Europe and Asia at that moment.")
        else:
            gap = JKM[row] - TTF[row]
            who = "Asia paid more" if gap > 0 else "Europe paid more" if gap < 0 else "No gap"
            st.info(f"**{ROWS[row]}**: TTF ${TTF[row]}/MMBtu · JKM ${JKM[row]}/MMBtu · **{who}**"
                    f"{f' (${abs(gap):.1f})' if gap else ''}\n\n{ROW_NOTES[row]}")

    # ---- 3. Sunburst: click to zoom (built into Plotly) ----
    with right:
        st.subheader("Where the world's LNG comes from, and where Hormuz LNG goes")
        st.caption("Click a segment to zoom in, and click the centre to zoom back out. Shares are EIA estimates for 2024.")
        st.plotly_chart(sunburst_chart(), width="stretch", theme=None, config={"displayModeBar": False})
        seg = st.selectbox("Explain a segment", list(SUN_NOTES), key="gas_seg")
        st.caption(SUN_NOTES[seg])

    # ---- 4. Calculator ----
    st.subheader("LNG supply-gap calculator")
    c1, c2 = st.columns([1, 1.3])
    with c1:
        blocked = st.slider("Share of Hormuz LNG blocked (%)", 0, 100, 90, key="gas_blk") / 100
        months = st.slider("Months of disruption", 1, 24, 6, key="gas_mo")
        st.caption(f"Uses {HORMUZ_BCM} bcm a year through Hormuz, about 20% of world LNG trade "
                   f"(so world trade ≈ {HORMUZ_BCM / HORMUZ_SHARE:.0f} bcm).")
    with c2:
        lost = HORMUZ_BCM * blocked * months / 12
        st.metric("LNG lost", f"{lost:.0f} bcm",
                  help="For comparison, the IEA estimated more than 50 bcm actually lost from March to August.")
        st.write(f"That's **{blocked * 20:.0f}%** of world LNG trade cut off while it lasts, "
                 f"or about **{HORMUZ_BCM * blocked / 12:.1f} bcm a month**.")
        st.progress(min(1.0, lost / HORMUZ_BCM), text="Scale: one full year of Hormuz LNG (110 bcm)")

    # ---- 5. Takeaway + sources ----
    st.success("**Takeaway:** the gas shock is serious but much smaller than 2022. TTF peaked around $21/MMBtu, "
               "against about $90 after Russia invaded Ukraine. Analysts put the milder reaction down to faster "
               "policy responses in Asia and softer European demand. The pain is lasting longer, though. TTF hit "
               "its highest level since December 2022 in mid-October, and Europe and Asia are now bidding against "
               "each other for US cargoes. Hormuz LNG traffic is only creeping back: 31 tankers in October, the "
               "most since February.")
    st.caption("Sources: EIA Short-Term Energy Outlooks and Today in Energy; IEA gas market analysis (Mar–Aug 2026); "
               "S&P Global LNG outlook; Platts JKM.")


# Lets you run this file on its own with `streamlit run gas_lng.py`
if __name__ == "__main__":
    # Run this panel on its own:  python3 -m streamlit run panels/gas_lng.py
    st.set_page_config(page_title="Hormuz Shock – Gas & LNG", layout="wide")
    render()
