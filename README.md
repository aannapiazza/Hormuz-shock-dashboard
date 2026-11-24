# Hormuz shock dashboard

An interactive dashboard that follows one question: **what happened to energy markets, shipping and household prices after the Strait of Hormuz closed in 2026?** About a fifth of the world's oil and LNG normally passes through the strait. Each panel looks at the shock from a different angle, using the same timeline and the same cut-off date.

## The panels

| Panel | Author | File | Question |
|---|---|---|---|
| Oil | Erin Dolly| `panels/oil.py` | What happened to crude oil prices? |
| Shipping & Markets | Anna Piazza | `panels/shipping.py` | How much traffic goes through Hormuz, and what did Brent and WTI do at the same time? |
| Gas & LNG | Eabha Kelly | `panels/gas_lng.py` | What did the closure do to European gas prices, LNG shipping and winter storage? |
| Inflation & households | Eleena Golchin | `panels/inflation.py` | How much of the oil shock reaches consumer prices and household energy bills? |

The home page shows a small card for each panel. Click a card to open the full panel.

## The timeline

All panels use the same four phases and the same colours:

| Phase | Dates | Colour |
|---|---|---|
| Build-up | 1 Jan – 28 Feb 2026 | yellow |
| War & closure | 28 Feb – 8 Apr 2026 | red |
| Ceasefire | 8 Apr – 8 Jul 2026 | blue |
| Conflict resumes | 8 Jul – 31 Oct 2026 | purple |

Key events: the war begins on 28 Feb (US-Israel strikes on Iran), ceasefire on 8 Apr, US–Iran MOU on 17 Jun, strikes resume on 8 Jul. All data runs to **31 October 2026**.

## How to run

1. Install the requirements:

```bash
pip install streamlit pandas numpy plotly yfinance
```

2. From the project folder, start the dashboard:

```bash
python3 -m streamlit run app.py
```

3. To run a single panel on its own:

```bash
python3 -m streamlit run panels/shipping.py
```

## Data and reproducibility

Every panel reads **saved copies of its data from `data/`**, so the dashboard runs offline and always shows the same numbers. Each panel has a `LIVE` setting at the top of its file: set it to `True` to download fresh data from the source (it falls back to the saved copy if a website is down). The sources and file names for each panel are listed in its own section below.

## Project structure

```
app.py          home page with one card per panel
panels/         one file per panel (oil, shipping, gas_lng, inflation)
data/           saved copies of all data (CSV)
tests/          tests for the panels (e.g. tests/test_gas.py)
```

## Limitations

The dashboard describes what happened; it does not forecast. Where two series are shown together, they show association, not proof of cause. Each panel lists its own limitations below.

---

## Shipping & Markets (Anna Piazza) — `panels/shipping.py`

**Question:** how much traffic goes through the Strait of Hormuz, and what did Brent and WTI oil futures do at the same time?

1. **Where things stand:** latest daily ship and tanker transits, the latest Brent and WTI futures prices, and how they compare with before the war (traffic, tanker share, Brent and the Brent–WTI gap).
2. **Traffic and prices over time:** pick a time range (30 days to all data) and a view (absolute or % vs pre-war). One chart shows daily ships and tankers with 7-day averages, the other shows Brent (and optionally WTI). Both shade the four phases of the conflict (the same colours as the other panels) and mark key events.
3. **Closer look:** pick one month and see its average ships and tankers a day, tanker share, change vs pre-war traffic and Brent average. A second chart switches between monthly traffic, tanker share, a traffic-vs-Brent scatter and Brent's daily change.
4. **Home page card:** `render_card()` shows ships and tankers a day for the latest month, compared with before the war, and a small traffic chart.

| Data | Source | Saved copy |
|---|---|---|
| Daily vessel transits through the Strait of Hormuz (all ships and tankers) | [IMF PortWatch](https://portwatch.imf.org) daily chokepoint transits | `data/portwatch_daily_chokepoints.csv` |
| Brent and WTI futures, VIX, US Dollar Index | Yahoo Finance via `yfinance` (`BZ=F`, `CL=F`, `^VIX`, `DX-Y.NYB`) | `data/shipping_markets.csv` |

All data runs to **31 October 2026**. By default the panel reads the saved copies, so it runs offline and always shows the same numbers. To download fresh market prices, set `LIVE = True` at the top of `panels/shipping.py` (it falls back to the saved copy if Yahoo is down), or delete `data/shipping_markets.csv`. The shipping data updates when the PortWatch CSV is replaced.

**Limitations:** "normal" traffic is the average of daily transits between 1 January and 27 February 2026, and the pre-war Brent price is the `BZ=F` close on 27 February. Prices are futures, not spot prices. A 7-day average needs seven consecutive daily observations, and shipping and market data can have different dates. The charts show association, not causation.

---

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

---

## Inflation & households (Eleena Golchin) — `panels/inflation.py`

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
