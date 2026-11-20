from pathlib import Path
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
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
    brent = yf.Ticker("BZ=F")

brent_price = brent.history(period="1d")["Close"].iloc[-1]

st.metric(
    "BRENT OIL LIVE",
    f"${brent_price:.2f}"
)
...
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
st.divider()


left, right = st.columns(2)

# COLONNA SINISTRA
with left:

  st.subheader("85 squares = one normal day of traffic")

active = st.slider(
    "Current crossings",
    min_value=0,
    max_value=85,
    value=1
)

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

period = st.selectbox(
    "Period",
    ["Last 8 days", "Last 30 days"]
)

shipping_df = pd.DataFrame({
    "Day": ["1","2","3","4","5","6","7","8"],
    "Crossings": [12,10,5,7,7,9,13,5]
})

st.bar_chart(
    shipping_df.set_index("Day")
)


# COLONNA DESTRA
with right:

    st.markdown("### War-risk premium")

    show_peak = st.toggle(
        "Show peak value",
        value=True
    )

   st.markdown("### Brent Oil - Last 6 Months")

brent_hist = brent.history(period="6mo")

st.line_chart(
    brent_hist["Close"]
)

    if show_peak:
        st.success("Peak premium reached: 6%")

    st.markdown("### Key observations")

    st.write("""
    • Ship traffic is well below normal levels.

    • Tanker tonnage remains extremely low.

    • Insurance costs have increased sharply.

    • Maritime incidents have risen.

    • The route is considered high risk.
    """)
    

       
