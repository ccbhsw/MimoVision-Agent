"""
WebSocket 管理模块
FastAPI WebSocket 连接管理：连接/断开/广播/价格告警
"""
import json
import logging
from typing import Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._subscriptions: dict[WebSocket, set] = {}  # ws -> subscribed symbols

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket):
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self._subscriptions[websocket] = set()
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """断开 WebSocket 连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self._subscriptions:
            del self._subscriptions[websocket]
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    # ------------------------------------------------------------------
    # 消息发送
    # ------------------------------------------------------------------

    async def send_personal(self, message: dict, websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")
            self.disconnect(websocket)

    async def broadcast_analysis(self, analysis_result: dict):
        """
        广播分析结果给所有连接的客户端

        Args:
            analysis_result: 分析结果字典
        """
        if not self.active_connections:
            return

        symbol = analysis_result.get("symbol", "")

        message = {
            "type": "analysis",
            "data": analysis_result,
            "timestamp": datetime.now().isoformat(),
        }

        disconnected = []
        for ws in self.active_connections:
            # 检查是否订阅了该品种
            subs = self._subscriptions.get(ws, set())
            if subs and symbol not in subs:
                continue

            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def send_price_alert(
        self,
        symbol: str,
        price: float,
        direction: str,
        threshold: float,
        message_text: str = "",
    ):
        """
        发送价格告警

        Args:
            symbol: 交易对
            price: 当前价格
            direction: up/down
            threshold: 触发阈值
            message_text: 自定义消息
        """
        alert = {
            "type": "price_alert",
            "data": {
                "symbol": symbol,
                "price": price,
                "direction": direction,
                "threshold": threshold,
                "message": message_text or f"{symbol} 价格 {direction == 'up' and '突破' or '跌破'} {threshold}",
            },
            "timestamp": datetime.now().isoformat(),
        }

        disconnected = []
        for ws in self.active_connections:
            subs = self._subscriptions.get(ws, set())
            if subs and symbol not in subs:
                continue

            try:
                await ws.send_json(alert)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    # ------------------------------------------------------------------
    # 订阅管理
    # ------------------------------------------------------------------

    def subscribe(self, websocket: WebSocket, symbols: list[str]):
        """订阅品种"""
        if websocket in self._subscriptions:
            self._subscriptions[websocket].update(symbols)
            logger.info(f"WebSocket subscribed to: {symbols}")

    def unsubscribe(self, websocket: WebSocket, symbols: list[str]):
        """取消订阅"""
        if websocket in self._subscriptions:
            self._subscriptions[websocket] -= set(symbols)

    # ------------------------------------------------------------------
    # 消息处理
    # ------------------------------------------------------------------

    async def handle_message(self, websocket: WebSocket, data: str):
        """
        处理客户端发来的消息

        消息格式:
        {"action": "subscribe", "symbols": ["BTCUSDT", "ETHUSDT"]}
        {"action": "unsubscribe", "symbols": ["BTCUSDT"]}
        {"action": "ping"}
        """
        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            await self.send_personal({"type": "error", "message": "Invalid JSON"}, websocket)
            return

        action = msg.get("action", "")

        if action == "subscribe":
            symbols = msg.get("symbols", [])
            self.subscribe(websocket, symbols)
            await self.send_personal({
                "type": "subscribed",
                "symbols": list(self._subscriptions.get(websocket, set())),
            }, websocket)

        elif action == "unsubscribe":
            symbols = msg.get("symbols", [])
            self.unsubscribe(websocket, symbols)
            await self.send_personal({
                "type": "unsubscribed",
                "symbols": symbols,
            }, websocket)

        elif action == "ping":
            await self.send_personal({"type": "pong"}, websocket)

        else:
            await self.send_personal({"type": "error", "message": f"Unknown action: {action}"}, websocket)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)
