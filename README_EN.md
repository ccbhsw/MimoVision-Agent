# MimoVision-Agent

<div align="center">

**Multi-Modal Financial Analysis Agent powered by Xiaomi MiMo**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MiMo Powered](https://img.shields.io/badge/Powered%20by-Xiaomi%20MiMo-orange.svg)](https://github.com/XiaomiMiMo/MiMo)

[中文文档](./README.md) | English

</div>

---

## Overview

MimoVision-Agent is a **multi-modal financial analysis system** that leverages Xiaomi's MiMo-V2.5 model family for comprehensive market intelligence. It combines chart visual understanding, news sentiment mining, and technical indicator analysis to provide data-driven trading insights.

### Key Features

- **Multi-Modal Analysis** — MiMo-V2.5-Omni understands candlestick charts, news text, and market data simultaneously
- **Multi-Timeframe Validation** — Cross-validates signals across 15m/1H/4H/1D/1W timeframes
- **News Sentiment Engine** — Automated news collection with quantitative sentiment scoring (-5 to +5)
- **Futures-Specific Data** — Funding rates, open interest, long/short ratios from Binance Futures
- **Risk Management** — Position sizing (Kelly criterion), ATR-based stops, leverage recommendations
- **Multi-Agent Pipeline** — Coordinated agents for data → analysis → strategy → risk assessment
- **Web Dashboard** — Real-time dark-themed dashboard with Chart.js visualizations
- **Telegram Bot** — Get analysis reports and charts anywhere via Telegram
- **REST API + WebSocket** — Full programmatic access for integration

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   MimoVision-Agent                   │
├──────────┬──────────┬──────────┬────────────────────┤
│   Data    │ Analysis │ Strategy │      Output        │
├──────────┼──────────┼──────────┼────────────────────┤
│ Binance  │  Charts  │  Trend   │  Web Dashboard     │
│ Futures  │  Vision  │  Signal  │  Telegram Bot      │
│ Yahoo    │  News    │  Risk    │  PDF Report         │
│ Fear&Gre │  Tech    │  PosSize │  REST API           │
│ CoinGeck │  MultiTF │  Leverage│  WebSocket          │
└──────────┴──────────┴──────────┴────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│              MiMo-V2.5 Model Layer                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ MiMo-V2.5-  │  │ MiMo-V2.5-  │  │ MiMo-V2.5-  │ │
│  │   Pro       │  │   Omni      │  │   Flash     │ │
│  │ (Reasoning) │  │ (Multimodal)│  │  (Fast)     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## Quick Start

### Requirements

- Python 3.11+
- MiMo API Key from [platform.xiaomimimo.com](https://platform.xiaomimimo.com)

### Installation

```bash
git clone https://github.com/ccbhsw/MimoVision-Agent.git
cd MimoVision-Agent
pip install -r requirements.txt
cp config/.env.example config/.env
# Edit config/.env with your API keys
python -m src.main
```

### Docker

```bash
docker-compose up -d
```

---

## Usage

### CLI

```bash
# Analyze a symbol
python -m src.main analyze --symbol BTCUSDT --timeframes 1H,4H,1D

# Full report with news sentiment
python -m src.main analyze --symbol SOLUSDT --full-report

# Start web server
python -m src.main web --port 8080

# Start Telegram bot
python -m src.main telegram
```

### Python API

```python
from src.agents.coordinator import AgentCoordinator

coordinator = AgentCoordinator()
result = await coordinator.analyze(
    symbol="BTCUSDT",
    timeframes=["1H", "4H", "1D"],
    include_news=True,
    include_sentiment=True
)
print(result.summary)        # Strategy summary
print(result.entry_signal)   # Entry signal
print(result.risk_assessment) # Risk assessment
```

### Example Output

See [examples/BTCUSDT_report.md](examples/BTCUSDT_report.md) for a complete analysis report.

---

## Supported Symbols

| Category | Symbols |
|----------|---------|
| Crypto | BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT |
| Commodities | Gold (XAUUSDT), Silver, Crude Oil |
| Indices | S&P 500, NASDAQ 100 |

---

## Project Structure

```
MimoVision-Agent/
├── src/
│   ├── agents/          # Multi-agent coordination
│   ├── data_collectors/ # Market data sources
│   ├── analyzers/       # Technical & sentiment analysis
│   ├── strategies/      # Trading strategy modules
│   ├── risk/            # Risk management
│   ├── api/             # REST + WebSocket server
│   └── utils/           # MiMo client, Telegram bot, config
├── tests/               # Test suite
├── frontend/            # Web dashboard
├── examples/            # Example reports & screenshots
├── docs/                # Documentation
└── docker/              # Docker deployment
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Xiaomi MiMo-V2.5-Pro / Omni / Flash |
| Language | Python 3.11 |
| Async | asyncio + aiohttp |
| Data | Binance Futures API, Yahoo Finance, Brave Search |
| Indicators | TA-Lib, pandas-ta |
| Charts | matplotlib, mplfinance |
| Web | FastAPI |
| Realtime | WebSocket |
| Container | Docker + Docker Compose |
| Messaging | Telegram Bot API |

---

## License

MIT License — Free to use, modify, and distribute.

---

## Acknowledgments

- [Xiaomi MiMo](https://github.com/XiaomiMiMo/MiMo) — Powerful multi-modal LLM
- [Binance](https://www.binance.com/) — Market data API
- [TA-Lib](https://ta-lib.org/) — Technical analysis library

---

## Disclaimer

This project is for educational and research purposes only. It does not constitute financial advice. Futures trading carries significant risk. Always do your own research.
