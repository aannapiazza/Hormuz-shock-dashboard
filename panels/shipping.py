from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots


st.set_page_config(
    page_title="Hormuz Dashboard",
    page_icon="🚢",
    layout="wide"
)


# STYLE

BLUE = "#60a5fa"
AMBER = "#f59e0b"
GREEN = "#34d399"
PURPLE = "#a78bfa"
TEAL = "#5eead4"
TEXT = "#cbd5e1"
MUTED = "#94a3b8"
GRID = "rgba(148, 163, 184, 0.13)"
PANEL = "#111a2e"

st.markdown(
    """
    <style>
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #111a2e 0%, #0d1424 100%);
        border: 1px solid #1f2a44;
        border-radius: 14px;
        padding: 16px 18px;
    }
    [data-testid="stMetricLabel"] { color: #94a3b8; }
    .stTabs [data-baseweb="tab"] { font-size: 1.02rem; padding: 10px 18px; }
    h1, h2, h3 { letter-spacing: -0.01em; }
    </style>
    """,
    unsafe_allow_html=True
)

# Key events drawn as vertical lines on the charts (optional).
# Add your own as ("YYYY-MM-DD", "Label"), for example:
# EVENTS = [("2026-03-01", "War begins"), ("2026-04-08", "Ceasefire")]
EVENTS = []


def style_figure(fig, height=420, rangeslider=True, buttons=True):
    """Apply the shared dark look to a Plotly figure."""
    fig.update_layout(
        height=height,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, size=13),
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#0b1220",
            bordercolor="#1f2a44",
            font=dict(color="#e2e8f0")
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)"
        ),
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor=GRID,
        zeroline=False,
        showline=False,
        showspikes=True,
        spikecolor=MUTED,
        spikethickness=1,
        spikedash="dot",
        spikemode="across",
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor=GRID,
        zeroline=False,
        showline=False,
    )

    if buttons:
        fig.update_xaxes(
            rangeselector=dict(
                buttons=[
                    dict(count=7, label="1W", step="day", stepmode="backward"),
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(step="all", label="All"),
                ],
                bgcolor=PANEL,
                activecolor="#1d4ed8",
                bordercolor="#1f2a44",
                borderwidth=1,
                font=dict(color=TEXT),
                x=0,
                y=1.16,
            )
        )

    if rangeslider:
        fig.update_xaxes(
            rangeslider=dict(
                visible=True,
                thickness=0.07,
                bgcolor="#0d1424",
                bordercolor="#1f2a44",
                borderwidth=1,
            )
        )

    return fig


def add_events(fig, events):
    """Draw dotted vertical lines with rotated labels for key events."""
    for date, label in events:
        fig.add_shape(
            type="line",
            x0=date, x1=date,
            y0=0, y1=1,
            xref="x", yref="paper",
            line=dict(color=MUTED, width=1, dash="dot"),
            opacity=0.6,
        )
        fig.add_annotation(
            x=date, y=1,
            xref="x", yref="paper",
            text=label,
            textangle=-90,
            showarrow=False,
            xanchor="right",
            yanchor="top",
            font=dict(size=11, color=MUTED),
        )


# SHIPPING DATA

script_folder = Path(__file__).resolve().parent

possible_paths = [
    script_folder / "Daily_Chokepoints_Data.csv",
    script_folder.parent / "Daily_Chokepoints_Data.csv",
]

csv_path = next(
    (path for path in possible_paths if path.is_file()),
    None
)

shipping_df = None

if csv_path is None:
    st.error(
        "Cannot find Daily_Chokepoints_Data.csv. "
        "Place it in the script folder or its parent folder."
    )
else:
    try:
        shipping_df = pd.read_csv(csv_path)
        shipping_df.columns = shipping_df.columns.str.strip()

        shipping_df = shipping_df.loc[
            shipping_df["portname"]
            .astype(str)
            .str.contains("Hormuz", case=False, na=False)
        ].copy()

        required_columns = {"date", "n_total", "n_tanker"}
        missing_columns = required_columns - set(shipping_df.columns)

        if missing_columns:
            st.error(
                "Missing CSV columns: "
                + ", ".join(sorted(missing_columns))
            )
            shipping_df = None
        else:
            shipping_df["date"] = pd.to_datetime(
                shipping_df["date"],
                errors="coerce"
            )

            for column in ["n_total", "n_tanker"]:
                shipping_df[column] = pd.to_numeric(
                    shipping_df[column],
                    errors="coerce"
                )

            shipping_df = (
                shipping_df
                .dropna(subset=["date", "n_total", "n_tanker"])
                .sort_values("date")
                .reset_index(drop=True)
            )

            if shipping_df.empty:
                st.error("The CSV contains no valid shipping records.")
                shipping_df = None
            else:
                shipping_df["ships_7d"] = (
                    shipping_df["n_total"]
                    .rolling(7, min_periods=1)
                    .mean()
                )
                shipping_df["tankers_7d"] = (
                    shipping_df["n_tanker"]
                    .rolling(7, min_periods=1)
                    .mean()
                )

    except Exception as error:
        st.error(f"Cannot read the shipping CSV: {error}")
        shipping_df = None


# LOAD MARKET DATA

@st.cache_data(ttl=300)
def load_market_data(symbol):
    try:
        history = yf.Ticker(symbol).history(period="6mo")

        if history.empty or "Close" not in history.columns:
            return pd.Series(dtype=float)

        closes = history["Close"].dropna()
        closes.index = pd.to_datetime(closes.index).tz_localize(None)
        return closes

    except Exception:
        return pd.Series(dtype=float)


market_symbols = {
    "BRENT": "BZ=F",
    "WTI": "CL=F",
    "VIX": "^VIX",
    "DOLLAR INDEX": "DX-Y.NYB",
}

market_data = {
    label: load_market_data(symbol)
    for label, symbol in market_symbols.items()
}


# CHART BUILDERS

def shipping_figure(df, height=420, rangeslider=True, default_days=90):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["n_total"],
            name="All ships (daily)",
            mode="lines",
            line=dict(color=BLUE, width=1),
            opacity=0.5,
            fill="tozeroy",
            fillcolor="rgba(96, 165, 250, 0.07)",
            hovertemplate="%{y:.0f}",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["n_tanker"],
            name="Tankers (daily)",
            mode="lines",
            line=dict(color=AMBER, width=1),
            opacity=0.5,
            hovertemplate="%{y:.0f}",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["ships_7d"],
            name="All ships · 7-day avg",
            mode="lines",
            line=dict(color=BLUE, width=3, shape="spline", smoothing=0.9),
            hovertemplate="%{y:.1f}",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["tankers_7d"],
            name="Tankers · 7-day avg",
            mode="lines",
            line=dict(color=AMBER, width=3, shape="spline", smoothing=0.9),
            hovertemplate="%{y:.1f}",
        )
    )

    last = df.iloc[-1]
    fig.add_trace(
        go.Scatter(
            x=[last["date"]],
            y=[last["ships_7d"]],
            mode="markers",
            marker=dict(color=BLUE, size=10, line=dict(color="#0b1220", width=2)),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    style_figure(fig, height=height, rangeslider=rangeslider)
    fig.update_yaxes(title_text="Vessels per day", rangemode="tozero")

    start = last["date"] - pd.Timedelta(days=default_days - 1)
    fig.update_xaxes(range=[start, last["date"]])

    if EVENTS:
        add_events(fig, EVENTS)

    return fig


def brent_figure(prices, height=420, rangeslider=True, show_wti=False):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=prices.index,
            y=prices.values,
            name="Brent",
            mode="lines",
            line=dict(color=GREEN, width=3, shape="spline", smoothing=0.6),
            fill="tozeroy",
            fillcolor="rgba(52, 211, 153, 0.08)",
            hovertemplate="$%{y:.2f}",
        )
    )

    if show_wti and not market_data["WTI"].empty:
        wti = market_data["WTI"]
        fig.add_trace(
            go.Scatter(
                x=wti.index,
                y=wti.values,
                name="WTI",
                mode="lines",
                line=dict(color=PURPLE, width=2, shape="spline", smoothing=0.6),
                hovertemplate="$%{y:.2f}",
            )
        )

    average = float(prices.mean())
    fig.add_hline(
        y=average,
        line=dict(color=TEAL, width=1.5, dash="dash"),
        annotation_text=f"6-month average ${average:.2f}",
        annotation_position="bottom right",
        annotation_font=dict(color=TEAL, size=12),
    )

    high_date = prices.idxmax()
    low_date = prices.idxmin()
    last_date = prices.index[-1]

    for date, color, position in [
        (high_date, "#f87171", "top center"),
        (low_date, TEAL, "bottom center"),
        (last_date, GREEN, "top left"),
    ]:
        value = float(prices.loc[date])
        fig.add_trace(
            go.Scatter(
                x=[date],
                y=[value],
                mode="markers+text",
                text=[f"${value:.1f}"],
                textposition=position,
                textfont=dict(color=TEXT, size=12),
                marker=dict(color=color, size=10, line=dict(color="#0b1220", width=2)),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    style_figure(fig, height=height, rangeslider=rangeslider)
    fig.update_yaxes(
        title_text="$ per barrel",
        range=[float(prices.min()) * 0.9, float(prices.max()) * 1.08],
    )

    if EVENTS:
        add_events(fig, EVENTS)

    return fig


def combined_figure(df, prices, height=420):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["tankers_7d"],
            name="Tanker transits · 7-day avg",
            mode="lines",
            line=dict(color=AMBER, width=3, shape="spline", smoothing=0.9),
            fill="tozeroy",
            fillcolor="rgba(245, 158, 11, 0.08)",
            hovertemplate="%{y:.1f}",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=prices.index,
            y=prices.values,
            name="Brent ($/bbl)",
            mode="lines",
            line=dict(color=GREEN, width=3, shape="spline", smoothing=0.6),
            hovertemplate="$%{y:.2f}",
        ),
        secondary_y=True,
    )

    style_figure(fig, height=height, rangeslider=True)
    fig.update_yaxes(title_text="Tankers per day", rangemode="tozero", secondary_y=False)
    fig.update_yaxes(title_text="$ per barrel", showgrid=False, secondary_y=True)

    # Show only the period where both series overlap.
    start = max(df["date"].min(), prices.index.min())
    end = min(df["date"].max(), prices.index.max())
    fig.update_xaxes(range=[start, end])

    if EVENTS:
        add_events(fig, EVENTS)

    return fig


# HEADER

st.title("🚢 Hormuz | Shipping & Markets")

st.caption(
    "Shipping: daily IMF PortWatch data from a local CSV. "
    "Market prices: latest available from Yahoo Finance; may be delayed."
)


# MAIN METRICS

traffic_col, tanker_col, brent_col, wti_col = st.columns(4)

latest_date = None

if shipping_df is not None:
    latest = shipping_df.iloc[-1]
    latest_date = latest["date"]
    previous = shipping_df.iloc[-2] if len(shipping_df) > 1 else latest

    latest_total = int(latest["n_total"])
    latest_tanker = int(latest["n_tanker"])

    with traffic_col:
        st.metric(
            "🚢 Daily ship transits",
            f"{latest_total:,}",
            delta=f"{latest_total - int(previous['n_total']):+d} vs previous day"
        )
        st.caption(f"{latest_date:%d %b %Y}")

    with tanker_col:
        st.metric(
            "🛢️ Daily tanker transits",
            f"{latest_tanker:,}",
            delta=f"{latest_tanker - int(previous['n_tanker']):+d} vs previous day"
        )
        st.caption("Included in total ship transits")

else:
    with traffic_col:
        st.metric("🚢 Daily ship transits", "Unavailable")

    with tanker_col:
        st.metric("🛢️ Daily tanker transits", "Unavailable")


for column, label in [
    (brent_col, "BRENT"),
    (wti_col, "WTI")
]:
    prices = market_data[label]

    with column:
        if prices.empty:
            st.metric(f"{label} futures", "Unavailable")
        else:
            current = float(prices.iloc[-1])
            change = (
                current - float(prices.iloc[-2])
                if len(prices) > 1 else 0.0
            )
            pct = change / float(prices.iloc[-2]) * 100 if len(prices) > 1 else 0.0

            st.metric(
                f"🛢️ {label} futures",
                f"${current:.2f}",
                delta=f"{change:+.2f} ({pct:+.1f}%)",
                delta_color="off"
            )
            st.caption(
                f"USD/barrel · {prices.index[-1]:%d %b %Y}"
            )

st.write("")


# TABS

tab_overview, tab_shipping, tab_markets, tab_data = st.tabs([
    "📊 Overview",
    "🚢 Shipping",
    "🛢️ Markets",
    "🗂️ Data",
])


# OVERVIEW

with tab_overview:
    left, right = st.columns(2, gap="large")

    with left:
        st.subheader("Traffic through Hormuz")
        st.caption("Daily vessel counts · IMF PortWatch")

        if shipping_df is not None:
            st.plotly_chart(
                shipping_figure(
                    shipping_df,
                    height=400,
                    rangeslider=False,
                    default_days=30
                ),
                use_container_width=True,
                theme=None,
                key="overview_shipping"
            )
        else:
            st.info("Shipping data is unavailable.")

    with right:
        st.subheader("Brent futures")
        st.caption("USD per barrel · Yahoo Finance")

        brent_prices = market_data["BRENT"]

        if brent_prices.empty:
            st.info("Brent prices are temporarily unavailable.")
        else:
            st.plotly_chart(
                brent_figure(brent_prices, height=400, rangeslider=False),
                use_container_width=True,
                theme=None,
                key="overview_brent"
            )

    st.divider()

    st.subheader("Tanker traffic vs Brent")
    st.caption(
        "7-day average of tanker transits (left axis) next to Brent (right axis)."
    )

    if shipping_df is not None and not market_data["BRENT"].empty:
        st.plotly_chart(
            combined_figure(shipping_df, market_data["BRENT"]),
            use_container_width=True,
            theme=None,
            key="overview_combined"
        )
    else:
        st.info("Both shipping and Brent data are needed for this chart.")

    st.caption(
        "These charts show traffic and prices side by side; "
        "they do not establish a causal relationship."
    )


# SHIPPING

with tab_shipping:
    st.subheader("Traffic through Hormuz")
    st.caption(
        "Daily vessel counts · IMF PortWatch. "
        "Thin lines are daily values, thick lines are 7-day averages."
    )

    if shipping_df is not None:
        last_30 = shipping_df.loc[
            shipping_df["date"] > latest_date - pd.Timedelta(days=30)
        ]
        prev_30 = shipping_df.loc[
            (shipping_df["date"] <= latest_date - pd.Timedelta(days=30))
            & (shipping_df["date"] > latest_date - pd.Timedelta(days=60))
        ]

        stat1, stat2, stat3 = st.columns(3)

        avg_total = float(last_30["n_total"].mean())
        avg_tanker = float(last_30["n_tanker"].mean())
        tanker_share = (
            float(last_30["n_tanker"].sum()) / float(last_30["n_total"].sum()) * 100
            if float(last_30["n_total"].sum()) > 0 else 0.0
        )

        with stat1:
            delta = None
            if not prev_30.empty:
                delta = f"{avg_total - float(prev_30['n_total'].mean()):+.1f} vs prior 30 days"
            st.metric("30-day avg · all ships", f"{avg_total:.1f}", delta=delta)

        with stat2:
            delta = None
            if not prev_30.empty:
                delta = f"{avg_tanker - float(prev_30['n_tanker'].mean()):+.1f} vs prior 30 days"
            st.metric("30-day avg · tankers", f"{avg_tanker:.1f}", delta=delta)

        with stat3:
            st.metric("Tanker share of transits", f"{tanker_share:.0f}%")
            st.caption("Last 30 days")

        st.plotly_chart(
            shipping_figure(shipping_df, height=460),
            use_container_width=True,
            theme=None,
            key="shipping_tab"
        )

        st.caption(
            f"Latest observation: {latest_date:%d %b %Y}. "
            "Tankers are included in all ships."
        )
    else:
        st.info("Shipping data is unavailable.")


# MARKETS

with tab_markets:
    st.subheader("Oil prices")
    st.caption("USD per barrel · Yahoo Finance · quotes may be delayed")

    brent_prices = market_data["BRENT"]

    if brent_prices.empty:
        st.info("Brent prices are temporarily unavailable.")
    else:
        show_wti = st.toggle("Compare with WTI", value=False, key="toggle_wti")

        st.plotly_chart(
            brent_figure(brent_prices, height=460, show_wti=show_wti),
            use_container_width=True,
            theme=None,
            key="markets_brent"
        )

    st.divider()
    st.subheader("More market indicators")

    vix_col, dollar_col = st.columns(2)

    for column, label in [
        (vix_col, "VIX"),
        (dollar_col, "DOLLAR INDEX")
    ]:
        prices = market_data[label]

        with column:
            if prices.empty:
                st.metric(label, "Unavailable")
            else:
                current = float(prices.iloc[-1])
                change = (
                    current - float(prices.iloc[-2])
                    if len(prices) > 1 else 0.0
                )
                st.metric(
                    label,
                    f"{current:.2f}",
                    delta=f"{change:+.2f}",
                    delta_color="off"
                )
                st.caption(
                    f"Observation: {prices.index[-1]:%d %b %Y}"
                )

                spark = go.Figure(
                    go.Scatter(
                        x=prices.index,
                        y=prices.values,
                        mode="lines",
                        line=dict(color=BLUE, width=2, shape="spline", smoothing=0.6),
                        fill="tozeroy",
                        fillcolor="rgba(96, 165, 250, 0.08)",
                        hovertemplate="%{y:.2f}",
                    )
                )
                style_figure(spark, height=160, rangeslider=False, buttons=False)
                spark.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                spark.update_yaxes(
                    showticklabels=False,
                    range=[float(prices.min()) * 0.95, float(prices.max()) * 1.03],
                )
                st.plotly_chart(
                    spark,
                    use_container_width=True,
                    theme=None,
                    key=f"spark_{label}"
                )


# DATA

with tab_data:
    st.subheader("Shipping data")

    if shipping_df is not None:
        export_df = shipping_df[["date", "n_total", "n_tanker"]].copy()

        st.dataframe(
            export_df.sort_values("date", ascending=False),
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            label="⬇️ Download Hormuz data",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name="hormuz_shipping.csv",
            mime="text/csv",
            key="download_hormuz_shipping"
        )
    else:
        st.info("No shipping data available.")


# SOURCES

st.divider()

st.caption(
    "Sources: IMF PortWatch — Hormuz daily transits; "
    "Yahoo Finance — market prices. "
    "Shipping data updates when the CSV is replaced. "
    "Shipping and market observations may have different dates."
)
