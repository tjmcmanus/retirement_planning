# Retirement Planning Application

> A personal, open-source tool for comprehensive retirement and tax planning — built because the existing tools either cost too much, hide their math, or don't model the real complexity of a US retirement plan.

---

## Why This Was Created

Most retirement calculators answer one question: *"Will I run out of money?"*  
This one answers the harder questions:

- **When should I do Roth conversions, and by how much?** The BETR algorithm evaluates each conversion dollar against the marginal tax rate now versus later, accounting for IRMAA cliffs, ACA subsidy thresholds, and RMDs.
- **How do I bridge the gap between early retirement and Medicare / Social Security?** The 7-stage withdrawal engine sequences drawdowns across account types to minimize lifetime taxes.
- **What does a bad sequence of returns actually do to my plan?** Monte Carlo runs 10,000 scenarios using empirical return distributions, not just an average.
- **Am I buying at the wrong time?** Three independent EMA timeframes (short, intermediate, long-term) flag market regime changes so you can adjust allocation tactically without abandoning your plan.
- **How do I track a real portfolio, not a hypothetical one?** The Portfolio Hub stores actual holdings, syncs with 12,000+ brokerages via SnapTrade, and shows performance analytics alongside tax optimisation suggestions.

All calculations run locally. No data leaves your machine. No subscription required.

---

## Quick Start

→ **[Quick Start Guide](docs/user/QUICKSTART.md)** — up and running in 10 minutes

---

## User Guides

| Guide | What it covers |
|---|---|
| [Quick Start](docs/user/QUICKSTART.md) | Installation, first launch, sample data walkthrough |
| [Full User Guide](docs/USER_GUIDE.md) | Every page and feature explained, including all indicator tables |
| [Configuration Guide](docs/user/CONFIG_GUIDE.md) | retirement_config.json fields, the Configuration page |
| [Strategy Guide](docs/user/STRATEGY_README.md) | 7-stage withdrawal engine, BETR integration, sequencing logic |
| [BETR Roth Conversion](docs/user/BETR_GUIDE.md) | Bracket-Efficient Tax-Aware Roth conversion algorithm |
| [Market Trend Analysis](docs/user/MARKET_TREND_GUIDE.md) | 9-state EMA regime/sub-phase indicator tables |
| [Market Stress Indicator](docs/user/MARKET_STRESS_INDICATOR_GUIDE.md) | EventHorizonIQ stress index, thresholds and actions |
| [Portfolio Market Indicators](docs/user/PORTFOLIO_MARKET_INDICATORS_GUIDE.md) | Per-security moving-average conditions |
| [Bucket Strategy](docs/user/BUCKET_STRATEGY_GUIDE.md) | Three-bucket framework, sizing, rebalancing rules |
| [Social Security Optimization](docs/user/SS_OPTIMIZATION_GUIDE.md) | Claiming strategies, spousal coordination, break-even |
| [Portfolio Data Entry](docs/user/PORTFOLIO_DATA_ENTRY_GUIDE.md) | How to enter and manage holdings |
| [Brokerage Connections](docs/guides/brokerage-connections.md) | SnapTrade OAuth setup, sync, troubleshooting |
| [SnapTrade Quick Start](docs/user/SNAPTRADE_QUICKSTART.md) | API credentials, first sync |
| [Portfolio Analytics](docs/user/PORTFOLIO_ANALYTICS_GUIDE.md) | Sharpe ratio, drawdown, benchmark comparison |
| [Portfolio Rebalancing](docs/user/PORTFOLIO_REBALANCING_GUIDE.md) | Tax-efficient rebalancing recommendations |
| [Monte Carlo Guide](docs/getting-started.md#monte-carlo) | Simulation parameters and interpreting results |
| [Single Person Mode](docs/user/SINGLE_PERSON_MODE_GUIDE.md) | Simplified interface for individual planning |
| [LTC Planning](docs/user/LTC_PLANNING_GUIDE.md) | Long-term care cost modelling |
| [HSA Integration](docs/user/HSA_INTEGRATION_GUIDE.md) | HSA contribution and withdrawal optimisation |
| [Direct Indexing](docs/user/DIRECT_INDEXING_USER_GUIDE.md) | Tax-loss harvesting workflow, setup, dashboard usage |
| [Advanced Strategies](docs/advanced/betr-guide.md) | Mega backdoor Roth, DAF, and other advanced planning topics |
| [Scenario Planning](docs/user/SCENARIO_PLANNING_USER_GUIDE.md) | What-if scenarios, comparison tools |
| [Income & Expense Modelling](docs/user/INCOME_EXPENSE_GUIDE.md) | Age-based expense curves, income sources |

---

## Application Pages

| Page | Purpose |
|---|---|
| **Dashboard** | Net worth, retirement readiness score, three-timeframe market forecast |
| **Configuration** | Personal info, expenses, Social Security, tax strategy, portfolio accounts |
| **Portfolio Hub** | Holdings, performance analytics, rebalancing, brokerage sync |
| **Strategy** | Year-by-year 7-stage withdrawal plan |
| **Monte Carlo** | 10,000-scenario probabilistic analysis |
| **Advanced Strategies** | BETR Roth conversions, bucket strategy, tax-loss harvesting, direct indexing, SS optimisation |
| **Estate Planning** | Beneficiary optimisation, estate tax projections, charitable giving |
| **Scenario Planning** | Compare multiple planning scenarios side-by-side |
| **Reports** | Exportable summaries |
| **Admin / Tax Data** | Update tax brackets, IRMAA thresholds, RMD tables |

---

## Technology Stack

| Layer | Technology |
|---|---|
| UI | Streamlit (Python) |
| Data processing | Pandas, NumPy |
| Visualisation | Plotly, Matplotlib |
| Market data | yfinance |
| Brokerage sync | SnapTrade API |
| Credential security | Cryptography (Fernet / AES-256) |
| Testing | pytest |
| Config | JSON, YAML, CSV |

---

## Key Data Files

| File | Purpose |
|---|---|
| `retirement_config.json` | All personal and financial settings |
| `portfolio_data_truth.csv` | Your actual holdings (source of truth) |
| `standard.csv` | Federal income tax brackets |
| `cap_gains.csv` | Capital gains tax rates |
| `irmaa.csv` | Medicare IRMAA premium thresholds |
| `rmd.csv` | Required Minimum Distribution tables |
| `ssincome.csv` | Your Social Security benefit estimates |

---

## Disclaimer

This tool is for educational and personal planning purposes only. It does not constitute financial, tax, or legal advice. Always consult a qualified professional before making financial decisions.

---

## Docs Site

Full documentation is published at the project's GitHub Pages site — see `docs/index.md` for the landing page.

---

*Made with Bob*
