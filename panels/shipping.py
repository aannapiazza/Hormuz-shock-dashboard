from pathlib import Path
import pandas as pd
import streamlit as st
import yfinance as yf



st.set_page_config(
    page_title="Hormuz Dashboard",
    layout="wide"
)

st.header("Shipping: Strait of Hormuz traffic and market prices")

st.caption(
    "Shipping: daily IMF PortWatch data from a local CSV. "
    "Market prices: latest available from Yahoo Finance; may be delayed."
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
        "Cannot find portwatch_hormuz.csv. "
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

    except Exception as error:
        st.error(f"Cannot read the shipping CSV: {error}")
        shipping_df = None


# MARKET DATA
# Cache downloads for 5 minutes to avoid repeated requests.

@st.cache_data(ttl=300)
def load_market_data(symbol):
    try:
        history = yf.Ticker(symbol).history(period="6mo")

        if history.empty or "Close" not in history.columns:
            return pd.Series(dtype=float)

        return history["Close"].dropna()

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

st.subheader("Latest available market prices")

market_columns = st.columns(4)

for column, (label, prices) in zip(
    market_columns,
    market_data.items()
):
    with column:
        if prices.empty:
            st.metric(label, "Unavailable")
        else:
            latest_price = float(prices.iloc[-1])

            if label in ["BRENT", "WTI"]:
                value = f"${latest_price:.2f}"
            else:
                value = f"{latest_price:.2f}"

            st.metric(label, value)

            st.caption(
                f"Observation: {prices.index[-1]:%d/%m/%Y}"
            )

st.caption(
    "Brent and WTI refer to futures prices. "
    "Prices refresh on the next app rerun after the cache expires."
)

st.divider()

left, right = st.columns(2)


# LEFT COLUMN: SHIPPING

with left:
    st.subheader("Hormuz daily ship transits")

    if shipping_df is not None:
        latest = shipping_df.iloc[-1]

        latest_date = latest["date"]
        latest_total = int(latest["n_total"])
        latest_tanker = int(latest["n_tanker"])

        st.caption(
            f"Latest shipping observation: {latest_date:%d/%m/%Y}. "
            "This CSV does not update automatically."
        )

        total_column, tanker_column = st.columns(2)

        with total_column:
            st.metric("Daily ship transits", latest_total)

        with tanker_column:
            st.metric("Daily tanker transits", latest_tanker)

        st.markdown("### Recent daily crossings")

        start_date = latest_date - pd.Timedelta(days=29)

        recent = shipping_df.loc[
            shipping_df["date"] >= start_date
        ]

        st.line_chart(
            recent.set_index("date")[["n_total", "n_tanker"]]
            .rename(
                columns={
                    "n_total": "All ships",
                    "n_tanker": "Tankers",
                }
            )
        )

        st.caption(
            "Source: IMF PortWatch. "
            "Tanker transits measure vessel counts, not tonnage."
        )

        with st.expander("View shipping data"):
            st.dataframe(
                recent,
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info(
            "Shipping charts will appear once a valid CSV is available."
        )


# RIGHT COLUMN: BRENT

with right:
    st.subheader("Brent futures — last 6 months")

    brent_prices = market_data["BRENT"]

    if brent_prices.empty:
        st.warning(
            "Brent prices are temporarily unavailable from Yahoo Finance."
        )
    else:
        st.line_chart(
            brent_prices.rename("Brent futures (USD/barrel)")
        )

        show_price = st.toggle(
            "Show latest Brent price",
            value=True
        )

        if show_price:
            st.success(
                f"Latest available Brent price: "
                f"${float(brent_prices.iloc[-1]):.2f}"
            )

    st.markdown("### Reading this dashboard")

    st.write(
        "Shipping figures describe the latest date in the CSV. "
        "Market prices may refer to a different date. "
        "These charts alone do not establish that changes in "
        "Hormuz traffic caused changes in oil prices."
    )
