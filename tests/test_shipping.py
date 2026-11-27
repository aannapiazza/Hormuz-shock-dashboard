import pandas as pd
import pytest

from panels import shipping as sh


def test_market_cutoff(tmp_path, monkeypatch):
    path = tmp_path / "shipping_markets.csv"

    pd.DataFrame({
        "date": ["2026-10-30", "2026-11-02"],
        "BRENT": [117.64, 120.0]
    }).to_csv(path, index=False)

    monkeypatch.setattr(sh, "MARKET_FILE", path)

    data, _ = sh.load_markets(live=False)

    assert data["BRENT"].index.max() <= sh.END


def test_empty_download_preserves_saved_data(tmp_path, monkeypatch):
    path = tmp_path / "shipping_markets.csv"

    pd.DataFrame({
        "date": ["2026-10-30"],
        "BRENT": [117.64]
    }).to_csv(path, index=False)

    original = path.read_bytes()

    monkeypatch.setattr(sh, "MARKET_FILE", path)
    monkeypatch.setattr(
        sh, "load_market_data", lambda *_: pd.Series(dtype=float)
    )

    data, _ = sh.load_markets(live=True)

    assert path.read_bytes() == original
    assert data["BRENT"].iloc[-1] == pytest.approx(117.64)


def test_prewar_baseline():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", "2026-02-28"),
        "n_total": [68] * 58 + [0],
        "n_tanker": [37] * 58 + [0]
    })

    baseline = sh.prewar_baseline(df)

    assert baseline["n_total"] == pytest.approx(68)
    assert baseline["n_tanker"] == pytest.approx(37)


def test_missing_day_in_rolling_average():
    dates = pd.date_range("2026-01-01", "2026-01-10")
    dates = dates.difference([pd.Timestamp("2026-01-03")])

    df = pd.DataFrame({
        "date": dates,
        "n_total": 10,
        "n_tanker": 3
    })

    daily = sh.build_daily(df)

    assert pd.isna(daily.loc["2026-01-09", "n_total_avg7"])
    assert daily.loc["2026-01-10", "n_total_avg7"] == 10


def test_percentage_change():
    assert sh.pct(100, 80) == pytest.approx(-20)
    assert sh.pct(100, 120) == pytest.approx(20)
