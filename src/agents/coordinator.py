"""
Agent 调度协调器 v2
集成 CoT推理引擎 + 验证引擎 + 多模型路由 + 并行引擎 + Pipeline编排
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
from src.reasoning.cot_engine import CoTEngine, ReasoningChain
from src.reasoning.verification import VerificationEngine, VerificationResult
from src.orchestration.model_router import ModelRouter
from src.orchestration.parallel_engine import ParallelEngine, TaskSpec
from src.orchestration.pipeline import Pipeline, PipelineStep, StepType
from src.risk.leverage_advisor import LeverageAdvisor
from src.risk.position_sizer import PositionSizer
from src.risk.stop_manager import StopManager

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
    chart_analyses: dict = field(default_factory=dict)
    news_sentiment: dict = field(default_factory=dict)

    # CoT推理链
    reasoning_chain: Optional[ReasoningChain] = None
    verification: Optional[VerificationResult] = None

    # 风险参数
    leverage_advice: dict = field(default_factory=dict)
    position_advice: dict = field(default_factory=dict)
    stop_advice: dict = field(default_factory=dict)

    # 最终结论
    summary: str = ""
    entry_signal: str = ""
    direction: str = ""
    entry_zone: str = ""
    stop_loss: str = ""
    take_profit: str = ""
    leverage: int = 0
    position_pct: float = 0.0
    risk_assessment: str = ""

    def format_report(self) -> str:
        report = f"""# {self.symbol} 合约分析报告
生成时间: {self.timestamp}

## 市场概况
- 当前价格: {self.market_data.get('price', 'N/A')}
- 24h涨跌: {self.market_data.get('change_24h', 'N/A')}%
- 资金费率: {self.market_data.get('funding_rate', 'N/A')}
- 持仓量: {self.market_data.get('open_interest', 'N/A')}
- 多空比: {self.market_data.get('long_short_ratio', 'N/A')}

## CoT推理链
{self.reasoning_chain.format_chain() if self.reasoning_chain else '未执行'}

## 验证结果
{self._format_verification()}

## 综合判断
{self.summary}

## 操作建议
- 方向: {self.direction.upper()}
- 入场区间: {self.entry_zone}
- 止损: {self.stop_loss}
- 建议杠杆: {self.leverage}x ({self.leverage_advice.get('reason', '')})
- 仓位比例: {self.position_pct}%

## 风险提示
{self.risk_assessment}
"""
        return report

    def _format_verification(self) -> str:
        if not self.verification:
            return "未验证"
        v = self.verification
        status = "通过" if v.passed else "未通过"
        lines = [f"- 状态: {status} (评分: {v.score})"]
        if v.issues:
            lines.append("- 问题:")
            for issue in v.issues:
                lines.append(f"  - {issue}")
        if v.suggestions:
            lines.append("- 建议:")
            for s in v.suggestions:
                lines.append(f"  - {s}")
        return "\n".join(lines)


class AgentCoordinator:
    """
    Agent调度协调器 v2

    完整流程：
    1. DataAgent - 并行采集市场数据、K线、新闻
    2. VisionAgent - 多模态分析K线图表
    3. NewsAgent - 分析新闻情绪
    4. CoTEngine - Chain-of-Thought 5步深度推理
    5. VerificationEngine - 推理链自我验证
    6. ModelRouter - 多模型共识投票
    7. RiskAgent - 杠杆/仓位/止损综合风控
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

        self.cot_engine = CoTEngine(self.mimo)
        self.verification_engine = VerificationEngine(self.mimo)
        self.router = ModelRouter(self.mimo)
        self.parallel = ParallelEngine(self.mimo)
        self.leverage_advisor = LeverageAdvisor(
            max_leverage=config.risk.max_leverage,
        )
        self.position_sizer = PositionSizer(
            max_position_pct=config.risk.max_position_pct,
            max_leverage=config.risk.max_leverage,
        )
        self.stop_manager = StopManager(
            atr_mult_sl=config.risk.stop_loss_atr_mult,
            atr_mult_tp=config.risk.take_profit_atr_mult,
        )

    async def analyze(
        self,
        symbol: str = "BTCUSDT",
        timeframes: Optional[list[str]] = None,
        include_news: bool = True,
        include_charts: bool = True,
    ) -> AnalysisResult:
        config = get_config()
        timeframes = timeframes or config.analysis.default_timeframes

        result = AnalysisResult(
            symbol=symbol,
            timeframes=timeframes,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        logger.info(f"Starting v2 analysis for {symbol} on {timeframes}")

        # Step 1: 并行数据采集
        logger.info("Step 1: Collecting market data (parallel)...")

        klines_tasks = {
            tf: self.binance.get_klines(symbol, tf, limit=200)
            for tf in timeframes
        }

        market_task = self.binance.get_market_summary(symbol)

        klines_results = {}
        for tf, task in klines_tasks.items():
            try:
                klines_results[tf] = await task
            except Exception as e:
                logger.error(f"Klines {tf} failed: {e}")

        try:
            result.market_data = await market_task
        except Exception as e:
            logger.error(f"Market summary failed: {e}")

        # Step 2: 技术指标计算
        logger.info("Step 2: Calculating technical indicators...")
        for tf, klines in klines_results.items():
            if klines:
                df = TechnicalAnalyzer.klines_to_dataframe(klines)
                result.technical_indicators[tf] = TechnicalAnalyzer.calculate_all(df)

        # Step 3: 图表生成 + 多模态分析
        if include_charts and klines_results:
            logger.info("Step 3: Generating charts & multimodal analysis...")

            for tf, klines in klines_results.items():
                if klines:
                    try:
                        chart_bytes = ChartGenerator.generate_chart(
                            klines=klines, symbol=symbol, timeframe=tf,
                            indicators=result.technical_indicators.get(tf, {}),
                        )
                        response = await self.mimo.analyze_chart(
                            image_path=chart_bytes, symbol=symbol, timeframe=tf,
                        )
                        result.chart_analyses[tf] = response.content
                    except Exception as e:
                        logger.error(f"Chart analysis failed for {tf}: {e}")

        # Step 4: 新闻情绪分析
        if include_news:
            logger.info("Step 4: Analyzing news sentiment...")
            try:
                news_items = await self.news.get_symbol_news(symbol)
                fear_greed = await self.news.get_fear_greed_index()

                if news_items:
                    sentiment_response = await self.mimo.analyze_news_sentiment(
                        news_items=news_items, symbol=symbol,
                    )
                    result.news_sentiment = {
                        "news": news_items,
                        "fear_greed": fear_greed,
                        "mimo_analysis": sentiment_response.content,
                    }
                else:
                    result.news_sentiment = {"fear_greed": fear_greed}
            except Exception as e:
                logger.error(f"News analysis failed: {e}")

        # Step 5: CoT 5步深度推理
        logger.info("Step 5: CoT reasoning (5 steps)...")
        try:
            result.reasoning_chain = await self.cot_engine.reason_full_analysis(
                symbol=symbol,
                market_data=result.market_data,
                technical_indicators=result.technical_indicators,
                chart_analyses=result.chart_analyses,
                news_sentiment=result.news_sentiment,
            )
        except Exception as e:
            logger.error(f"CoT reasoning failed: {e}")

        # Step 6: 推理链验证
        logger.info("Step 6: Verifying reasoning chain...")
        if result.reasoning_chain:
            try:
                result.verification = await self.verification_engine.verify_chain(
                    reasoning_text=result.reasoning_chain.format_chain(),
                    market_data=result.market_data,
                    technical_indicators=result.technical_indicators,
                    final_direction=result.reasoning_chain.final_conclusion,
                    final_confidence=result.reasoning_chain.overall_confidence,
                )
            except Exception as e:
                logger.error(f"Verification failed: {e}")

        # Step 7: 多模型共识投票
        logger.info("Step 7: Multi-model consensus vote...")
        agreement = 0
        try:
            tech_summary = "\n".join([
                TechnicalAnalyzer.format_analysis(indicators, symbol, tf)
                for tf, indicators in result.technical_indicators.items()
            ])

            chart_summary = "\n".join([
                f"### {tf} 图表分析\n{analysis}"
                for tf, analysis in result.chart_analyses.items()
            ])

            reasoning_summary = result.reasoning_chain.final_conclusion if result.reasoning_chain else ""

            vote_prompt = (
                f"品种: {symbol}\n"
                f"当前价格: {result.market_data.get('price', 'N/A')}\n\n"
                f"技术指标:\n{tech_summary[:2000]}\n\n"
                f"图表分析:\n{chart_summary[:1500]}\n\n"
                f"CoT推理结论: {reasoning_summary}\n\n"
                "请给出你的方向判断：做多、做空、还是观望？给出理由。"
            )

            vote_result = await self.mimo.multi_model_vote(
                prompt=vote_prompt,
                models=["mimo-v2.5-pro", "mimo-v2-flash"],
                system_prompt="你是专业的合约交易分析师，请基于数据给出方向判断。",
            )
            consensus = vote_result.get("consensus_direction", "wait")
            agreement = vote_result.get("agreement_pct", 0)
            best_response = vote_result.get("best_response")

            if best_response:
                result.summary = best_response.content
        except Exception as e:
            logger.error(f"Multi-model vote failed: {e}")
            consensus = "wait"

        # Step 8: 综合风控
        logger.info("Step 8: Risk management...")

        if result.reasoning_chain and result.reasoning_chain.final_conclusion:
            rc = result.reasoning_chain.final_conclusion.lower()
            if "做多" in rc or "long" in rc or "买入" in rc:
                result.direction = "long"
            elif "做空" in rc or "short" in rc or "卖出" in rc:
                result.direction = "short"
            else:
                result.direction = consensus
        else:
            result.direction = consensus

        primary_tf = timeframes[0] if timeframes else "1H"
        primary_ind = result.technical_indicators.get(primary_tf, {})
        atr = primary_ind.get("atr", 0)
        atr_pct = primary_ind.get("atr_pct", 0)
        current_price = primary_ind.get("current_price", 0)

        if current_price > 0 and atr > 0:
            result.leverage_advice = self.leverage_advisor.suggest(
                atr_pct=atr_pct,
                account_balance=10000,
                position_value=10000 * 0.1,
            )
            result.leverage = result.leverage_advice["suggested_leverage"]

            result.stop_advice = self.stop_manager.atr_based_stop(
                entry=current_price,
                direction=result.direction,
                atr=atr,
            )
            result.stop_loss = str(result.stop_advice["stop_loss"])
            result.take_profit = str(result.stop_advice["take_profit_2"])

            result.position_advice = self.position_sizer.volatility_adjusted(
                balance=10000,
                atr=atr,
                price=current_price,
                leverage=result.leverage,
            )
            result.position_pct = result.position_advice["position_pct"]
            result.entry_zone = str(current_price)

        risk_parts = []
        if result.verification and not result.verification.passed:
            risk_parts.append(f"推理验证未通过(评分{result.verification.score})，结论需谨慎")
        if result.verification and result.verification.issues:
            risk_parts.append("发现矛盾: " + "; ".join(result.verification.issues[:3]))
        if agreement and agreement < 60:
            risk_parts.append(f"多模型共识度低({agreement}%)，建议观望")
        if atr_pct > 5:
            risk_parts.append(f"波动率极高({atr_pct}%)，建议降低仓位")
        result.risk_assessment = "\n".join(risk_parts) if risk_parts else "无特殊风险提示"

        logger.info(f"Analysis complete: direction={result.direction}, leverage={result.leverage}")
        return result

    async def close(self):
        await self.binance.close()
        await self.news.close()
