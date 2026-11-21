"""Tests for the inflation panel, using made-up data (no internet needed).
Run:  python3 -m pytest -q
"""
import numpy as np
import pandas as pd
import pytest

from panels import inflation as inf

DATES = pd.date_range("2018-01-01", "2026-10-01", freq="MS")


@pytest.fixture
def oil():
    rng = np.random.default_rng(0)
    usd = 70 + np.cumsum(rng.normal(0, 4, len(DATES)))
    return pd.DataFrame({"USD": usd, "EUR": usd / 1.1}, index=DATES)


def test_passthrough_finds_the_lag_and_slope_it_was_built_with(oil):
    change = inf.oil_change_yoy(oil, "EUR")
    energy = (0.4 * change.shift(2)).dropna()          # answer built in: 2 months, slope 0.4
    model = inf.fit_passthrough(energy, change)
    assert model["lag"] == 2
    assert model["slope"] == pytest.approx(0.4)
    assert model["r2"] == pytest.approx(1.0)


def test_scenario_with_no_oil_change():
    model = {"intercept": 1.0, "slope": 0.4}
    r = inf.household_scenario(model, 100, 100, energy_now=5, headline_now=3,
                               energy_weight=10, monthly_bill=200)
    assert r["oil_change"] == 0
    assert r["energy"] == pytest.approx(1.0)
    assert r["headline"] == pytest.approx(3 + 0.1 * (1 - 5))
    assert r["extra_per_month"] == pytest.approx(2.0)


def test_higher_oil_means_higher_inflation():
    model = {"intercept": 0.0, "slope": 0.4}
    low = inf.household_scenario(model, 100, 80, 5, 3, 10, 200)
    high = inf.household_scenario(model, 100, 150, 5, 3, 10, 200)
    assert high["headline"] > low["headline"] and high["extra_per_month"] > 0


def test_change_since_war():
    s = pd.Series([2.0, 2.5, 4.0], index=pd.to_datetime(["2026-01-01", "2026-02-01", "2026-09-01"]))
    latest, change = inf.change_since_war(s)
    assert latest == 4.0 and change == pytest.approx(1.5)
    assert inf.change_since_war(s[s.index < "2026-03-01"]) is None     # nothing after the war yet


def test_jsonstat_to_frame():
    j = {"id": ["geo", "time"], "size": [2, 2],
         "dimension": {"geo": {"category": {"index": {"IE": 0, "EA": 1}}},
                       "time": {"category": {"index": {"2026-09": 0, "2026-10": 1}}}},
         "value": {"0": 1.0, "1": 2.0, "3": 4.0}}
    df = inf.jsonstat_to_frame(j)
    assert len(df) == 3
    assert df[(df.geo == "EA") & (df.time == "2026-10")]["value"].iloc[0] == 4.0


def test_data_stops_at_october_2026():
    df = pd.DataFrame({"date": ["2026-10-01", "2026-11-01"], "value": [1, 2]})
    assert list(inf.up_to_end(df)["value"]) == [1]


def test_saved_copy_is_used_when_the_website_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(inf, "DATA_DIR", tmp_path)
    monkeypatch.setattr(inf, "LIVE", True)
    pd.DataFrame({"date": ["2026-10-01"], "value": [7]}).to_csv(tmp_path / "inflation_x.csv", index=False)

    def website_down():
        raise ConnectionError("site down")
    df, source = inf.load("x", website_down)
    assert source == "saved copy" and df["value"].iloc[0] == 7


def test_bls_skips_months_that_were_not_published(monkeypatch):
    data = [{"year": str(2024 + i // 12), "period": f"M{i % 12 + 1:02d}", "value": str(300 + i)}
            for i in range(24)]
    data[21]["value"] = "-"                            # Oct 2025: not published (shutdown)

    class Reply:
        def raise_for_status(self): pass
        def json(self): return {"Results": {"series": [{"seriesID": "CUUR0000SA0", "data": data}]}}
    monkeypatch.setattr(inf.requests, "post", lambda *a, **k: Reply())
    df = inf.download_bls()
    assert len(df) == 11
    assert pd.Timestamp("2025-10-01") not in set(df["date"])


def test_hormuz_traffic_as_percent_of_normal():
    months = pd.date_range("2025-01-01", "2026-10-01", freq="MS")
    hormuz = pd.DataFrame({"capacity_tanker": [200.0] * 12 + [100.0] * 10}, index=months)
    t = inf.traffic_vs_normal(hormuz)
    assert t.loc["2025-06-01"] == pytest.approx(100)      # 2025 is "normal"
    assert t.loc["2026-10-01"] == pytest.approx(50)


def test_download_hormuz_keeps_only_hormuz(tmp_path, monkeypatch):
    raw = tmp_path / "portwatch.csv"
    pd.DataFrame({"date": ["2026/10/01", "2026/10/01"], "portname": ["Strait of Hormuz", "Suez Canal"],
                  "n_tanker": [1, 20], "n_total": [3, 40], "capacity_tanker": [9000, 900000]}).to_csv(raw, index=False)
    monkeypatch.setattr(inf, "PORTWATCH_RAW", raw)
    df = inf.download_hormuz()
    assert len(df) == 1 and df["n_tanker"].iloc[0] == 1


# ---- tests for the time slider, cards and delay chart ----

def make_inflation(rows):
    """A small inflation table from (country, measure, date, value) tuples."""
    return pd.DataFrame([{"country": c, "measure": m, "date": pd.Timestamp(d), "value": v} for c, m, d, v in rows])


def test_in_period_keeps_both_ends():
    s = pd.Series(range(12), index=pd.date_range("2025-01-01", periods=12, freq="MS"))
    kept = inf.in_period(s, pd.Timestamp("2025-03-01"), pd.Timestamp("2025-05-31"))
    assert list(kept) == [2, 3, 4]


def test_value_at_takes_the_last_month_of_the_period():
    s = pd.Series([1.0, 2.0, 3.0], index=pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"]))
    assert inf.value_at(s, pd.Timestamp("2026-02-28")) == 2.0       # the period ends in February
    assert inf.value_at(s, pd.Timestamp("2026-10-31")) == 3.0       # past the data: the latest month


def test_story_numbers_follow_the_end_of_the_period():
    inflation = make_inflation([("Euro area", "Headline", "2026-02-01", 2.0), ("Euro area", "Headline", "2026-10-01", 4.5),
                                ("Euro area", "Energy", "2026-02-01", 1.0), ("Euro area", "Energy", "2026-10-01", 18.0),
                                ("Euro area", "Food", "2026-02-01", 2.0), ("Euro area", "Food", "2026-10-01", 3.0)])
    traffic = pd.Series([90.0, 0.6], index=pd.to_datetime(["2026-02-01", "2026-10-01"]))
    cards = inf.story_numbers(inflation, traffic)
    assert len(cards) == 3
    assert cards[0]["delta"] == "+2.5 pts since Feb 2026"
    assert cards[2]["value"] == "0.6% of normal"
    assert "food 3.0% (+1.0 pts)" in cards[1]["note"]                    # energy compared with food
    before = inf.story_numbers(inflation, traffic, pd.Timestamp("2026-02-28"))
    assert before[0]["value"] == "2.0%" and before[0]["delta"] is None   # nothing to compare with yet


def test_fit_passthrough_keeps_every_correlation(oil):
    change = inf.oil_change_yoy(oil, "EUR")
    model = inf.fit_passthrough((0.4 * change.shift(2)).dropna(), change)
    assert list(model["correlations"]) == list(range(inf.MAX_LAG_MONTHS + 1))
    assert max(model["correlations"], key=model["correlations"].get) == model["lag"]
