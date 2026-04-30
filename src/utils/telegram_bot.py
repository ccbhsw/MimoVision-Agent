"""
Telegram Bot 模块
通过Telegram接收分析请求并发送结果
"""
import asyncio
import logging
from typing import Optional

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

from src.agents.coordinator import AgentCoordinator
from src.utils.config import get_config

logger = logging.getLogger(__name__)

coordinator: Optional[AgentCoordinator] = None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    await update.message.reply_text(
        "MimoVision-Agent 已启动！\n\n"
        "可用命令：\n"
        "/analyze <品种> — 分析指定品种（默认BTCUSDT）\n"
        "/price <品种> — 获取实时价格\n"
        "/fear — 获取恐慌贪婪指数\n"
        "/help — 查看帮助"
    )


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /analyze 命令"""
    symbol = context.args[0].upper() if context.args else "BTCUSDT"

    await update.message.reply_text(f"正在分析 {symbol}，请稍候...")

    try:
        result = await coordinator.analyze(
            symbol=symbol,
            timeframes=["1H", "4H", "1D"],
            include_news=True,
            include_charts=True,
        )

        # 发送分析报告
        report = result.format_report()
        if len(report) > 4096:
            # Telegram消息长度限制，分段发送
            for i in range(0, len(report), 4096):
                await update.message.reply_text(report[i:i+4096])
        else:
            await update.message.reply_text(report)

    except Exception as e:
        await update.message.reply_text(f"分析失败: {e}")
        logger.error(f"Analyze command failed: {e}")


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /price 命令"""
    symbol = context.args[0].upper() if context.args else "BTCUSDT"

    try:
        ticker = await coordinator.binance.get_24h_ticker(symbol)
        text = (
            f"{ticker['symbol']}\n"
            f"价格: ${ticker['price']:,.2f}\n"
            f"24h涨跌: {ticker['price_change_pct']:+.2f}%\n"
            f"24h最高: ${ticker['high']:,.2f}\n"
            f"24h最低: ${ticker['low']:,.2f}\n"
            f"24h成交量: {ticker['volume']:,.0f}"
        )
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"获取价格失败: {e}")


async def fear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /fear 命令"""
    try:
        data = await coordinator.news.get_fear_greed_index()
        emoji = {"Extreme Fear": "😱", "Fear": "😰", "Neutral": "😐", "Greed": "😊", "Extreme Greed": "🤑"}
        text = (
            f"恐慌贪婪指数\n"
            f"数值: {data['value']}\n"
            f"状态: {emoji.get(data['classification'], '❓')} {data['classification']}\n"
            f"时间: {data.get('timestamp', 'N/A')}"
        )
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"获取恐慌指数失败: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /help 命令"""
    await update.message.reply_text(
        "MimoVision-Agent 使用指南\n\n"
        "/analyze BTCUSDT — 分析BTC合约\n"
        "/analyze SOLUSDT — 分析SOL合约\n"
        "/price ETHUSDT — 查看ETH价格\n"
        "/fear — 查看恐慌贪婪指数\n\n"
        "支持品种: BTC, ETH, SOL, BNB, 黄金(XAUUSD) 等"
    )


async def post_init(application: Application):
    """Bot初始化后设置命令菜单"""
    commands = [
        BotCommand("analyze", "分析合约 (如 /analyze BTCUSDT)"),
        BotCommand("price", "查看价格 (如 /price SOLUSDT)"),
        BotCommand("fear", "恐慌贪婪指数"),
        BotCommand("help", "使用帮助"),
    ]
    await application.bot.set_my_commands(commands)


async def start_bot():
    """启动Telegram Bot"""
    global coordinator

    config = get_config()
    if not config.telegram.bot_token:
        logger.error("Telegram bot token not configured!")
        return

    coordinator = AgentCoordinator()

    app = Application.builder().token(config.telegram.bot_token).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("fear", fear_command))
    app.add_handler(CommandHandler("help", help_command))

    logger.info("Starting Telegram bot...")
    await app.run_polling()
