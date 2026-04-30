"""
Agent 调度协调器
多Agent协作完成完整的分析流程
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime
from dataclasses import dataclass, field

from src.utils.mimo_client import MiMoClient, MiMoResponse
from src.utils.config import get_config
from src.data_collectors.binance_futures import BinanceFuturesCollector
from src.data_collectors.news_collector import NewsCollector
from src.analyzers.technical import TechnicalAnalyzer
from src.analyzers.chart_generator import ChartGenerator

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析结果"""
    symbol: str
    timeframes: list[str]
    timestamp: str = ""

    # 各模块分析结果
    market_data: dict = field(default_factory=dict)
    technical_indicators: dict = field(default_factory=dict)
    chart_analyses: dict = field(default_factory=dict)  # {timeframe: vision_analysis}
    news_sentiment: dict = field(default_factory=dict)

    # 最终结论
    summary: str = ""
    entry_signal: str = ""
    direction: str = ""  # long / short / wait
    entry_zone: str = ""
    stop_loss: str = ""
    take_profit: str = ""
    leverage: int = 0
    position_pct: float = 0.0
    risk_assessment: str = ""

    def format_report(self) -> str:
        """格式化完整分析报告"""
        report = f"""# {self.symbol} 合约分析报告
生成时间: {self.timestamp}

## 市场概况
- 当前价格: {self.market_data.get('price', 'N/A')}
- 24h涨跌: {self.market_data.get('change_24h', 'N/A')}%
- 资金费率: {self.market_data.get('funding_rate', 'N/A')}
- 持仓量: {self.market_data.get('open_interest', 'N/A')}
- 多空比: {self.market_data.get('long_short_ratio', 'N/A')}

## 综合判断
{self.summary}

## 操作建议
- 方向: {self.direction.upper()}
- 入场区间: {self.entry_zone}
- 止损: {self.stop_loss}
- 止盈: {self.take_profit}
- 建议杠杆: {self.leverage}x
- 仓位比例: {self.position_pct}%

## 风险提示
{self.risk_assessment}
"""
        return report


class AgentCoordinator:
    """
    Agent调度协调器

    调度流程：
    1. DataAgent — 并行采集市场数据、K线、新闻
    2. VisionAgent — 多模态分析K线图表
    3. NewsAgent — 分析新闻情绪
    4. StrategyAgent — 综合推理，生成策略
    5. RiskAgent — 风险评估和仓位建议
    """

    def __init__(
        self,
        mimo_client: Optional[MiMoClient] = None,
        binance: Optional[BinanceFuturesCollector] = None,
        news: Optional[NewsCollector] = None,
    ):
        config = get_config()
        self.mimo = mimo_client or MiMoClient(
            api_key=config.mimo.api_key,
            base_url=config.mimo.base_url,
        )
        self.binance = binance or BinanceFuturesCollector(
            api_key=config.binance.api_key,
            api_secret=config.binance.api_secret,
        )
        self.news = news or NewsCollector(
            brave_api_key=getattr(config, 'brave_api_key', ''),
        )

    async def analyze(
        self,
        symbol: str = "BTCUSDT",
        timeframes: Optional[list[str]] = None,
        include_news: bool = True,
        include_charts: bool = True,
    ) -> AnalysisResult:
        """
        执行完整分析流程

        Args:
            symbol: 交易对
            timeframes: 时间周期列表
            include_news: 是否包含新闻分析
            include_charts: 是否生成图表
        """
        config = get_config()
        timeframes = timeframes or config.analysis.default_timeframes

        result = AnalysisResult(
            symbol=symbol,
            timeframes=timeframes,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        logger.info(f"Starting analysis for {symbol} on {timeframes}")

        # ━━━ Step 1: 并行数据采集 ━━━
        logger.info("Step 1: Collecting market data...")

        klines_tasks = {
            tf: self.binance.get_klines(symbol, tf, limit=200)
            for tf in timeframes
        }

        data_tasks = [
            self.binance.get_market_summary(symbol),
            self.news.get_fear_greed_index() if include_news else asyncio.sleep(0),
            self.news.get_symbol_news(symbol) if include_news else asyncio.sleep(0),
        ]

        # 并行采集K线
        klines_results = {}
        async def collect_klines():
            for tf, task in klines_tasks.items():
                klines_results[tf] = await task

        # 并行执行
        await asyncio.gather(collect_klines(), *data_tasks)

        # 整理市场数据
        market_summary = data_tasks[0] if not isinstance(data_tasks[0], asyncio.Task) else {}
        result.market_data = market_summary if isinstance(market_summary, dict) else {}

        # ━━━ Step 2: 技术指标计算 ━━━
        logger.info("Step 2: Calculating technical indicators...")

        for tf, klines in klines_results.items():
            if klines:
                df = TechnicalAnalyzer.klines_to_dataframe(klines)
                result.technical_indicators[tf] = TechnicalAnalyzer.calculate_all(df)

        # ━━━ Step 3: 生成K线图表 + 多模态分析 ━━━
        if include_charts and klines_results:
            logger.info("Step 3: Generating charts & multimodal analysis...")

            chart_tasks = {}
            for tf, klines in klines_results.items():
                if klines:
                    chart_tasks[tf] = asyncio.create_task(
                        self._analyze_chart(klines, symbol, tf, result.technical_indicators.get(tf, {}))
                    )

            for tf, task in chart_tasks.items():
                try:
                    result.chart_analyses[tf] = await task
                except Exception as e:
                    logger.error(f"Chart analysis failed for {tf}: {e}")
                    result.chart_analyses[tf] = f"Analysis failed: {e}"

        # ━━━ Step 4: 新闻情绪分析 ━━━
        if include_news:
            logger.info("Step 4: Analyzing news sentiment...")

            news_items = []
            fear_greed = {}

            # 获取新闻数据
            try:
                news_items = await self.news.get_symbol_news(symbol)
                fear_greed = await self.news.get_fear_greed_index()
            except Exception as e:
                logger.error(f"News collection failed: {e}")

            # MiMo 分析新闻情绪
            if news_items:
                try:
                    sentiment_response = await self.mimo.analyze_news_sentiment(
                        news_items=news_items,
                        symbol=symbol,
                    )
                    result.news_sentiment = {
                        "news": news_items,
                        "fear_greed": fear_greed,
                        "mimo_analysis": sentiment_response.content,
                    }
                except Exception as e:
                    logger.error(f"Sentiment analysis failed: {e}")
                    result.news_sentiment = {"news": news_items, "fear_greed": fear_greed, "error": str(e)}

        # ━━━ Step 5: 综合策略推理 ━━━
        logger.info("Step 5: Generating strategy with MiMo-V2.5-Pro...")

        try:
            tech_summary = "\n".join([
                TechnicalAnalyzer.format_analysis(indicators, symbol, tf)
                for tf, indicators in result.technical_indicators.items()
            ])

            chart_summary = "\n".join([
                f"### {tf} 图表分析\n{analysis}"
                for tf, analysis in result.chart_analyses.items()
            ])

            news_summary = result.news_sentiment.get("mimo_analysis", "无新闻数据")

            strategy_response = await self.mimo.reason_strategy(
                market_data=result.market_data,
                technical_analysis=tech_summary,
                news_sentiment=news_summary,
                chart_analysis=chart_summary,
            )

            # 解析策略结果
            self._parse_strategy_response(strategy_response.content, result)

        except Exception as e:
            logger.error(f"Strategy generation failed: {e}")
            result.summary = f"策略生成失败: {e}"

        logger.info(f"Analysis complete for {symbol}")
        return result

    async def _analyze_chart(
        self,
        klines: list[dict],
        symbol: str,
        timeframe: str,
        indicators: dict,
    ) -> str:
        """生成图表并用MiMo-Omni进行多模态分析"""
        # 生成图表
        chart_bytes = ChartGenerator.generate_chart(
            klines=klines,
            symbol=symbol,
            timeframe=timeframe,
            indicators=indicators,
        )

        # MiMo 多模态分析
        response = await self.mimo.analyze_chart(
            image_path=chart_bytes,
            symbol=symbol,
            timeframe=timeframe,
        )

        return response.content

    def _parse_strategy_response(self, content: str, result: AnalysisResult):
        """解析策略响应，填充结果字段"""
        result.summary = content

        # 简单关键词提取
        content_lower = content.lower()

        if "做多" in content or "long" in content_lower or "买入" in content:
            result.direction = "long"
        elif "做空" in content or "short" in content_lower or "卖出" in content:
            result.direction = "short"
        else:
            result.direction = "wait"

        # 提取杠杆建议
        for word in content.split():
            if "x" in word.lower() and any(c.isdigit() for c in word):
                try:
                    result.leverage = int(''.join(c for c in word if c.isdigit()))
                except ValueError:
                    pass

        config = get_config()
        if not result.leverage:
            result.leverage = config.risk.default_leverage
        if not result.position_pct:
            result.position_pct = (config.risk.max_position_pct + config.risk.min_position_pct) / 2
