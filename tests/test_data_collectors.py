"""
测试模块 - 数据采集器
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from src.data_collectors.binance_futures import BinanceFuturesCollector
from src.data_collectors.news_collector import NewsCollector


@pytest.fixture
def binance_collector():
    return BinanceFuturesCollector(api_key="test", api_secret="test")


@pytest.fixture
def news_collector():
    return NewsCollector(brave_api_key="test")


class TestBinanceFuturesCollector:
    """Binance合约数据采集器测试"""

    @pytest.mark.asyncio
    async def test_klines_parsing(self):
        """测试K线数据解析"""
        collector = BinanceFuturesCollector()

        mock_response = [
            [1700000000000, "50000", "51000", "49000", "50500", "1000",
             1700003600000, "50000000", 10000, "500", "25000000", "0"]
        ]

        with patch.object(collector, '_request', return_value=mock_response):
            klines = await collector.get_klines("BTCUSDT", "1h", limit=1)

            assert len(klines) == 1
            assert klines[0]["open"] == 50000.0
            assert klines[0]["high"] == 51000.0
            assert klines[0]["low"] == 49000.0
            assert klines[0]["close"] == 50500.0
            assert klines[0]["volume"] == 1000.0

    @pytest.mark.asyncio
    async def test_ticker_price(self):
        """测试价格获取"""
        collector = BinanceFuturesCollector()

        mock_response = {"symbol": "BTCUSDT", "price": "50000.00", "time": 1700000000000}

        with patch.object(collector, '_request', return_value=mock_response):
            ticker = await collector.get_ticker_price("BTCUSDT")
            assert ticker["symbol"] == "BTCUSDT"
            assert ticker["price"] == 50000.0


class TestNewsCollector:
    """新闻采集器测试"""

    def test_initialization(self):
        """测试初始化"""
        collector = NewsCollector(brave_api_key="test_key")
        assert collector.brave_api_key == "test_key"

    @pytest.mark.asyncio
    async def test_fear_greed_parse(self):
        """测试恐慌贪婪指数解析"""
        collector = NewsCollector()

        mock_response = {"data": [{"value": "47", "value_classification": "Neutral", "timestamp": "1700000000"}]}

        with patch.object(collector, '_get_session') as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock(return_value=False)

            session = AsyncMock()
            session.get = AsyncMock(return_value=mock_resp)
            mock_session.return_value = session

            result = await collector.get_fear_greed_index()
            assert result["value"] == 47
            assert result["classification"] == "Neutral"
