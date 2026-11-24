"""Tests for the Gas & LNG panel (panels/gas_lng.py). They use the saved files in data/, so no internet is needed.
Run from the project folder:  python3 -m pytest -q
"""
import numpy as np
import pandas as pd
import pytest

from panels import gas_lng as gas


@pytest.fixture(scope="module")
def data():
    loaded, _ = gas.load_data(False)          # False = the saved copies, same numbers every time
    return loaded


@pytest.fixture(scope="module")
def table(data):
    return gas.monthly_table(data)


# ---------- conversions and dates ----------
def test_euro_per_mwh_to_dollars_per_mmbtu():
    daily = pd.DataFrame({"ttf_eur_mwh": [10.0, 50.0], "eurusd": [1.1, 1.0]})
    expected = [10 * 1.1 * 0.293071, 50 * 1.0 * 0.293071]      # 1 MMBtu = 0.293071 MWh
    assert gas.ttf_in_usd(daily).tolist() == pytest.approx(expected)


@pytest.mark.parametrize("date, phase", [("2025-12-15", None), ("2026-02-10", "Build-up"),
                                         ("2026-03-15", "War & closure"), ("2026-05-15", "Ceasefire"),
                                         ("2026-10-15", "Conflict resumes")])
def test_each_date_falls_in_the_right_phase(date, phase):
    assert gas.phase_for(pd.Timestamp(date)) == phase


def test_benchmark_rows_map_to_months():
    assert gas.bench_month("Before the war (Feb 2026 avg)") == "2026-02"
    assert gas.bench_month("October 2026 avg") == "2026-10"
    assert gas.bench_month("2022 crisis peak (approx.)") is None


# ---------- the monthly table everything is built on ----------
def test_no_data_after_the_cut_off(data):
    assert data["daily"]["date"].max() <= gas.END
    assert pd.to_datetime(data["prices"]["month"]).max() <= gas.END


def test_one_row_per_month_and_every_month_has_a_phase(table):
    assert table["month"].is_unique
    assert table["phase"].notna().all()


def test_february_is_the_pre_war_reference(table):
    feb = table.set_index("month").loc[gas.PREWAR_MONTH]
    assert feb["vs_prewar"] == pytest.approx(0)
    assert feb["tanker_pct"] == pytest.approx(100)


def test_change_since_the_war_matches_the_prices(table):
    feb, last = table.set_index("month").loc[gas.PREWAR_MONTH], table.iloc[-1]
    assert last["vs_prewar"] == pytest.approx((last["ttf"] / feb["ttf"] - 1) * 100)


def test_europe_pays_more_than_the_us_every_month(table):
    assert (table["ratio"].dropna() > 1).all()


def test_storage_is_a_percentage(data):
    now = gas.storage_now(data["storage"])
    assert 0 <= now["pct"] <= 100
    assert now["gap"] < 0            # below the 5-year average this winter


# ---------- chart helpers ----------
class FakeFigure:
    """Records add_vrect calls, so the shading can be checked without drawing anything."""
    def __init__(self):
        self.bands = []

    def add_vrect(self, **kwargs):
        self.bands.append(kwargs)


def test_phase_shading_covers_whole_months(table):
    fig = FakeFigure()
    gas.shade_months(fig, table, "Ceasefire")
    band = fig.bands[0]
    assert band["x0"] == pd.Timestamp("2026-04-01")
    assert band["x1"] == pd.Timestamp("2026-07-01")


def test_no_shading_when_no_phase_is_picked(table):
    fig = FakeFigure()
    gas.shade_months(fig, table, None)
    assert fig.bands == []


def test_labels_go_under_the_dips():
    assert gas.label_positions([12, 11, 18, 15, 16]) == ["top center", "bottom center", "top center",
                                                         "bottom center", "top center"]


# ---------- price swings (volatility) ----------
def make_daily(prices):
    """A small made-up daily file: TTF prices in €/MWh with EUR/USD fixed at 1."""
    days = pd.bdate_range("2026-01-01", periods=len(prices))
    return pd.DataFrame({"date": days, "ttf_eur_mwh": prices, "eurusd": 1.0, "hh_usd_mmbtu": 3.0})


def test_a_steady_price_has_no_volatility():
    swings = gas.price_swings(make_daily([40.0] * 30))
    assert swings["vol"].dropna().eq(0).all()


def test_daily_change_is_a_log_return_in_percent():
    swings = gas.price_swings(make_daily([40.0, 44.0]))
    assert swings["ret"].iloc[1] == pytest.approx(np.log(44 / 40) * 100)


def test_volatility_is_scaled_to_a_year():
    rng = np.random.default_rng(1)
    prices = 40 * np.exp(np.cumsum(rng.normal(0, 0.02, 60)))       # daily swings of about 2%
    swings = gas.price_swings(make_daily(prices))
    last = swings["ret"].iloc[-gas.VOL_WINDOW:].std() * np.sqrt(gas.TRADING_DAYS)
    assert swings["vol"].iloc[-1] == pytest.approx(last)


def test_the_war_made_the_market_jumpier(data):
    summary = gas.swings_summary(gas.price_swings(data["daily"]))
    assert summary["since"] > summary["before"]
    assert summary["biggest"]["date"].iloc[0] >= pd.Timestamp(gas.WAR_START)   # the biggest jump came after the strikes


def test_every_month_has_a_volatility(table):
    assert table["vol"].notna().all()


def test_download_has_clear_column_names_and_one_row_per_month(table):
    out = gas.download_table(table)
    assert len(out) == len(table)
    assert {"month", "european_gas_usd_per_mmbtu", "lng_tankers", "volatility_pct_a_year"} <= set(out.columns)
