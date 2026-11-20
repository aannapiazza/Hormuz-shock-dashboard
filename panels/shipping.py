import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf


st.set_page_config(
    page_title="Hormuz Dashboard",
    page_icon="🚢",
    layout="wide"
)


# DATA SETTINGS

# Nothing after this date is ever shown or saved.
END = pd.Timestamp("2026-10-31")

# LIVE = False: market prices come from saved copies (downloaded once if missing).
# LIVE = True:  market prices are downloaded fresh from Yahoo Finance.
# Either way, everything is cut at END.
LIVE = False


def up_to_end(data):
    """Drop everything after END (DataFrame with a 'date' column, or a Series
    indexed by date)."""
    if isinstance(data, pd.DataFrame):
        return data.loc[data["date"] <= END].copy()
    return data.loc[data.index <= END]


# STYLE

BLUE = "#60a5fa"
AMBER = "#f59e0b"
GREEN = "#34d399"
TEAL = "#5eead4"
TEXT = "#cbd5e1"
MUTED = "#94a3b8"
GRID = "rgba(148, 163, 184, 0.13)"

# Hide the Plotly toolbar (zoom buttons); dragging on a chart still zooms,
# and double-clicking resets it.
PLOT_CONFIG = {"displayModeBar": False}

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
    h1, h2, h3 { letter-spacing: -0.01em; }
    </style>
    """,
    unsafe_allow_html=True
)

# Key events drawn as vertical lines on the charts (optional).
# Add your own as ("YYYY-MM-DD", "Label"), for example:
# EVENTS = [("2026-03-01", "War begins"), ("2026-04-08", "Ceasefire")]
EVENTS = []


def style_figure(fig, height=380):
    """Apply the shared dark look to a Plotly figure."""
    fig.update_layout(
        height=height,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, size=13),
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#0b1220",
            bordercolor="#1f2a44",
            font=dict(color="#e2e8f0")
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.0,
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
        # Few, short labels so the dates never overlap in a narrow column.
        nticks=5,
        tickformat="%d %b",
        tickangle=0,
        automargin=True,
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
        automargin=True,
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


# HEADER

st.title("🚢 Hormuz | Shipping & Markets")

st.caption(
    "Shipping: daily IMF PortWatch data from a local CSV. "
    "Market prices: Yahoo Finance. "
    f"Data shown up to {END:%d %b %Y}."
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

            # Cut everything after END (the CSV may run further).
            shipping_df = up_to_end(shipping_df).reset_index(drop=True)

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

SAVED_FOLDER = script_folder / "saved_market_data"


def saved_path(symbol):
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", symbol).strip("_")
    return SAVED_FOLDER / f"{safe_name}.csv"


@st.cache_data(ttl=300)
def load_market_data(symbol, live):
    path = saved_path(symbol)

    # Saved copy first (cut again at END, just in case).
    if not live and path.is_file():
        try:
            saved = pd.read_csv(path, index_col=0, parse_dates=True)["Close"]
            return up_to_end(saved.dropna())
        except Exception:
            pass

    # Otherwise download, cut at END, and save the copy.
    try:
        history = yf.Ticker(symbol).history(
            start=END - pd.DateOffset(months=6),
            end=END + pd.Timedelta(days=1)  # Yahoo's end date is exclusive
        )

        if history.empty or "Close" not in history.columns:
            return pd.Series(dtype=float)

        closes = history["Close"].dropna()
        closes.index = pd.to_datetime(closes.index).tz_localize(None)
        closes.index.name = "Date"
        closes = up_to_end(closes)

        try:
            SAVED_FOLDER.mkdir(exist_ok=True)
            closes.rename("Close").to_csv(path)
        except Exception:
            pass  # saving is best effort

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
    label: load_market_data(symbol, LIVE)
    for label, symbol in market_symbols.items()
}


# CHART BUILDERS

def shipping_figure(df, height=380):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["n_total"],
            name="All ships",
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
            name="Tankers",
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

    style_figure(fig, height=height)
    fig.update_yaxes(title_text="Vessels per day", rangemode="tozero")

    if EVENTS:
        add_events(fig, EVENTS)

    return fig


def brent_figure(prices, height=380):
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

    average = float(prices.mean())
    fig.add_hline(
        y=average,
        line=dict(color=TEAL, width=1.5, dash="dash"),
        annotation_text=f"Average ${average:.2f}",
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

    style_figure(fig, height=height)
    fig.update_yaxes(
        title_text="$ per barrel",
        range=[float(prices.min()) * 0.9, float(prices.max()) * 1.08],
    )

    if EVENTS:
        add_events(fig, EVENTS)

    return fig


# MAIN METRICS

st.divider()

traffic_col, tanker_col, brent_col, wti_col = st.columns(4)

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
            pct = (
                change / float(prices.iloc[-2]) * 100
                if len(prices) > 1 else 0.0
            )

            st.metric(
                f"🛢️ {label} futures",
                f"${current:.2f}",
                delta=f"{change:+.2f} ({pct:+.1f}%)",
                delta_color="off"
            )
            st.caption(
                f"USD/barrel · {prices.index[-1]:%d %b %Y}"
            )


st.divider()


# CHARTS

left, right = st.columns(2, gap="large")


with left:
    st.subheader("Traffic through Hormuz")
    st.caption("Daily vessel counts · IMF PortWatch")

    if shipping_df is not None:
        period = st.selectbox(
            "Shipping history",
            [30, 90, 180, 365],
            format_func=lambda days: f"Last {days} days",
            key="shipping_history_period"
        )

        start_date = latest_date - pd.Timedelta(
            days=period - 1
        )

        recent = shipping_df.loc[
            shipping_df["date"] >= start_date
        ].copy()

        st.plotly_chart(
            shipping_figure(recent),
            use_container_width=True,
            theme=None,
            config=PLOT_CONFIG,
            key="shipping_chart"
        )

        st.caption(
            f"Latest observation: {latest_date:%d %b %Y}. "
            "Tankers are included in all ships. "
            "Thin lines are daily values, thick lines are 7-day averages."
        )

    else:
        st.info("Shipping data is unavailable.")


with right:
    st.subheader("Brent futures")
    st.caption("USD per barrel · Yahoo Finance")

    months = st.selectbox(
        "Price history",
        [1, 3, 6],
        format_func=lambda value: f"Last {value} months",
        index=2,
        key="shipping_brent_period"
    )

    brent_prices = market_data["BRENT"]

    if brent_prices.empty:
        st.info("Brent prices are temporarily unavailable.")
    else:
        cutoff = (
            brent_prices.index.max()
            - pd.DateOffset(months=months)
        )

        selected_prices = brent_prices.loc[
            brent_prices.index >= cutoff
        ]

        st.plotly_chart(
            brent_figure(selected_prices),
            use_container_width=True,
            theme=None,
            config=PLOT_CONFIG,
            key="brent_chart"
        )

        st.caption(
            "Latest available daily prices; "
            "quotes may be delayed."
        )


# ADDITIONAL MARKET INDICATORS

with st.expander("More market indicators"):
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
                st.metric(
                    label,
                    f"{float(prices.iloc[-1]):.2f}"
                )
                st.caption(
                    f"Observation: "
                    f"{prices.index[-1]:%d %b %Y}"
                )


# DATA AND SOURCES

st.divider()

with st.expander("Shipping data and download"):
    if shipping_df is not None:
        export_df = shipping_df[["date", "n_total", "n_tanker"]].copy()

        st.dataframe(
            export_df.sort_values(
                "date",
                ascending=False
            ),
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            label="Download Hormuz data",
            data=export_df.to_csv(
                index=False
            ).encode("utf-8"),
            file_name="hormuz_shipping.csv",
            mime="text/csv",
            key="download_hormuz_shipping"
        )
    else:
        st.info("No shipping data available.")


st.caption(
    "Sources: IMF PortWatch — Hormuz daily transits; "
    "Yahoo Finance — market prices. "
    "Shipping data updates when the CSV is replaced. "
    "Shipping and market observations may have different dates."
)

st.caption(
    "These charts show traffic and prices separately; "
    "they do not establish a causal relationship."
)

