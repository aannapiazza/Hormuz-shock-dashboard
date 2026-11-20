from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf


# DATA LOADING

def load_shipping_data():
    script_folder = Path(__file__).resolve().parent

    possible_paths = [
        script_folder / "Daily_Chokepoints_Data.csv",
        script_folder.parent / "Daily_Chokepoints_Data.csv",
        script_folder.parent / "data" / "Daily_Chokepoints_Data.csv",
    ]

    csv_path = next(
        (path for path in possible_paths if path.is_file()),
        None,
    )

    if csv_path is None:
        raise FileNotFoundError(
            "Cannot find Daily_Chokepoints_Data.csv. "
            "Place it in the panel folder, the project root "
            "or the project's data folder."
        )

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    required_columns = {
        "portname",
        "date",
        "n_total",
        "n_tanker",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            "Missing CSV columns: "
            + ", ".join(sorted(missing_columns))
        )

    df = df.loc[
        df["portname"]
        .astype("string")
        .str.contains("Hormuz", case=False, na=False)
    ].copy()

    if df.empty:
        raise ValueError(
            "No Hormuz records were found in the CSV."
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
        utc=True,
    ).dt.tz_convert(None).dt.normalize()

    for column in ["n_total", "n_tanker"]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = (
        df.dropna(subset=["date", "n_total", "n_tanker"])
        .sort_values("date")
        .reset_index(drop=True)
    )

    if df.empty:
        raise ValueError(
            "The CSV contains no valid Hormuz shipping records."
        )

    if df["date"].duplicated().any():
        raise ValueError(
            "Multiple Hormuz records were found for the same date. "
            "Check the CSV before calculating daily totals."
        )

    invalid_counts = (
        (df["n_total"] < 0)
        | (df["n_tanker"] < 0)
        | (df["n_tanker"] > df["n_total"])
        | (df["n_total"] % 1 != 0)
        | (df["n_tanker"] % 1 != 0)
    )

    if invalid_counts.any():
        raise ValueError(
            "Invalid vessel counts in the CSV. Counts must be "
            "non-negative whole numbers, and tankers cannot "
            "exceed total vessels."
        )

    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_market_data(symbol):
    history = yf.Ticker(symbol).history(period="6mo")

    if history.empty or "Close" not in history.columns:
        return pd.Series(dtype=float)

    prices = pd.to_numeric(
        history["Close"],
        errors="coerce",
    ).dropna()

    prices = prices.loc[np.isfinite(prices.to_numpy())]

    return prices.sort_index()


# NUMPY CALCULATIONS

def percentage_change(prices):
    """Percentage change between the last two observations."""
    if len(prices) < 2:
        return None

    values = prices.iloc[-2:].to_numpy(dtype=float)

    if not np.all(np.isfinite(values)) or values[0] <= 0:
        return None

    return float(np.diff(values)[0] / values[0] * 100)


# PANEL

def render():
    st.header("🚢 Hormuz | Shipping & Markets")

    st.caption(
        "Shipping: daily IMF PortWatch data from a local CSV. "
        "Markets: latest available daily observations retrieved "
        "from Yahoo Finance; quotes may be delayed."
    )

    shipping_df = None

    try:
        shipping_df = load_shipping_data()
    except Exception as error:
        st.error(f"Shipping data unavailable: {error}")

    market_symbols = {
        "BRENT": "BZ=F",
        "WTI": "CL=F",
        "VIX": "^VIX",
        "DOLLAR INDEX": "DX-Y.NYB",
    }

    market_data = {}
    market_errors = []

    with st.spinner("Loading market data..."):
        for label, symbol in market_symbols.items():
            try:
                market_data[label] = load_market_data(symbol)
            except Exception:
                market_data[label] = pd.Series(dtype=float)

            if market_data[label].empty:
                market_errors.append(label)

    if market_errors:
        st.warning(
            "Market data could not be retrieved for: "
            + ", ".join(market_errors)
            + "."
        )

    # MAIN METRICS

    st.divider()

    traffic_col, tanker_col, brent_col, wti_col = st.columns(4)

    if shipping_df is not None:
        latest = shipping_df.iloc[-1]
        latest_date = latest["date"]

        previous = (
            shipping_df.iloc[-2]
            if len(shipping_df) >= 2
            else None
        )

        # Only describe changes as daily when dates are consecutive.
        consecutive_days = (
            previous is not None
            and latest_date - previous["date"] == pd.Timedelta(days=1)
        )

        total_delta = None
        tanker_delta = None

        if consecutive_days:
            total_delta = (
                f"{int(latest['n_total'] - previous['n_total']):+d}"
                " vs previous day"
            )
            tanker_delta = (
                f"{int(latest['n_tanker'] - previous['n_tanker']):+d}"
                " vs previous day"
            )

        with traffic_col:
            st.metric(
                "Ship transits",
                f"{int(latest['n_total']):,}",
                delta=total_delta,
                delta_color="off",
            )
            st.caption(f"{latest_date:%d %b %Y}")

        with tanker_col:
            st.metric(
                "Tanker transits",
                f"{int(latest['n_tanker']):,}",
                delta=tanker_delta,
                delta_color="off",
            )
            st.caption(
                f"{latest_date:%d %b %Y} · Included in total"
            )

    else:
        with traffic_col:
            st.metric("Ship transits", "Unavailable")

        with tanker_col:
            st.metric("Tanker transits", "Unavailable")

    for column, label in [
        (brent_col, "BRENT"),
        (wti_col, "WTI"),
    ]:
        prices = market_data[label]

        with column:
            if prices.empty:
                st.metric(f"{label} futures", "Unavailable")
            else:
                change = percentage_change(prices)

                st.metric(
                    f"{label} futures",
                    f"${float(prices.iloc[-1]):.2f}",
                    delta=(
                        f"{change:+.2f}%"
                        if change is not None
                        else None
                    ),
                    delta_color="off",
                )

                st.caption(
                    f"USD/barrel · {prices.index[-1]:%d %b %Y}"
                )

    st.caption(
        "Market percentage changes compare the last two "
        "available observations."
    )

    # CHARTS

    st.divider()

    left, right = st.columns(2, gap="large")

    with left:
        st.subheader("Traffic through Hormuz")
        st.caption("Daily vessel counts · IMF PortWatch")

        if shipping_df is None:
            st.info("Shipping data is unavailable.")
        else:
            period = st.selectbox(
                "Shipping history",
                [30, 90, 180, 365],
                index=3,
                format_func=lambda days: f"Last {days} days",
                key="shipping_history_period",
            )

            latest_date = shipping_df["date"].max()
            start_date = latest_date - pd.Timedelta(
                days=period - 1
            )

            daily = (
                shipping_df
                .set_index("date")[["n_total", "n_tanker"]]
                .rename(
                    columns={
                        "n_total": "All ships",
                        "n_tanker": "Tankers",
                    }
                )
                .asfreq("D")
            )

            # Compute averages before filtering the visible period.
            # Missing observations remain missing, rather than zero.
            averages = (
                daily.rolling(window=7, min_periods=7)
                .mean()
                .rename(
                    columns={
                        "All ships": "All ships · 7-day average",
                        "Tankers": "Tankers · 7-day average",
                    }
                )
            )

            chart_data = daily.join(averages)
            chart_data = chart_data.loc[
                chart_data.index >= start_date
            ]

            st.line_chart(
                chart_data,
                color=[
                    "#2563eb",
                    "#d97706",
                    "#0891b2",
                    "#9333ea",
                ],
                height=350,
                use_container_width=True,
            )

            st.caption(
                f"Latest observation: {latest_date:%d %b %Y}. "
                "Tankers are included in all ships. "
                "Each average requires seven consecutive "
                "daily observations."
            )

    with right:
        st.subheader("Brent futures")
        st.caption("USD per barrel · Yahoo Finance")

        months = st.selectbox(
            "Price history",
            [1, 3, 6],
            index=2,
            format_func=lambda value: f"Last {value} months",
            key="shipping_brent_period",
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

            st.line_chart(
                selected_prices.rename("Brent"),
                color="#059669",
                height=350,
                use_container_width=True,
            )

            st.caption(
                f"Last returned observation: "
                f"{brent_prices.index[-1]:%d %b %Y}. "
                "Daily observations; quotes may be delayed."
            )

    # ADDITIONAL MARKET INDICATORS

    with st.expander("More market indicators"):
        vix_col, dollar_col = st.columns(2)

        for column, label in [
            (vix_col, "VIX"),
            (dollar_col, "DOLLAR INDEX"),
        ]:
            prices = market_data[label]

            with column:
                if prices.empty:
                    st.metric(label, "Unavailable")
                else:
                    change = percentage_change(prices)

                    st.metric(
                        label,
                        f"{float(prices.iloc[-1]):.2f}",
                        delta=(
                            f"{change:+.2f}%"
                            if change is not None
                            else None
                        ),
                        delta_color="off",
                    )

                    st.caption(
                        f"Observation: "
                        f"{prices.index[-1]:%d %b %Y}"
                    )

        st.caption(
            "VIX measures expected US equity market volatility. "
            "The Dollar Index tracks the US dollar against "
            "a basket of currencies."
        )

    # DATA AND SOURCES

    st.divider()

    with st.expander("Shipping data and download"):
        if shipping_df is None:
            st.info("No shipping data available.")
        else:
            st.dataframe(
                shipping_df.sort_values(
                    "date",
                    ascending=False,
                ),
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                label="Download Hormuz data",
                data=shipping_df.to_csv(
                    index=False
                ).encode("utf-8"),
                file_name="hormuz_shipping.csv",
                mime="text/csv",
                key="download_hormuz_shipping",
            )

    st.caption(
        "Sources: IMF PortWatch — Hormuz daily transits; "
        "Yahoo Finance — market prices. "
        "Shipping data updates when the CSV is replaced. "
        "Market requests are cached for five minutes and "
        "run when the app executes. "
        "Shipping and market observations may have different dates."
    )

    st.caption(
        "These charts show traffic and prices separately; "
        "they do not establish a causal relationship."
    )


# Allows this file to run independently.
# When imported by app.py, the main dashboard calls render().
if __name__ == "__main__":
    st.set_page_config(
        page_title="Hormuz | Shipping & Markets",
        layout="wide",
    )
    render()
