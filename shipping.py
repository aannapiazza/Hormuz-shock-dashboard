import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(
    page_title="Hormuz Dashboard",
    layout="wide"
)

st.header("Shipping: traffic collapses, risk gets priced in")

# KPI

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "SHIP TRANSITS PER DAY",
        "1.0",
        "-84 vs normal"
    )

with col2:
    st.metric(
        "TANKER TONNAGE",
        "0.1%"
    )

with col3:
    st.metric(
        "WAR-RISK PREMIUM",
        "6%"
    )

with col4:
    st.metric(
        "MARITIME INCIDENTS",
        "130"
    )

# LIVE MARKET DATA

brent = yf.Ticker("BZ=F")
brent_price = brent.history(period="1d")["Close"].iloc[-1]

st.metric(
    "BRENT OIL LIVE",
    f"${brent_price:.2f}"
)

col_a, col_b, col_c = st.columns(3)

wti = yf.Ticker("CL=F")
wti_price = wti.history(period="1d")["Close"].iloc[-1]

vix = yf.Ticker("^VIX")
vix_price = vix.history(period="1d")["Close"].iloc[-1]

dxy = yf.Ticker("DX-Y.NYB")
dxy_price = dxy.history(period="1d")["Close"].iloc[-1]

with col_a:
    st.metric("WTI OIL", f"${wti_price:.2f}")

with col_b:
    st.metric("VIX", f"{vix_price:.2f}")

with col_c:
    st.metric("DOLLAR INDEX", f"{dxy_price:.2f}")

st.divider()

left, right = st.columns(2)

# LEFT COLUMN

with left:

    shipping_df = pd.read_csv("portwatch_hormuz.csv")

    shipping_df["date"] = pd.to_datetime(
        shipping_df["date"]
    )

    shipping_df = shipping_df.sort_values("date")

    latest_total = int(
        shipping_df["n_total"].iloc[-1]
    )

    latest_tanker = int(
        shipping_df["n_tanker"].iloc[-1]
    )

    st.metric(
        "Current Daily Traffic",
        latest_total
    )

    st.metric(
        "Tankers",
        latest_tanker
    )

    st.subheader("85 squares = one normal day of traffic")

    active = min(85, latest_total)

    squares = ""

    for i in range(85):

        color = "#1e293b"

        if i < active:
            color = "#f59e0b"

        squares += f"""
        <div style="
            width:18px;
            height:18px;
            background:{color};
            display:inline-block;
            margin:3px;
            border-radius:3px;
        "></div>
        """

    st.markdown(squares, unsafe_allow_html=True)

    st.markdown("### Recent daily crossings (all ships)")

    recent = shipping_df.tail(30)

    st.line_chart(
        recent.set_index("date")["n_total"]
    )

# RIGHT COLUMN

with right:

    st.markdown("### Brent Oil - Last 6 Months")

    show_price = st.toggle(
        "Show latest Brent price",
        value=True
    )

    brent_hist = brent.history(period="6mo")

    st.line_chart(
        brent_hist["Close"]
    )

    if show_price:
        st.success(
            f"Latest Brent Price: ${brent_price:.2f}"
        )

    st.markdown("### Key observations")

    st.write("""
    • Ship traffic is well below normal levels.

    • Tanker tonnage remains extremely low.

    • Insurance costs have increased sharply.

    • Maritime incidents have risen.

    • The route is considered high risk.
    """)
