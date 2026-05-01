# MimoVision-Agent 系统架构

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (HTML/JS)                       │
│            Bootstrap 5 + Chart.js 暗色主题仪表盘                  │
└──────────────┬──────────────────────────────┬───────────────────┘
               │ REST API (/api/*)            │ WebSocket (ws://)
               ▼                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      FastAPI Server (src/api/)                   │
│  server.py ............................ REST 接口                │
│  websocket.py ....................... 实时推送                   │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Agent 协调层 (src/agents/)                     │
│                                                                  │
│  coordinator.py ........... 总调度，串联所有Agent                  │
│  data_agent.py ............ 数据采集调度                          │
│  vision_agent.py .......... 图表分析调度                          │
│  news_agent.py ............ 新闻情绪调度                          │
│  strategy_agent.py ........ 策略信号调度                          │
│  risk_agent.py ............ 风控计算调度                          │
└──┬────────┬────────┬────────┬────────┬────────┬─────────────────┘
   │        │        │        │        │        │
   ▼        ▼        ▼        ▼        ▼        ▼
┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────────────┐
│Binance││Yahoo ││News  ││Multi ││Senti-││  MiMo API    │
│Futures││Finance││Collec││modal ││ment  ││  Client      │
│      ││      ││tor   ││      ││      ││              │
│fapi.  ││yfin.││Brave ││Analy-││Analy-││ mimo-v2.5-pro│
│binance││     ││RSS   ││zer   ││zer   ││ mimo-v2-omni │
│.com   ││     ││F&G   ││      ││      ││ mimo-v2-flash│
└──────┘└──────┘└──────┘└──────┘└──────┘└──────────────┘
```

## 数据流

```
用户请求 (POST /api/analyze)
    │
    ▼
┌─────────────────────────────────────────────┐
│ 1. DataAgent: 采集原始数据                    │
│    ├─ BinanceFutures: K线/资金费率/持仓量      │
│    ├─ YahooFinance: 黄金/白银/原油/指数       │
│    └─ NewsCollector: 新闻/恐慌贪婪指数        │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 2. VisionAgent: 图表生成 + 多模态分析         │
│    ├─ ChartGenerator: TradingView风格K线图    │
│    ├─ MultimodalAnalyzer: MiMo-V2-Omni分析   │
│    └─ 多周期对比 → 方向一致性判断             │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 3. TechnicalAnalyzer: 计算技术指标            │
│    ├─ EMA 9/21/50/200                       │
│    ├─ RSI / MACD / 布林带 / KDJ / ATR       │
│    └─ 支撑阻力位 / 趋势判断                  │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 4. NewsAgent: 新闻情绪分析                    │
│    ├─ SentimentAnalyzer: MiMo-V2-Flash评分   │
│    ├─ 7天情绪趋势                            │
│    └─ 综合情绪报告                           │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 5. StrategyAgent: 信号融合                    │
│    ├─ TrendFollowing / MeanReversion         │
│    ├─ Breakout                               │
│    └─ Ensemble: 加权投票 + 冲突解决           │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 6. RiskAgent: 风控计算                        │
│    ├─ PositionSizer: 仓位/保证金              │
│    ├─ StopManager: 止损止盈                   │
│    └─ LeverageAdvisor: 杠杆建议              │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 7. MiMo-V2.5-Pro: 最终策略推理               │
│    综合以上所有维度 → 输出完整分析报告          │
└──────────────────┬──────────────────────────┘
                   ▼
            返回 JSON 结果
```

## 模块职责

### src/data_collectors/ - 数据采集层

| 模块 | 职责 | 数据源 |
|------|------|--------|
| `binance_futures.py` | 加密货币合约数据 | Binance FAPI |
| `yahoo_finance.py` | 非加密品种（黄金/白银/原油/指数） | yfinance |
| `news_collector.py` | 新闻/恐慌贪婪指数 | Brave Search / alternative.me |
| `market_metrics.py` | 市场综合指标（资金费率趋势/爆仓/大户） | Binance FAPI |

### src/analyzers/ - 分析层

| 模块 | 职责 | MiMo模型 |
|------|------|----------|
| `technical.py` | 技术指标计算（纯数学） | 无 |
| `chart_generator.py` | K线图表生成（matplotlib） | 无 |
| `multimodal.py` | 图表视觉分析 / 多周期对比 / 形态检测 | mimo-v2-omni |
| `sentiment.py` | 新闻情绪分析 / 7天趋势 | mimo-v2-flash |

### src/strategies/ - 策略层

| 模块 | 职责 |
|------|------|
| `trend_following.py` | EMA排列+MACD+成交量 → 趋势信号 |
| `mean_reversion.py` | RSI+布林带 → 均值回归信号 |
| `breakout.py` | 支撑阻力突破 → 突破信号 |
| `ensemble.py` | 加权投票+冲突解决 → 综合信号 |

### src/risk/ - 风控层

| 模块 | 职责 |
|------|------|
| `position_sizer.py` | 固定比例/凯利公式/波动率调整仓位 |
| `stop_manager.py` | ATR止损/支撑阻力止损/移动止损/保本止损 |
| `leverage_advisor.py` | 波动率+账户规模 → 杠杆建议 |

### src/agents/ - Agent调度层

| 模块 | 职责 |
|------|------|
| `coordinator.py` | 总调度，串联所有Agent |
| `data_agent.py` | 数据采集Agent |
| `vision_agent.py` | 图表分析Agent |
| `news_agent.py` | 新闻情绪Agent |
| `strategy_agent.py` | 策略信号Agent |
| `risk_agent.py` | 风控计算Agent |

### src/api/ - API层

| 模块 | 职责 |
|------|------|
| `server.py` | FastAPI REST接口 |
| `websocket.py` | WebSocket实时推送 |

### src/utils/ - 工具层

| 模块 | 职责 |
|------|------|
| `mimo_client.py` | MiMo API封装（chat/图表分析/策略推理/情绪分析） |
| `config.py` | 配置加载 |
| `logger.py` | 日志配置 |
| `telegram_bot.py` | Telegram通知 |

## MiMo 模型使用说明

本项目的核心竞争力来自小米 MiMo 系列模型的多模态能力：

| 模型 | 用途 | 调用位置 |
|------|------|----------|
| **mimo-v2-omni** | K线图表视觉理解 | MultimodalAnalyzer |
| **mimo-v2.5-pro** | 深度策略推理 | Coordinator 最终报告 |
| **mimo-v2-flash** | 快速新闻情绪评分 | SentimentAnalyzer |

### MiMo API 接口

- 兼容 OpenAI Chat Completions 格式
- 支持图片输入（base64 / URL）
- 支持流式输出
- 支持 reasoning_content（推理过程）
- 端点: `https://api.xiaomimimo.com/v1/chat/completions`

## 技术栈

- **后端**: Python 3.11 + FastAPI + aiohttp
- **前端**: Bootstrap 5 + Chart.js + 原生JS
- **数据**: yfinance + Binance FAPI + Brave Search
- **AI**: 小米 MiMo 系列 (v2.5-pro / v2-omni / v2-flash)
- **部署**: Docker + docker-compose
