from pathlib import Path
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="Hormuz Dashboard",
    layout="wide"
)

st.title("Hormuz: Economic Impact")

st.header("Shipping: traffic collapses, risk gets priced in")

# KPI
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("SHIP TRANSITS PER DAY", "1.0", "-84 vs normal")

with col2:
    st.metric("TANKER TONNAGE", "0.1%")

with col3:
    st.metric("WAR-RISK PREMIUM", "6%")

with col4:
    st.metric("MARITIME INCIDENTS", "130")

st.divider()

left, right = st.columns(2)

# COLONNA SINISTRA
with left:

    st.subheader("85 squares = one normal day of traffic")

    squares = ""

    for i in range(85):
        color = "#cccccc"

        if i == 0:
            color = "#666666"

        squares += f"""
        <div style="
            width:18px;
            height:18px;
            background:{color};
            display:inline-block;
            margin:3px;
            border-radius:2px;
        "></div>
        """

    st.markdown(squares, unsafe_allow_html=True)

    st.markdown("### Recent daily crossings (all ships)")

    shipping_df = pd.DataFrame({
        "Day": ["1","2","3","4","5","6","7","8"],
        "Crossings": [12,10,5,7,7,9,13,5]
    })

    fig1, ax1 = plt.subplots(figsize=(8,4))

    ax1.bar(
        shipping_df["Day"],
        shipping_df["Crossings"]
    )

    ax1.set_xlabel("Day")
    ax1.set_ylabel("Crossings")
    ax1.set_title("Recent Daily Crossings")

    st.pyplot(fig1)

# COLONNA DESTRA
with right:

    st.subheader("War-risk premium (% of hull value)")

    risk_df = pd.DataFrame({
        "Month": ["Feb","Mar","Apr","May","Jun","Jul"],
        "Premium": [0.25,1,2.5,1,1,6]
    })

    fig2, ax2 = plt.subplots(figsize=(8,4))

    ax2.plot(
        risk_df["Month"],
        risk_df["Premium"],
        marker="o"
    )

    ax2.set_xlabel("Month")
    ax2.set_ylabel("Premium %")
    ax2.set_title("War-Risk Premium")

    st.pyplot(fig2)

    st.subheader("Key observations")

    st.write("""
    • Ship traffic is significantly below normal levels.

    • Tanker tonnage remains extremely weak.

    • Insurance costs have risen sharply.

    • Maritime incidents have increased.

    • Shipping companies are avoiding the route where possible.
    """)
       
