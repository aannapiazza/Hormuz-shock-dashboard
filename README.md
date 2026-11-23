# build-you-wealth-dashboard## 🧾 Inflation & households (Eleena Golchin) — `panels/inflation.py`



**Question:** how much of the Hormuz oil shock is reaching consumer prices, and what would a new oil price mean for a household's energy bill?

1. **Inflation since the war:** pick countries (6 European, the UK, the USA, South Korea, China, India), a measure (headline, energy, food or services) and a start year. Cards show each country's change since February 2026; the chart shades the war, marks key events and can overlay oil-tanker capacity through Hormuz on a second axis.
2. **What it means for your household:** pick a country, a Brent price for a year from now and your monthly energy bill. The panel tests delays of 0–6 months between oil and energy prices, keeps the strongest correlation, fits a least-squares line, and projects energy inflation, headline inflation and your bill.

| Data | Source | Saved copy |
|---|---|---|
| HICP inflation, euro countries | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table) (ECOICOP ver.2) | `data/inflation_eurostat.csv` |
| Energy share of the basket | Eurostat `prc_hicp_iw` | `data/inflation_weights.csv` |
| CPI inflation, UK, South Korea, China, India | [OECD Data Explorer](https://data-explorer.oecd.org) | `data/inflation_oecd.csv` |
| CPI, USA | [US Bureau of Labor Statistics](https://www.bls.gov/cpi/) | `data/inflation_bls.csv` |
| Brent crude and exchange rates | Yahoo Finance via `yfinance` | `data/inflation_oil.csv` |
| Oil tankers through the Strait of Hormuz | [IMF PortWatch](https://portwatch.imf.org) daily chokepoint transits | `data/inflation_hormuz.csv` (from the raw `data/portwatch_daily_chokepoints.csv`) |

All data runs to **October 2026**. By default the panel reads the saved copies, so it runs offline and always shows the same numbers. To download fresh copies from the sources, run:

```bash
python3 -c "from panels.inflation import save_all; save_all()"
```

or set `LIVE = True` at the top of `panels/inflation.py` (it falls back to the saved copies if a website is down).

**Limitations:** the model is descriptive, not a forecast. It assumes exchange rates and non-energy prices stay where they are and ignores second-round effects such as wages. A strong correlation is not proof of cause.


