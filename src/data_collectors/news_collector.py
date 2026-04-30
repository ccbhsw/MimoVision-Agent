"""
新闻与市场情绪数据采集模块
集成 Brave Search API、恐慌贪婪指数、CoinGecko 等数据源
"""
import aiohttp
import logging
import feedparser
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class NewsCollector:
    """新闻情绪数据采集器"""

    def __init__(
        self,
        brave_api_key: str = "",
        proxy: str = "",
    ):
        self.brave_api_key = brave_api_key
        self.proxy = proxy
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def search_news(self, query: str, count: int = 5) -> list[dict]:
        """
        使用 Brave Search API 搜索新闻

        Returns:
            [{"title", "url", "snippet", "source", "time"}]
        """
        if not self.brave_api_key:
            logger.warning("Brave Search API key not configured, skipping news search")
            return []

        session = await self._get_session()
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "Accept-Encoding": "gzip"}
        params = {
            "q": query,
            "count": count,
            "freshness": "pd",  # 过去一天
            "search_lang": "en",
        }

        try:
            async with session.get(
                url, headers={**headers, "X-Subscription-Token": self.brave_api_key},
                params=params, proxy=self.proxy or None
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Brave Search error: {resp.status}")
                    return []

                data = await resp.json()
                results = []
                for item in data.get("web", {}).get("results", [])[:count]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", ""),
                        "source": item.get("source", ""),
                        "time": item.get("age", ""),
                    })
                return results
        except Exception as e:
            logger.error(f"Brave Search failed: {e}")
            return []

    async def get_fear_greed_index(self) -> dict:
        """
        获取恐慌贪婪指数 (alternative.me)

        Returns:
            {"value": 47, "classification": "Neutral", "timestamp": "..."}
        """
        session = await self._get_session()
        url = "https://api.alternative.me/fng/?limit=1"

        try:
            async with session.get(url, proxy=self.proxy or None) as resp:
                if resp.status != 200:
                    return {"value": 50, "classification": "Neutral", "error": "API unavailable"}

                data = await resp.json()
                item = data["data"][0]
                return {
                    "value": int(item["value"]),
                    "classification": item["value_classification"],
                    "timestamp": datetime.fromtimestamp(int(item["timestamp"])).strftime("%Y-%m-%d %H:%M"),
                }
        except Exception as e:
            logger.error(f"Fear & Greed API failed: {e}")
            return {"value": 50, "classification": "Neutral", "error": str(e)}

    async def get_crypto_news_rss(self, count: int = 10) -> list[dict]:
        """
        从 RSS 源获取加密货币新闻

        Returns:
            [{"title", "summary", "link", "source", "time"}]
        """
        rss_feeds = [
            "https://cointelegraph.com/rss",
            "https://coingape.com/feed/",
            "https://cryptoslate.com/feed/",
        ]

        all_news = []
        session = await self._get_session()

        for feed_url in rss_feeds:
            try:
                async with session.get(feed_url, proxy=self.proxy or None) as resp:
                    if resp.status != 200:
                        continue
                    text = await resp.text()
                    feed = feedparser.parse(text)

                    for entry in feed.entries[:count]:
                        all_news.append({
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", "")[:200],
                            "link": entry.get("link", ""),
                            "source": feed.feed.get("title", ""),
                            "time": entry.get("published", ""),
                        })
            except Exception as e:
                logger.warning(f"RSS feed {feed_url} failed: {e}")
                continue

        return all_news[:count]

    async def get_coingecko_global(self) -> dict:
        """获取 CoinGecko 全球市场数据"""
        session = await self._get_session()
        url = "https://api.coingecko.com/api/v3/global"

        try:
            async with session.get(url, proxy=self.proxy or None) as resp:
                if resp.status != 200:
                    return {}
                data = await resp.json()["data"]
                return {
                    "total_market_cap_usd": data["total_market_cap"].get("usd", 0),
                    "total_volume_usd": data["total_volume"].get("usd", 0),
                    "btc_dominance": data["market_cap_percentage"].get("btc", 0),
                    "eth_dominance": data["market_cap_percentage"].get("eth", 0),
                    "active_cryptos": data.get("active_cryptocurrencies", 0),
                    "market_cap_change_24h": data.get("market_cap_change_percentage_24h_usd", 0),
                }
        except Exception as e:
            logger.error(f"CoinGecko global failed: {e}")
            return {}

    async def get_symbol_news(self, symbol: str, count: int = 5) -> list[dict]:
        """获取指定品种的相关新闻"""
        # 美化搜索关键词
        name_map = {
            "BTCUSDT": "Bitcoin BTC",
            "ETHUSDT": "Ethereum ETH",
            "SOLUSDT": "Solana SOL",
            "BNBUSDT": "BNB",
            "XAUUSD": "Gold price",
            "XAGUSD": "Silver price",
        }
        query = name_map.get(symbol, symbol)
        return await self.search_news(f"{query} crypto news analysis", count)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
