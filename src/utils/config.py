"""
配置管理模块
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MiMoConfig:
    """MiMo API 配置"""
    api_key: str = ""
    base_url: str = "https://api.xiaomimimo.com/v1"
    vision_model: str = "mimo-v2-omni"
    reasoning_model: str = "mimo-v2.5-pro"
    fast_model: str = "mimo-v2-flash"


@dataclass
class BinanceConfig:
    """Binance API 配置"""
    api_key: str = ""
    api_secret: str = ""
    base_url: str = "https://fapi.binance.com"


@dataclass
class TelegramConfig:
    """Telegram Bot 配置"""
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class RiskConfig:
    """风险控制配置"""
    max_position_pct: float = 15.0
    min_position_pct: float = 5.0
    default_leverage: int = 20
    max_leverage: int = 50
    stop_loss_atr_mult: float = 2.5
    take_profit_atr_mult: float = 4.0
    risk_per_trade_pct: float = 2.0


@dataclass
class AnalysisConfig:
    """分析配置"""
    default_timeframes: list = field(default_factory=lambda: ["1H", "4H", "1D"])
    news_count: int = 5
    technical_indicators: list = field(default_factory=lambda: [
        "RSI", "MACD", "BB", "KDJ", "EMA", "ATR"
    ])


@dataclass
class WebConfig:
    """Web服务配置"""
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False


@dataclass
class AppConfig:
    """应用总配置"""
    mimo: MiMoConfig = field(default_factory=MiMoConfig)
    binance: BinanceConfig = field(default_factory=BinanceConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    web: WebConfig = field(default_factory=WebConfig)
    log_level: str = "INFO"
    log_file: str = "logs/mimovision.log"


# 全局配置单例
_config: Optional[AppConfig] = None


def load_config(env_path: Optional[str] = None) -> AppConfig:
    """加载配置"""
    global _config

    if env_path:
        load_dotenv(env_path)
    else:
        # 查找默认 .env 文件
        for search_path in [
            Path("config/.env"),
            Path(".env"),
            Path(__file__).parent.parent.parent / "config" / ".env",
        ]:
            if search_path.exists():
                load_dotenv(search_path)
                break

    _config = AppConfig(
        mimo=MiMoConfig(
            api_key=os.getenv("MIMO_API_KEY", ""),
            base_url=os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1"),
            vision_model=os.getenv("MIMO_VISION_MODEL", "mimo-v2-omni"),
            reasoning_model=os.getenv("MIMO_REASONING_MODEL", "mimo-v2.5-pro"),
            fast_model=os.getenv("MIMO_FAST_MODEL", "mimo-v2-flash"),
        ),
        binance=BinanceConfig(
            api_key=os.getenv("BINANCE_API_KEY", ""),
            api_secret=os.getenv("BINANCE_API_SECRET", ""),
            base_url=os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com"),
        ),
        telegram=TelegramConfig(
            bot_token=os.getenv("TG_BOT_TOKEN", ""),
            chat_id=os.getenv("TG_CHAT_ID", ""),
        ),
        risk=RiskConfig(
            max_position_pct=float(os.getenv("MAX_POSITION_PCT", "15")),
            min_position_pct=float(os.getenv("MIN_POSITION_PCT", "5")),
            default_leverage=int(os.getenv("DEFAULT_LEVERAGE", "20")),
            max_leverage=int(os.getenv("MAX_LEVERAGE", "50")),
            stop_loss_atr_mult=float(os.getenv("STOP_LOSS_ATR_MULT", "2.5")),
            take_profit_atr_mult=float(os.getenv("TAKE_PROFIT_ATR_MULT", "4.0")),
            risk_per_trade_pct=float(os.getenv("RISK_PER_TRADE_PCT", "2")),
        ),
        analysis=AnalysisConfig(
            default_timeframes=os.getenv("DEFAULT_TIMEFRAMES", "1H,4H,1D").split(","),
            news_count=int(os.getenv("NEWS_COUNT", "5")),
            technical_indicators=os.getenv("TECHNICAL_INDICATORS", "RSI,MACD,BB,KDJ,EMA,ATR").split(","),
        ),
        web=WebConfig(
            host=os.getenv("WEB_HOST", "0.0.0.0"),
            port=int(os.getenv("WEB_PORT", "8080")),
            debug=os.getenv("WEB_DEBUG", "false").lower() == "true",
        ),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=os.getenv("LOG_FILE", "logs/mimovision.log"),
    )

    return _config


def get_config() -> AppConfig:
    """获取全局配置"""
    if _config is None:
        return load_config()
    return _config


def load_symbols_config(path: str = "config/symbols.json") -> dict:
    """加载交易品种配置"""
    config_path = Path(path)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "crypto": {
            "BTCUSDT": {"exchange": "binance_futures", "category": "major"},
            "ETHUSDT": {"exchange": "binance_futures", "category": "major"},
            "SOLUSDT": {"exchange": "binance_futures", "category": "layer1"},
            "BNBUSDT": {"exchange": "binance_futures", "category": "exchange"},
        },
        "commodities": {
            "XAUUSD": {"exchange": "yahoo", "yahoo_symbol": "GC=F", "category": "precious_metal"},
            "XAGUSD": {"exchange": "yahoo", "yahoo_symbol": "SI=F", "category": "precious_metal"},
            "USOIL": {"exchange": "yahoo", "yahoo_symbol": "CL=F", "category": "energy"},
        },
        "indices": {
            "SPX500": {"exchange": "yahoo", "yahoo_symbol": "^GSPC", "category": "us_index"},
            "NAS100": {"exchange": "yahoo", "yahoo_symbol": "^IXIC", "category": "us_index"},
        },
    }
