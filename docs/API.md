# MimoVision-Agent API 文档

## 基础信息

- 基地址: `http://localhost:8000`
- 数据格式: JSON
- 编码: UTF-8

---

## 接口列表

### 1. 执行完整分析

**POST** `/api/analyze`

对指定品种执行完整的多维度分析流程。

**请求体:**

```json
{
  "symbol": "BTCUSDT",
  "timeframes": ["1H", "4H", "1D"],
  "include_news": true,
  "include_charts": true
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 交易对，如 BTCUSDT, ETHUSDT, XAUUSD |
| timeframes | string[] | 是 | 时间周期: 1H, 4H, 1D, 1W |
| include_news | boolean | 否 | 是否包含新闻分析（默认true） |
| include_charts | boolean | 否 | 是否包含图表分析（默认true） |

**响应示例:**

```json
{
  "success": true,
  "data": {
    "symbol": "BTCUSDT",
    "timestamp": "2026-05-01 10:00:00",
    "direction": "long",
    "entry_zone": "50200-50500",
    "stop_loss": 49200,
    "take_profit": 52000,
    "leverage": 15,
    "position_pct": 8.5,
    "market_data": {
      "price": 50350,
      "change_24h": 1.23,
      "funding_rate": 0.0001,
      "open_interest": 12345.6
    },
    "technical_indicators": {
      "trend": "bullish",
      "rsi": 58.2,
      "macd": 150.5,
      "macd_cross": "bullish"
    },
    "summary": "综合分析：多周期看多...",
    "risk_assessment": {}
  }
}
```

---

### 2. 获取实时价格

**GET** `/api/price/{symbol}`

**路径参数:**

| 参数 | 说明 |
|------|------|
| symbol | 交易对名称 (BTCUSDT, ETHUSDT 等) |

**响应示例:**

```json
{
  "success": true,
  "data": {
    "symbol": "BTCUSDT",
    "price": 50350.5,
    "time": "2026-05-01 10:00:00"
  }
}
```

---

### 3. 获取市场综合数据

**GET** `/api/market/{symbol}`

返回价格、资金费率、持仓量、多空比等综合数据。

**响应示例:**

```json
{
  "success": true,
  "data": {
    "symbol": "BTCUSDT",
    "price": 50350.5,
    "change_24h": 1.23,
    "high_24h": 51000,
    "low_24h": 49500,
    "volume_24h": 150000,
    "funding_rate": 0.0001,
    "open_interest": 12345.6,
    "long_short_ratio": 1.35,
    "timestamp": "2026-05-01 10:00:00"
  }
}
```

---

### 4. 获取恐慌贪婪指数

**GET** `/api/fear-greed`

**响应示例:**

```json
{
  "success": true,
  "data": {
    "value": 47,
    "classification": "Neutral",
    "timestamp": "2026-05-01 08:00"
  }
}
```

---

### 5. 健康检查

**GET** `/api/health`

**响应:**

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

### 6. WebSocket 实时推送

**连接地址:** `ws://localhost:8000/ws`

**客户端发送消息格式:**

```json
{"action": "subscribe", "symbols": ["BTCUSDT", "ETHUSDT"]}
{"action": "unsubscribe", "symbols": ["BTCUSDT"]}
{"action": "ping"}
```

**服务端推送消息类型:**

- `analysis` - 分析结果
- `price_alert` - 价格告警
- `pong` - 心跳响应
- `subscribed` - 订阅确认
- `error` - 错误消息

---

## 错误格式

所有接口在出错时返回:

```json
{
  "detail": "错误描述信息"
}
```

HTTP 状态码:
- `200` - 成功
- `400` - 请求参数错误
- `500` - 服务器内部错误（通常是上游API超时）
