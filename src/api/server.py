"""
REST API 服务
提供 HTTP 接口供外部调用
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from src.agents.coordinator import AgentCoordinator
from src.utils.config import get_config


def create_app() -> FastAPI:
    app = FastAPI(
        title="MimoVision-Agent API",
        description="基于小米MiMo多模态的金融智能分析系统",
        version="1.0.0",
    )

    # 静态文件
    frontend_path = Path(__file__).parent.parent.parent / "frontend"
    if frontend_path.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_path / "static")), name="static")

    coordinator = None

    @app.on_event("startup")
    async def startup():
        nonlocal coordinator
        coordinator = AgentCoordinator()

    @app.get("/", response_class=HTMLResponse)
    async def index():
        index_path = Path(__file__).parent.parent.parent / "frontend" / "index.html"
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        return "<h1>MimoVision-Agent API</h1><p>Visit /docs for API documentation.</p>"

    class AnalysisRequest(BaseModel):
        symbol: str = "BTCUSDT"
        timeframes: list[str] = ["1H", "4H", "1D"]
        include_news: bool = True
        include_charts: bool = True

    @app.post("/api/analyze")
    async def analyze(request: AnalysisRequest):
        """执行完整分析"""
        try:
            result = await coordinator.analyze(
                symbol=request.symbol,
                timeframes=request.timeframes,
                include_news=request.include_news,
                include_charts=request.include_charts,
            )
            return {
                "success": True,
                "data": {
                    "symbol": result.symbol,
                    "timestamp": result.timestamp,
                    "market_data": result.market_data,
                    "technical_indicators": result.technical_indicators,
                    "chart_analyses": result.chart_analyses,
                    "news_sentiment": result.news_sentiment,
                    "summary": result.summary,
                    "direction": result.direction,
                    "entry_zone": result.entry_zone,
                    "stop_loss": result.stop_loss,
                    "take_profit": result.take_profit,
                    "leverage": result.leverage,
                    "position_pct": result.position_pct,
                    "risk_assessment": result.risk_assessment,
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/price/{symbol}")
    async def get_price(symbol: str):
        """获取实时价格"""
        try:
            ticker = await coordinator.binance.get_ticker_price(symbol)
            return {"success": True, "data": ticker}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/market/{symbol}")
    async def get_market_data(symbol: str):
        """获取市场综合数据"""
        try:
            summary = await coordinator.binance.get_market_summary(symbol)
            return {"success": True, "data": summary}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/fear-greed")
    async def get_fear_greed():
        """获取恐慌贪婪指数"""
        try:
            data = await coordinator.news.get_fear_greed_index()
            return {"success": True, "data": data}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok", "version": "1.0.0"}

    return app
