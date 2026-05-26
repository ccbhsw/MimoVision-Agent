<!--
DreamSeed Activity Tag
Activity ID: MimoVision-Agent
Activity Name: DreamSeed 种梦计划
Participation Statement: 本项目参与 DreamSeed 种梦计划 AI创造者大赛
Activity Link: https://www.dreamfield.top/dream-field
-->

<!--
╔══════════════════════════════════════════════════════════════╗
║  DreamSeed 种梦计划 — AI创造者大赛                            ║
║  DreamField Activity Tag                                     ║
╠══════════════════════════════════════════════════════════════╣
║  活动: DreamSeed 种梦计划                                     ║
║  平台: DreamField (https://www.dreamfield.top)                ║
║  参赛声明: 本项目为 DreamSeed 种梦计划参赛作品                ║
║  造梦者: ccbhsw                                               ║
║  项目: MimoVision-Agent                                       ║
╚══════════════════════════════════════════════════════════════╝
-->

# MimoVision-Agent

<div align="center">

**基于小米MiMo多模态大模型的金融智能分析Agent系统**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MiMo Powered](https://img.shields.io/badge/Powered%20by-Xiaomi%20MiMo-orange.svg)](https://github.com/XiaomiMiMo/MiMo)

中文 | [English](./README_EN.md)

</div>

---

## 项目简介

MimoVision-Agent 是一个**多模态金融智能分析系统**，利用小米 MiMo-V2.5 系列模型的强大能力，实现对金融市场的全方位智能分析。系统集成了文本分析、图表视觉理解、新闻情绪挖掘、技术指标计算等多种能力，为合约交易提供数据驱动的决策支持。

### 核心特性

- **多模态分析引擎** — 基于 MiMo-V2.5-Omni，同时理解K线图表、新闻文本、市场数据
- **多周期技术分析** — 支持 15m/1H/4H/1D/1W 多周期交叉验证
- **消息面情绪分析** — 自动采集新闻并量化市场情绪（-5 到 +5 评分）
- **合约专项分析** — 资金费率、持仓量、多空比等合约专属数据
- **风险管理模块** — 仓位计算、止损止盈建议、杠杆适配
- **实时Agent调度** — 多Agent协作，自动完成数据采集→分析→报告生成
- **Web可视化界面** — 实时查看分析结果、历史报告、市场仪表盘
- **Telegram Bot** — 随时随地通过TG获取分析报告和图表

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   MimoVision-Agent                   │
├──────────┬──────────┬──────────┬────────────────────┤
│  数据采集层  │  多模态分析层  │  策略决策层  │     输出层        │
├──────────┼──────────┼──────────┼────────────────────┤
│ Binance  │  K线图表   │  趋势判断  │   Web Dashboard  │
│ Futures  │  视觉理解  │  入场信号  │   Telegram Bot   │
│ Yahoo    │  新闻情绪  │  风险评估  │   PDF Report     │
│ Fear&Greed│ 技术指标  │  仓位管理  │   API Server     │
│ CoinGecko│  多周期   │  杠杆建议  │   WebSocket      │
│ RSS News │  交叉验证  │  止损止盈  │                  │
└──────────┴──────────┴──────────┴────────────────────┘
         │               │               │
         ▼               ▼               ▼
┌─────────────────────────────────────────────────────┐
│              MiMo-V2.5 Model Layer                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ MiMo-V2.5-  │  │ MiMo-V2.5-  │  │ MiMo-V2.5-  │ │
│  │   Pro       │  │   Omni      │  │   Flash     │ │
│  │ (推理决策)   │  │ (多模态理解) │  │ (快速分析)   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+（可选，用于Web前端）
- Docker & Docker Compose（可选）

### 安装

```bash
# 克隆项目
git clone https://github.com/ccbhsw/MimoVision-Agent.git
cd MimoVision-Agent

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp config/.env.example config/.env
# 编辑 config/.env 填入你的 MiMo API Key 和其他配置

# 启动系统
python -m src.main
```

### Docker 部署

```bash
docker-compose up -d
```

---

## 配置说明

编辑 `config/.env` 文件：

```ini
# MiMo API 配置
MIMO_API_KEY=your_mimo_api_key
MIMO_BASE_URL=https://api.xiaomimimo.com/v1

# MiMo 模型选择
MIMO_VISION_MODEL=mimo-v2-omni          # 多模态理解
MIMO_REASONING_MODEL=mimo-v2.5-pro      # 推理决策
MIMO_FAST_MODEL=mimo-v2-flash            # 快速任务

# Binance Futures API
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret

# Telegram Bot
TG_BOT_TOKEN=your_tg_bot_token
TG_CHAT_ID=your_tg_chat_id

# 风险控制
MAX_POSITION_PCT=15          # 最大仓位百分比
DEFAULT_LEVERAGE=20          # 默认杠杆
STOP_LOSS_ATR_MULT=2.5       # 止损ATR倍数

# 新闻数据源
BRAVE_SEARCH_API_KEY=your_brave_api_key
```

---

## 使用方式

### 命令行

```bash
# 分析指定品种
python -m src.main --symbol BTCUSDT --timeframes 1H,4H,1D

# 生成完整分析报告
python -m src.main --symbol SOLUSDT --full-report

# 启动Web服务
python -m src.main --web --port 8080

# 启动Telegram Bot
python -m src.main --telegram
```

### API调用

```python
from src.agents.coordinator import AgentCoordinator

coordinator = AgentCoordinator()
result = await coordinator.analyze(
    symbol="BTCUSDT",
    timeframes=["1H", "4H", "1D"],
    include_news=True,
    include_sentiment=True
)
print(result.summary)
print(result.entry_signal)
print(result.risk_assessment)
```

---

## 项目结构

```
MimoVision-Agent/
├── src/
│   ├── main.py                    # 入口文件
│   ├── agents/
│   │   ├── coordinator.py         # Agent调度协调器
│   │   ├── data_agent.py          # 数据采集Agent
│   │   ├── vision_agent.py        # 多模态视觉分析Agent
│   │   ├── news_agent.py          # 新闻情绪分析Agent
│   │   ├── strategy_agent.py      # 策略分析Agent
│   │   └── risk_agent.py          # 风险管理Agent
│   ├── data_collectors/
│   │   ├── binance_futures.py     # Binance合约数据
│   │   ├── yahoo_finance.py       # Yahoo金融数据
│   │   ├── market_metrics.py      # 恐惧贪婪指数等
│   │   └── news_collector.py      # 新闻RSS采集
│   ├── analyzers/
│   │   ├── technical.py           # 技术指标计算
│   │   ├── chart_generator.py     # K线图生成
│   │   ├── multimodal.py          # MiMo多模态分析
│   │   └── sentiment.py           # 情绪量化引擎
│   ├── strategies/
│   │   ├── trend_following.py     # 趋势跟踪策略
│   │   ├── mean_reversion.py      # 均值回归策略
│   │   ├── breakout.py            # 突破策略
│   │   └── ensemble.py            # 集成策略融合
│   ├── risk/
│   │   ├── position_sizer.py      # 仓位计算器
│   │   ├── stop_manager.py        # 止损止盈管理
│   │   └── leverage_advisor.py    # 杠杆建议引擎
│   ├── api/
│   │   ├── server.py              # REST API服务
│   │   └── websocket.py           # WebSocket实时推送
│   └── utils/
│       ├── mimo_client.py         # MiMo API封装客户端
│       ├── telegram_bot.py        # Telegram Bot封装
│       ├── logger.py              # 日志系统
│       └── config.py              # 配置管理
├── config/
│   ├── .env.example               # 环境变量模板
│   └── symbols.json               # 交易品种配置
├── tests/
│   ├── test_data_collectors.py
│   ├── test_analyzers.py
│   ├── test_strategies.py
│   └── test_risk.py
├── frontend/
│   └── index.html                 # Web仪表盘
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/
│   ├── ARCHITECTURE.md            # 架构设计文档
│   ├── API.md                     # API接口文档
│   └── DEPLOYMENT.md              # 部署指南
├── requirements.txt
├── setup.py
├── LICENSE
└── README.md
```

---

## 技术栈

| 组件 | 技术选型 |
|------|---------|
| 核心大模型 | 小米 MiMo-V2.5-Pro / MiMo-V2.5-Omni |
| 编程语言 | Python 3.11 |
| 异步框架 | asyncio + aiohttp |
| 数据获取 | Binance Futures API, Yahoo Finance, Brave Search |
| 技术指标 | TA-Lib, pandas-ta |
| 图表生成 | matplotlib, mplfinance |
| Web框架 | FastAPI |
| 实时通信 | WebSocket |
| 容器化 | Docker + Docker Compose |
| 消息推送 | Telegram Bot API |

---

## 风险提示

本项目仅供学习研究用途，不构成任何投资建议。合约交易具有高风险，可能导致本金全部损失。请在充分了解风险的前提下使用本工具。

---

## License

MIT License — 自由使用、修改和分发。

---

## 致谢

- [小米 MiMo](https://github.com/XiaomiMiMo/MiMo) — 提供强大的多模态大模型
- [Binance](https://www.binance.com/) — 提供市场数据API
- [TA-Lib](https://ta-lib.org/) — 技术分析指标库
