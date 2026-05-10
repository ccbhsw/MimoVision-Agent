# Changelog

All notable changes to MimoVision-Agent will be documented in this file.

## [2.1.0] - 2026-05-10

### Added
- English README for international users
- Example analysis output (`examples/BTCUSDT_report.md`)
- Example chart screenshots (`examples/screenshots/`)
- CHANGELOG.md for tracking project updates
- Backtesting mode with historical performance metrics
- Multi-language support for reports (Chinese / English)

### Changed
- Updated MiMo API endpoint to v2.5-Pro latest version
- Improved chart generation with 6 technical indicators overlay
- Enhanced risk management with dynamic Kelly criterion adjustment
- Optimized async data collection for lower latency

## [2.0.0] - 2026-05-01

### Added
- 5 Agent modules: DataAgent, VisionAgent, NewsAgent, StrategyAgent, RiskAgent
- 4 Strategy modules: TrendFollowing, MeanReversion, Breakout, Ensemble (weighted voting)
- 3 Risk modules: PositionSizer (Kelly criterion), StopManager (ATR/trailing/breakeven), LeverageAdvisor
- 4 Data collectors: BinanceFutures, YahooFinance (gold/oil/indices), MarketMetrics, NewsCollector
- 4 Analyzers: Technical (15+ indicators), ChartGenerator, MultimodalAnalyzer, SentimentEngine
- REST API server with FastAPI
- WebSocket real-time data push
- Dark-themed web dashboard (Bootstrap5 + Chart.js)
- Telegram Bot integration
- Docker deployment support
- Comprehensive test suite
- Full documentation (architecture, API, deployment)

## [1.0.0] - 2026-04-30

### Added
- Initial MVP release
- MiMo API client with vision/reasoning/fast model support
- Binance Futures data collector
- News sentiment collector
- Technical analyzer (RSI, MACD, BB, KDJ, EMA, ATR)
- Chart generator with multi-indicator overlay
- Multi-agent coordinator
- Risk management module
- REST API server
- Telegram Bot integration
