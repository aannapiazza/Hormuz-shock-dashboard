# Hormuz shock dashboard

An interactive Streamlit dashboard that follows one question: **what happened to energy markets, shipping and household prices after the Strait of Hormuz closed in 2026?** About a fifth of the world's oil and LNG normally passes through the strait. Each panel looks at the shock from a different angle, using the same timeline, the same colours and the same cut-off date (31 October 2026).

MIS20080 Introduction to Programming · Group project · UCD 2026

## The panels

| Panel | Author | File | Question |
|---|---|---|---|
| Oil prices | Erin Dolly | `panels/oil.py` | What happened to crude oil prices? |
| Shipping & Markets | Anna Piazza | `panels/shipping.py` | How much traffic goes through Hormuz, and what did Brent and WTI do at the same time? |
| Gas & LNG | Eabha Kelly | `panels/gas_lng.py` | What did the closure do to European gas prices, LNG shipping and winter storage? |
| Inflation & households | Eleena Golchin | `panels/inflation.py` | How much of the oil shock reaches consumer prices and household energy bills? |

The home page (`app.py`) shows a small card for each panel: two headline numbers and a chart. Click a card's title to open the full panel.

## Who did what

| Member | Panel | Other work on the project |
|---|---|---|
| Erin Dolly | Oil prices (`panels/oil.py`), oil data files and event sources | Oil card on the home page |
| Anna Piazza | Shipping & Markets (`panels/shipping.py`), PortWatch and market data | Built the home page and the card layout (`app.py`), owns the repository, edited the README |
| Eabha Kelly | Gas & LNG (`panels/gas_lng.py`), gas data files, home page Gas card, `tests/test_gas.py` (23 tests) | Tested a fresh install of the project (all 38 tests pass), added Plotly to `requirements.txt`, wrote the Gas section of the README |
| Eleena Golchin | Inflation & households (`panels/inflation.py`, `panels/inflation_data.py`), `tests/test_inflation.py` | Matched the phases, cut-off and theme across the panels; tidied `requirements.txt` |

Each member wrote and committed their own panel; the commit history on GitHub shows who changed what.

## The timeline

All panels use the same four phases and the same colours:

| Phase | Dates | Colour |
|---|---|---|
| Build-up | 1 Jan – 28 Feb 2026 | yellow |
| War & closure | 28 Feb – 8 Apr 2026 | red |
| Ceasefire | 8 Apr – 8 Jul 2026 | blue |
| Conflict resumes | 8 Jul – 31 Oct 2026 | purple |

Key events: the war begins on 28 February (US–Israel strikes on Iran), a ceasefire on 8 April, a US–Iran MOU on 17 June, and strikes resume on 8 July. All data runs to 31 October 2026.

## How to run

You need Python 3.10 or newer.

1. Download the project (on GitHub: **Code → Download ZIP**, then unzip it) or clone it:
```
   git clone https://github.com/aannapiazza/Hormuz-shock-dashboard.git
   cd Hormuz-shock-dashboard
```
2. Install the requirements:
```
   python3 -m pip install -r requirements.txt
```
3. Start the dashboard from the project folder:
```
   python3 -m streamlit run app.py
```
   It opens in your browser at http://localhost:8501.

4. To run one panel on its own:
```
   python3 -m streamlit run panels/gas_lng.py
```
5. To run the tests:
```
   python3 -m pytest -q
```

**Tested on a fresh download** (24 November 2026): the requirements install with no errors, all 38 tests pass (`tests/test_gas.py` and `tests/test_inflation.py`), and all four panels open.

## Data and reproducibility

Every panel reads saved copies of its data from `data/`, so the dashboard runs offline and always shows the same numbers. Each panel has a `LIVE` setting at the top of its file: set it to `True` to download fresh data from the source (it falls back to the saved copy if a website is down). Data after 31 October 2026 is cut off, so all panels stop on the same day. The sources and file names for each panel are listed in its section below.

## Project structure

```
app.py                  home page with one card per panel
panels/                 one file per panel (oil, shipping, gas_lng, inflation) + inflation_data.py
data/                   saved copies of all data (CSV)
tests/                  tests for the gas and inflation panels
requirements.txt        Python packages needed to run the dashboard and the tests
.streamlit/config.toml  the shared light theme
```

## Limitations

The dashboard describes what happened; it does not forecast. Where two series are shown together, they show association, not proof of cause. Each panel lists its own limitations below.

---

## Oil prices (Erin Dolly) — `panels/oil.py`

**Question:** how did the 2026 Iran war and the near-closure of the Strait of Hormuz move the price of crude oil, from September 2025 to the cut-off date of 31 October 2026?

- **KPI cards:** the latest Brent price, its change since the pre-war price, the highest monthly average and the Brent–WTI gap.
- **Main chart:** Brent monthly average price, with buttons to shade each phase of the crisis (Build-up, War & closure, Ceasefire, Conflict resumes), a switch between $ per barrel and % vs pre-war, an option to add WTI for comparison, and zoom buttons for the last 3 or 6 months.
- **Second chart** (pick one): month-on-month change, rolling 3-month volatility or the Brent–WTI gap.
- **Month in focus:** click any month on either chart, or use Previous / Next, to see that month's prices and changes with a short note on what was happening.
- **Home page card:** `render_card()` shows the latest price, the Brent–WTI gap and a small chart with the four phases.

All data is from the U.S. Energy Information Administration via FRED, downloaded in November 2026 and cut off at 31 October 2026.

| Data | Source | Saved copy |
|---|---|---|
| Brent (Europe), monthly average | US EIA via FRED ([`MCOILBRENTEU`](https://fred.stlouisfed.org/series/MCOILBRENTEU)) | `data/oil_monthly_brent_data.csv` |
| WTI (Cushing, Oklahoma), monthly average | US EIA via FRED ([`MCOILWTICO`](https://fred.stlouisfed.org/series/MCOILWTICO)) | `data/oil_monthly_wti_data.csv` |
| Brent (Europe), daily | US EIA via FRED ([`DCOILBRENTEU`](https://fred.stlouisfed.org/series/DCOILBRENTEU)) | `data/oil_daily_brent_data.csv` |
| Sources for the event dates | S&P Global, ING Think, Reuters | `data/oil_event_sources.csv` |

- The **latest price** ($120.15, 30 October 2026) and the **pre-war price** ($71.32, 27 February 2026) are read from the daily file.
- All other figures (monthly change, volatility, year-on-year change, Brent–WTI gap) are calculated in the code from these files.

**Running and updating:** by default the panel reads the saved files in `data/`, so the results are the same every time it runs. Nothing after `END = 31 Oct 2026` is used, even if the files contain later data. To download fresh data from FRED, set `LIVE = True` at the top of `panels/oil.py`; the download is still cut at `END` and saved over the files in `data/`. Everything you might want to change (dates, file names, phases, text, colours) is in the **EDIT HERE** section at the top of the file.

**Event sources:** the phase dates are taken from these reports (also listed in `data/oil_event_sources.csv`). The start of the Build-up phase (1 January 2026) and the pre-war date (27 February 2026) are our own choices.

- [S&P Global, 28 Feb 2026: Iran claims Hormuz is shut down](https://www.spglobal.com/energy/en/news-research/latest-news/crude-oil/022826-iran-claims-hormuz-is-shut-down-after-irgc-threat-to-shipping-tasnim)
- [ING Think, 8 Apr 2026: Oil slumps below $100 after US, Iran agree to two-week ceasefire](https://think.ing.com/articles/the-commodities-feed-oil-slumps-below-100-after-us-iran-agree-to-two-week-ceasefire)
- [Reuters via Al-Monitor, 12 Jul 2026: Iran's IRGC navy says Strait of Hormuz closed until further notice](https://www.al-monitor.com/originals/2026/07/irans-irgc-navy-says-strait-hormuz-closed-until-further-notice-state-media)

Price records such as "highest since March 2012" and "biggest rise since 2020" were checked against the FRED data.

**How the code is organised:**

| Part | What it does |
|---|---|
| EDIT HERE section | Settings: dates, data files, phases, text and colours |
| `read_fred_csv()`, `load_series()`, `download()`, `up_to_end()` | Read the saved FRED files (or download them when `LIVE = True`) and cut them at `END` |
| `add_metrics()`, `build_data()` | Calculate monthly change, volatility, year-on-year, the Brent–WTI gap and change vs pre-war |
| `build_main_figure()`, `build_second_figure()` | Draw the two charts with Plotly |
| `render()` | Lays out the full page (only runs when the panel is opened as its own page) |
| `render_card()`, `card_figure()` | The small summary card on the group home page |

Widget keys all start with `ho_` so they don't clash with the other panels.

**Limitations:** these are spot prices, and the main chart uses monthly averages, which smooth out daily swings. The pre-war price is the Brent close on 27 February 2026.

## Shipping & Markets (Anna Piazza) — `panels/shipping.py`

**Question:** how much traffic goes through the Strait of Hormuz, and what did Brent and WTI oil futures do at the same time?

- **Where things stand:** latest daily ship and tanker transits, the latest Brent and WTI futures prices, and how they compare with before the war (traffic, tanker share, Brent and the Brent–WTI gap).
- **Traffic and prices over time:** pick a time range (30 days to all data) and a view (absolute or % vs pre-war). One chart shows daily ships and tankers with 7-day averages, the other shows Brent (and optionally WTI). Both shade the four phases of the conflict and mark key events.
- **Closer look:** pick one month and see its average ships and tankers a day, tanker share, change vs pre-war traffic and Brent average. A second chart switches between monthly traffic, tanker share, a traffic-vs-Brent scatter and Brent's daily change.
- **Shipping data and download:** the monthly summary and the daily records as tables, with download buttons.
- **Home page card:** `render_card()` shows ships and tankers a day for the latest month, compared with before the war, and a small traffic chart.

| Data | Source | Saved copy |
|---|---|---|
| Daily vessel transits through the Strait of Hormuz (all ships and tankers) | IMF PortWatch daily chokepoint transits | `data/portwatch_daily_chokepoints.csv` |
| Brent and WTI futures, VIX, US Dollar Index | Yahoo Finance via yfinance (`BZ=F`, `CL=F`, `^VIX`, `DX-Y.NYB`) | `data/shipping_markets.csv` |

By default the panel reads the saved copies. To download fresh market prices, set `LIVE = True` at the top of `panels/shipping.py` (it falls back to the saved copy if Yahoo Finance is down), or delete `data/shipping_markets.csv`. The shipping data updates when the PortWatch CSV is replaced.

**Limitations:** "normal" traffic is the average of daily transits between 1 January and 27 February 2026, and the pre-war Brent price is the `BZ=F` close on 27 February. Prices are futures, not spot prices. A 7-day average needs seven consecutive daily observations, and shipping and market data can have different dates. The charts show association, not causation.

## Gas & LNG (Eabha Kelly) — `panels/gas_lng.py`

**Question:** about a fifth of the world's LNG passes through the Strait of Hormuz, almost all of it from Qatar. What has closing the strait done to European gas prices, LNG shipping and Europe's winter gas storage?

- **KPI cards:** the latest European gas price (Dutch TTF) and its change since before the war, how many times more Europe pays than the US, LNG tankers through Hormuz as a share of normal, and EU gas storage against the 5-year average.
- **Main chart:** the monthly European gas price, with the daily price as a thin grey line behind it (from October 2025) and the pre-war level marked. The monthly points take the colour of their phase. You can highlight a phase, switch between $ per MMBtu and % vs pre-war, and add US gas (Henry Hub) for comparison.
- **Second chart** (pick one):
  - *LNG tankers:* tankers through Hormuz each month, against the pre-war level.
  - *EU storage:* 2026 against 2025 and the 5-year average, with the EU's 90% target and 80% flexible target.
  - *Price swings:* the volatility of the daily gas price, with the three biggest one-day jumps marked.
  - *2026 vs 2022:* Europe vs Asia (JKM) prices before the war, in 2026 and at the 2022 crisis peak.
- **Month in focus:** click any month on either chart, or use Previous/Next. The card shows that month's phase, two donuts (LNG traffic vs normal, EU storage % full), the price, its change since before the war, how much more Europe pays than the US, its volatility, and a note on what happened.
- **Everything is linked:** choosing a month, a phase or the price view updates both charts and the Month in focus card together. Picking a phase also shows a summary line with that phase's price change, average tanker traffic and storage change.
- **Gas data and download:** the monthly summary behind every chart and all daily prices as tables, each with a download button (CSV).
- **Home page card:** `render_card()` shows the latest price and tanker count, and a chart of the daily and monthly price with the four phases named.

**Analysis in the code:**
- Daily TTF prices are converted from €/MWh to $/MMBtu using each day's EUR/USD rate, so they can be compared with US gas.
- Daily prices are averaged into months and joined with the monthly World Bank price, the tanker counts and end-of-month storage.
- The code works out the change since February 2026 (the last month before the war), the Europe/US price ratio, tanker traffic as a % of normal, the storage gap to the 5-year average, and which phase each month belongs to.
- **Volatility:** daily log returns, their standard deviation over a rolling 21-trading-day window, scaled to a yearly figure (× √252). European gas went from 53% a year before the war to 79% since, peaking at 162% in late March. The biggest one-day jump was +33% on 2 March.

| Data | Source | Saved copy |
|---|---|---|
| European gas price (Dutch TTF), monthly average | World Bank Pink Sheet | `data/gas_prices_monthly.csv` |
| Daily TTF (€/MWh), US Henry Hub ($/MMBtu), EUR/USD | Yahoo Finance via yfinance (`TTF=F`, `NG=F`, `EURUSD=X`) | `data/gas_prices_daily.csv` |
| LNG tankers through Hormuz each month | S&P Global Commodity Insights and Kpler, as reported in the news | `data/gas_tankers.csv` |
| EU gas storage, % full (2026, 2025 and 5-year average) | GIE AGSI, as reported by Argus, GMK Center and others | `data/gas_storage.csv` |
| Europe (TTF) vs Asia (JKM) prices: before the war, 2026 and the 2022 peak | World Bank, EIA, IEA, S&P Global | `data/gas_benchmarks.csv` |

Every row of every gas data file has a `source` or `url` column, so each number can be traced back to where it came from. The tanker, storage and benchmark files were compiled by hand from the reports linked in each file.

**Running and updating:** by default the panel reads the saved copies. To fetch fresh daily prices, turn on **"Download the latest prices from Yahoo Finance"** at the bottom of the panel; it falls back to the saved copy if Yahoo Finance can't be reached, and it doesn't change the files in `data/`. To also save the download over `data/gas_prices_daily.csv`, set `LIVE = True` at the top of `panels/gas_lng.py`.

**Tests:** `tests/test_gas.py` has 23 tests: the €→$ conversion, the phase of each date, the monthly table (cut-off, pre-war reference, changes), the volatility calculation, the phase shading and the data downloads. Run them with `python3 -m pytest -q tests/test_gas.py`.

**Limitations:** tanker counts come from two trackers that count slightly differently (hover over a bar to see which tracker counted it). Storage readings are on the dates they were reported, not every day; with the latest on 27 October, compared with the latest 5-year average before it (6 October). The panel describes what happened and doesn't forecast prices.

## Inflation & households (Eleena Golchin) — `panels/inflation.py`

**Question:** how much of the Hormuz oil shock is reaching the prices people pay, and what would a new oil price mean for a household's energy bill?

- **Controls:** a **Period** slider, **Countries** (the euro area, Ireland, Germany, France, Italy, Spain, the UK, the USA, South Korea, China and India) and **Measure** (headline, energy, food or services). The slider links the whole panel: the chart shows the months you pick, and the key takeaway, the three numbers and the bill calculator use the last one.
- **Main chart:** *Over time* (inflation with the four phases shaded and tanker traffic through Hormuz on a second axis) or *By country* (a bar chart of each country's change since February 2026).
- **Your energy bill:** pick a country, an oil price a year from now and your monthly bill to see your new bill, with a sensitivity chart of the bill at every oil price from $40 to $200.
- **Home page card:** `render_card()` shows euro-area energy inflation and tanker traffic, with a small chart.

**How the model works:** for each country, the code takes the yearly change in Brent in that country's own currency, tests delays of 0 to 6 months, keeps the delay with the strongest correlation with energy inflation, and fits a least-squares line (`np.polyfit`) through every month since 2016.

| Data | Source | Saved copy |
|---|---|---|
| Inflation: euro area, Ireland, Germany, France, Italy, Spain | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table) (`prc_hicp_minr`) | `data/inflation_eurostat.csv` |
| Inflation: UK, South Korea, China, India | [OECD Data Explorer](https://data-explorer.oecd.org) | `data/inflation_oecd.csv` |
| Inflation: USA | [US Bureau of Labor Statistics](https://www.bls.gov/cpi/) | `data/inflation_bls.csv` |
| Brent crude, monthly | US EIA via FRED (`MCOILBRENTEU`), the same file as the oil panel | `data/oil_monthly_brent_data.csv` |
| Exchange rates | Yahoo Finance via yfinance | `data/inflation_oil.csv` |
| Oil tankers through Hormuz | [IMF PortWatch](https://portwatch.imf.org) | `data/inflation_hormuz.csv` |

US data ends in September 2026 and October 2025 was never published (government shutdown). China has no energy figures and India publishes only headline inflation. South Korea replaces Japan, whose OECD series stops in 2021.

**Running and updating:** the panel reads the saved copies by default. To refresh them, run `python3 -c "from panels.inflation_data import save_all; save_all()"` or set `LIVE = True` in `panels/inflation_data.py`.

**Tests:** `tests/test_inflation.py` has 15 tests using made-up data, so no internet is needed. Run them with `python3 -m pytest -q tests/test_inflation.py`.

**Limitations:** the model is a simple line, so it describes rather than forecasts. It assumes exchange rates and other prices stay the same, and a strong correlation is not proof of cause.

## Use of AI tools

As the module asks, each of us has listed which AI tools we used and what for.

- Erin Dolly:
- Anna Piazza: Claude helped me visualise the data before writing the script and ensure consistency in the organisation of the plots. It was also useful for drafting some of the docstrings and improving the visual appearance of the charts. Once I had completed my panel, Copilot helped me check the accuracy of the data and verify its consistency with the other panels in the dashboard.
- Eabha Kelly: Claude, to help explain errors in my code, suggest ways to improve the layout and colours of my panel, and give step-by-step instructions for git commands and pull requests. I tested every change myself, checked the numbers against my data, and made the final decisions on what went into my panel.
- Eleena Golchin: Claude, to help plan the layout of my panel, explain and fix errors in my code, check that the data and dates matched across the four panels, and give step-by-step instructions for edits and git commits. Gemini, to review the project against the grading criteria. I tested every change myself and chose what went into the panel.
