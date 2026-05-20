"""
MimoVision-Agent 主入口 v2
支持单次分析、Web服务、Telegram Bot、Pipeline模式
"""
import asyncio
import click
import logging
from pathlib import Path

from src.utils.config import load_config
from src.utils.logger import setup_logger
from src.agents.coordinator import AgentCoordinator


@click.group()
@click.option('--env', default=None, help='Path to .env file')
def cli(env):
    """MimoVision-Agent v2 - 基于MiMo多模态+CoT推理的金融智能分析系统"""
    config = load_config(env)
    setup_logger(config.log_level, config.log_file)


@cli.command()
@click.option('--symbol', default='BTCUSDT', help='Trading symbol')
@click.option('--timeframes', default='1H,4H,1D', help='Timeframes (comma separated)')
@click.option('--no-news', is_flag=True, help='Skip news analysis')
@click.option('--no-charts', is_flag=True, help='Skip chart generation')
@click.option('--output', default=None, help='Output file path')
def analyze(symbol, timeframes, no_news, no_charts, output):
    """分析指定交易品种（完整8步流程）"""
    async def _run():
        coordinator = AgentCoordinator()
        tf_list = [tf.strip() for tf in timeframes.split(',')]

        click.echo(f"开始分析 {symbol} ({', '.join(tf_list)})...")
        click.echo("流程: 数据采集 -> 技术指标 -> 多模态图表 -> 新闻情绪 -> CoT推理 -> 验证 -> 多模型投票 -> 风控")

        result = await coordinator.analyze(
            symbol=symbol,
            timeframes=tf_list,
            include_news=not no_news,
            include_charts=not no_charts,
        )

        report = result.format_report()
        click.echo(report)

        if output:
            Path(output).write_text(report, encoding='utf-8')
            click.echo(f"\n报告已保存到: {output}")

        await coordinator.close()

    asyncio.run(_run())


@cli.command()
@click.option('--symbol', default='BTCUSDT', help='Trading symbol')
@click.option('--timeframes', default='1H,4H,1D', help='Timeframes')
@click.option('--output', default=None, help='Output file path')
def pipeline(symbol, timeframes, output):
    """使用Pipeline编排模式分析（DAG式依赖）"""
    async def _run():
        from src.utils.mimo_client import MiMoClient
        from src.utils.config import get_config
        from src.orchestration.pipeline import Pipeline, PipelineStep, StepType

        config = get_config()
        mimo = MiMoClient(
            api_key=config.mimo.api_key,
            base_url=config.mimo.base_url,
        )
        pipe = Pipeline(mimo)

        tf_list = [tf.strip() for tf in timeframes.split(',')]
        context = {
            "symbol": symbol,
            "timeframes": ", ".join(tf_list),
        }

        click.echo(f"Pipeline模式分析 {symbol}...")

        results = await pipe.execute(Pipeline.FULL_ANALYSIS_PIPELINE, context)

        for name, r in results.items():
            status = "OK" if r.success else f"FAIL: {r.error}"
            click.echo(f"  [{name}] {status} ({r.duration_ms:.0f}ms, model={r.model_used})")

        summary = pipe.get_execution_summary()
        click.echo(f"\n总步骤: {summary['total_steps']}, 成功: {summary['successful']}, 失败: {summary['failed']}")

        if output:
            import json
            Path(output).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    asyncio.run(_run())


@cli.command()
@click.option('--host', default='0.0.0.0', help='Web server host')
@click.option('--port', default=8080, help='Web server port')
def web(host, port):
    """启动Web服务"""
    from src.api.server import create_app
    import uvicorn

    app = create_app()
    uvicorn.run(app, host=host, port=port)


@cli.command()
def telegram():
    """启动Telegram Bot"""
    from src.utils.telegram_bot import start_bot
    asyncio.run(start_bot())


@cli.command()
def version():
    """显示版本信息"""
    click.echo("MimoVision-Agent v2.1.0")
    click.echo("Powered by Xiaomi MiMo-V2.5")
    click.echo("Features: CoT推理 + 多模型投票 + 推理验证 + 多模态分析 + 综合风控")


if __name__ == "__main__":
    cli()
