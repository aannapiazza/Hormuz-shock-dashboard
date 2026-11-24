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




## Gas & LNG (Eabha Kelly) — `panels/gas_lng.py`

**Question:** about a fifth of the world's LNG passes through the Strait of Hormuz, almost all of it from Qatar. What has closing the strait done to European gas prices, LNG shipping and Europe's winter gas storage?

**What the panel shows**

1. **KPI cards:** the latest European gas price (Dutch TTF) and its change since before the war, how many times more Europe pays than the US, LNG tankers through Hormuz as a share of normal, and how full EU gas storage is compared with the 5-year average.
2. **Main chart:** the monthly European gas price, January to October 2026, with the pre-war level marked. You can shade a phase of the crisis (Build-up, War & closure, Ceasefire, Conflict resumes: the same phases and dates as the oil panel), switch between $ per MMBtu and % vs pre-war, and add US gas (Henry Hub) for comparison.
3. **Second chart** (pick one): LNG tankers through Hormuz each month, EU gas storage in 2026 against 2025 and the 5-year average, or Europe vs Asia (JKM) prices in 2026 compared with the 2022 crisis peak.
4. **Month in focus:** click any month on either chart, or use Previous/Next. The card shows that month's price, its change since before the war, how much more Europe pays than the US, two donuts (LNG traffic vs normal, EU storage % full), and a note on what happened.
5. **Everything is linked:** choosing a month, a phase or the price view updates both charts and the Month in focus card together. Picking a phase also shows a summary line with that phase's price change, average tanker traffic and storage change.
6. **Home page card:** `render_card()` shows the latest price, the latest tanker count and a small price chart on the group's overview page.

**Analysis in the code:** daily TTF prices are converted from €/MWh to $/MMBtu using each day's EUR/USD rate, so they can be compared with US gas. Daily prices are averaged into months and joined with the monthly World Bank price, the tanker counts and end-of-month storage. The code then works out the change since February 2026 (the last month before the war), the Europe/US price ratio, tanker traffic as a % of normal, the storage gap to the 5-year average, and which phase each month belongs to.

| Data | Source | Saved copy |
|---|---|---|
| European gas price (Dutch TTF), monthly average | World Bank Pink Sheet | `data/gas_prices_monthly.csv` |
| Daily TTF (€/MWh), US Henry Hub ($/MMBtu), EUR/USD | Yahoo Finance via `yfinance` (tickers `TTF=F`, `NG=F`, `EURUSD=X`) | `data/gas_prices_daily.csv` |
| LNG tankers through Hormuz each month | S&P Global Commodity Insights and Kpler, as reported in the news | `data/gas_tankers.csv` |
| EU gas storage, % full (2026, 2025 and 5-year average) | GIE AGSI, as reported by Argus, GMK Center and others | `data/gas_storage.csv` |
| Europe (TTF) vs Asia (JKM) prices: before the war, 2026 and the 2022 peak | World Bank, EIA, IEA, S&P Global | `data/gas_benchmarks.csv` |

Every row of every data file has a `source` or `url` column, so each number can be traced back to where it came from.

**Running and updating:** by default the panel reads the saved copies, so it runs offline and always shows the same numbers. Prices stop on **31 October 2026**, the same cut-off as the other panels. To fetch fresh daily prices, turn on **"Download the latest prices from Yahoo Finance"** at the bottom of the panel. It falls back to the saved copy if Yahoo Finance can't be reached, and it doesn't change the files in `data/`. To also save the download over `data/gas_prices_daily.csv`, set `LIVE = True` at the top of `panels/gas_lng.py`.

Run the panel on its own with `python3 -m streamlit run panels/gas_lng.py`. Run its tests with `python3 -m pytest -q tests/test_gas.py` (install pytest first with `pip install pytest` if needed).

**Limitations:** tanker counts come from two trackers (S&P Global counts laden tankers leaving, Kpler counts all LNG-carrier crossings), so months from different trackers aren't exactly comparable. Hover over a bar to see which tracker counted it. EU storage readings are on the dates they were reported, not every day. The panel describes what happened and doesn't forecast prices.
