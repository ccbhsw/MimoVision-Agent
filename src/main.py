"""
MimoVision-Agent 主入口
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
    """MimoVision-Agent - 基于MiMo多模态的金融智能分析系统"""
    config = load_config(env)
    setup_logger(config.log_level, config.log_file)


@cli.command()
@click.option('--symbol', default='BTCUSDT', help='Trading symbol')
@click.option('--timeframes', default='1H,4H,1D', help='Timeframes (comma separated)')
@click.option('--no-news', is_flag=True, help='Skip news analysis')
@click.option('--no-charts', is_flag=True, help='Skip chart generation')
@click.option('--output', default=None, help='Output file path')
def analyze(symbol, timeframes, no_news, no_charts, output):
    """分析指定交易品种"""
    async def _run():
        coordinator = AgentCoordinator()
        tf_list = [tf.strip() for tf in timeframes.split(',')]

        click.echo(f"开始分析 {symbol} ({', '.join(tf_list)})...")

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

        await coordinator.binance.close()
        await coordinator.news.close()

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


if __name__ == "__main__":
    cli()
