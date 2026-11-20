from pathlib import Path
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

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

    risk_df = pd.DataFrame({
        "Month":["Feb","Mar","Apr","May","Jun","Jul"],
        "Premium":[0.25,1,2.5,1,1,6]
    })

    st.line_chart(
        risk_df.set_index("Month")
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
    

       
