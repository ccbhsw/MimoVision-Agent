"""
MiMo API 封装客户端
基于 OpenAI 兼容接口调用小米 MiMo 系列模型
"""
import aiohttp
import json
import base64
import logging
from typing import Optional, AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MiMoMessage:
    """MiMo 消息格式"""
    role: str  # system, user, assistant
    content: str | list  # 文本或多模态内容列表
    reasoning_content: Optional[str] = None


@dataclass
class MiMoResponse:
    """MiMo 响应格式"""
    content: str
    reasoning: Optional[str] = None
    model: str = ""
    usage: dict = field(default_factory=dict)
    finish_reason: str = ""


class MiMoClient:
    """
    小米 MiMo API 客户端

    支持三种模型:
    - mimo-v2.5-pro: 深度推理，用于策略决策
    - mimo-v2-omni: 多模态理解，用于图表/图片/音频分析
    - mimo-v2-flash: 快速推理，用于简单任务
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.xiaomimimo.com/v1",
        default_model: str = "mimo-v2.5-pro",
        timeout: int = 120,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_text_content(self, text: str) -> list:
        """构建纯文本消息内容"""
        return [{"type": "text", "text": text}]

    def _build_image_content(self, text: str, image_path: str | bytes) -> list:
        """构建图片+文本的多模态消息内容"""
        content = [{"type": "text", "text": text}]

        if isinstance(image_path, bytes):
            b64 = base64.b64encode(image_path).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"}
            })
        else:
            path = Path(image_path)
            if path.exists():
                b64 = base64.b64encode(path.read_bytes()).decode()
                ext = path.suffix.lstrip(".") or "png"
                mime = f"image/{ext}" if ext in ("png", "jpg", "jpeg", "gif", "webp") else "image/png"
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}
                })
            else:
                # URL 形式
                content.append({
                    "type": "image_url",
                    "image_url": {"url": str(image_path)}
                })

        return content

    def _build_audio_content(self, text: str, audio_path: str | bytes) -> list:
        """构建音频+文本的多模态消息内容"""
        content = [{"type": "text", "text": text}]

        if isinstance(audio_path, bytes):
            b64 = base64.b64encode(audio_path).decode()
            content.append({
                "type": "audio_url",
                "audio_url": {"url": f"data:audio/wav;base64,{b64}"}
            })
        else:
            content.append({
                "type": "audio_url",
                "audio_url": {"url": str(audio_path)}
            })

        return content

    def _build_video_content(self, text: str, video_url: str) -> list:
        """构建视频+文本的多模态消息内容"""
        return [
            {"type": "text", "text": text},
            {"type": "video_url", "video_url": {"url": video_url}}
        ]

    async def chat(
        self,
        messages: list[MiMoMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: Optional[list] = None,
        tool_choice: Optional[str] = None,
    ) -> MiMoResponse | AsyncIterator[str]:
        """
        发送聊天请求

        Args:
            messages: 消息列表
            model: 模型名称，默认使用 default_model
            temperature: 温度参数
            max_tokens: 最大输出token数
            stream: 是否流式输出
            tools: 工具定义列表
            tool_choice: 工具选择策略
        """
        model = model or self.default_model

        payload = {
            "model": model,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content if isinstance(m.content, list) else m.content,
                }
                for m in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        url = f"{self.base_url}/chat/completions"

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    if stream:
                        return self._stream_response(session, url, payload)
                    else:
                        async with session.post(url, headers=self._headers(), json=payload) as resp:
                            if resp.status != 200:
                                error_text = await resp.text()
                                logger.error(f"MiMo API error ({resp.status}): {error_text}")
                                if attempt < self.max_retries - 1:
                                    continue
                                raise Exception(f"MiMo API error: {resp.status} - {error_text}")

                            data = await resp.json()
                            choice = data["choices"][0]
                            message = choice["message"]

                            return MiMoResponse(
                                content=message.get("content", ""),
                                reasoning=message.get("reasoning_content"),
                                model=data.get("model", model),
                                usage=data.get("usage", {}),
                                finish_reason=choice.get("finish_reason", ""),
                            )
            except aiohttp.ClientError as e:
                logger.warning(f"MiMo API connection error (attempt {attempt+1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise

    async def _stream_response(self, session, url, payload) -> AsyncIterator[str]:
        """流式响应处理"""
        async with session.post(url, headers=self._headers(), json=payload) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"MiMo API stream error: {resp.status} - {error_text}")

            async for line in resp.content:
                line = line.decode().strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    delta = data["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]
                    if "reasoning_content" in delta:
                        yield f"[REASONING] {delta['reasoning_content']}"
                except json.JSONDecodeError:
                    continue

    async def analyze_chart(
        self,
        image_path: str | bytes,
        symbol: str,
        timeframe: str,
        prompt: Optional[str] = None,
    ) -> MiMoResponse:
        """
        使用 MiMo-V2-Omni 分析K线图表

        Args:
            image_path: 图片路径或字节数据
            symbol: 交易对 (如 BTCUSDT)
            timeframe: 时间周期
            prompt: 自定义分析提示
        """
        system_prompt = (
            "你是一个专业的加密货币技术分析师。你拥有丰富的合约交易经验。"
            "请仔细观察提供的K线图表，分析以下内容：\n"
            "1. 当前趋势方向（多头/空头/震荡）\n"
            "2. 关键支撑位和阻力位\n"
            "3. 技术指标信号（RSI、MACD、布林带、KDJ等图表上显示的指标）\n"
            "4. 成交量变化\n"
            "5. 潜在的入场和出场点\n"
            "请用简洁专业的中文回答。"
        )

        user_prompt = prompt or f"请分析 {symbol} {timeframe} 周期的K线图表，给出你的技术分析判断。"

        messages = [
            MiMoMessage(role="system", content=system_prompt),
            MiMoMessage(
                role="user",
                content=self._build_image_content(user_prompt, image_path),
            ),
        ]

        return await self.chat(
            messages=messages,
            model="mimo-v2-omni",
            temperature=0.3,
            max_tokens=2048,
        )

    async def reason_strategy(
        self,
        market_data: dict,
        technical_analysis: str,
        news_sentiment: str,
        chart_analysis: str,
    ) -> MiMoResponse:
        """
        使用 MiMo-V2.5-Pro 进行策略推理

        Args:
            market_data: 市场数据字典
            technical_analysis: 技术分析结果
            news_sentiment: 新闻情绪分析结果
            chart_analysis: 图表视觉分析结果
        """
        system_prompt = (
            "你是一个专业的合约交易策略分析师。基于以下多维度信息：\n"
            "1. 市场数据（价格、资金费率、持仓量、多空比）\n"
            "2. 技术指标分析\n"
            "3. 多周期K线图表视觉分析\n"
            "4. 新闻面和市场情绪\n\n"
            "请给出综合分析报告，包含：\n"
            "- 市场概况（一句话总结）\n"
            "- 多周期趋势判断\n"
            "- 方向建议（做多/做空/观望）\n"
            "- 入场区间\n"
            "- 止损价位\n"
            "- 止盈目标\n"
            "- 建议杠杆\n"
            "- 仓位比例\n"
            "- 风险提示\n\n"
            "请用中文回答，简洁专业。"
        )

        user_content = (
            f"## 市场数据\n"
            f"当前价格: {market_data.get('price', 'N/A')}\n"
            f"24h涨跌: {market_data.get('change_24h', 'N/A')}%\n"
            f"资金费率: {market_data.get('funding_rate', 'N/A')}\n"
            f"持仓量: {market_data.get('open_interest', 'N/A')}\n"
            f"多空比: {market_data.get('long_short_ratio', 'N/A')}\n\n"
            f"## 技术指标分析\n{technical_analysis}\n\n"
            f"## K线图表分析\n{chart_analysis}\n\n"
            f"## 新闻与市场情绪\n{news_sentiment}"
        )

        messages = [
            MiMoMessage(role="system", content=system_prompt),
            MiMoMessage(role="user", content=user_content),
        ]

        return await self.chat(
            messages=messages,
            model="mimo-v2.5-pro",
            temperature=0.4,
            max_tokens=4096,
        )

    async def analyze_news_sentiment(
        self,
        news_items: list[dict],
        symbol: str,
    ) -> MiMoResponse:
        """
        使用 MiMo-V2-Flash 快速分析新闻情绪

        Args:
            news_items: 新闻列表 [{title, summary, source, time}]
            symbol: 交易对
        """
        news_text = "\n".join([
            f"- [{n.get('time', '')}] {n.get('title', '')} ({n.get('source', '')}): {n.get('summary', '')}"
            for n in news_items
        ])

        system_prompt = (
            f"你是加密货币市场情绪分析专家。请分析以下关于 {symbol} 的新闻，"
            "给出每条新闻的情绪评分（-5到+5，-5极度恐慌，+5极度贪婪），"
            "然后给出整体市场情绪评分和判断。"
        )

        messages = [
            MiMoMessage(role="system", content=system_prompt),
            MiMoMessage(role="user", content=f"新闻列表：\n{news_text}"),
        ]

        return await self.chat(
            messages=messages,
            model="mimo-v2-flash",
            temperature=0.2,
            max_tokens=2048,
        )

    async def quick_analysis(self, prompt: str) -> MiMoResponse:
        """快速分析（使用Flash模型）"""
        messages = [MiMoMessage(role="user", content=prompt)]
        return await self.chat(
            messages=messages,
            model="mimo-v2-flash",
            temperature=0.3,
            max_tokens=1024,
        )

    async def chain_of_thought(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "mimo-v2.5-pro",
        max_tokens: int = 4000,
        temperature: float = 0.3,
    ) -> MiMoResponse:
        """
        Chain-of-Thought推理调用

        在prompt前添加CoT引导，让模型逐步推理
        """
        cot_system = (
            (system_prompt + "\n\n" if system_prompt else "")
            + "请使用Chain-of-Thought逐步推理。"
            "每一步都要：\n"
            "1. 明确当前分析目标\n"
            "2. 列出支持/反对的证据\n"
            "3. 给出中间结论和置信度\n"
            "4. 标记发现的矛盾\n"
            "最后给出综合结论。"
        )
        messages = [
            MiMoMessage(role="system", content=cot_system),
            MiMoMessage(role="user", content=prompt),
        ]
        return await self.chat(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def multi_model_vote(
        self,
        prompt: str,
        models: list[str] = None,
        system_prompt: str = "",
        temperature: float = 0.4,
        max_tokens: int = 2000,
    ) -> dict:
        """
        多模型投票：让多个模型同时回答同一问题

        Returns:
            {responses, consensus_direction, agreement_pct}
        """
        import asyncio as _asyncio

        models = models or ["mimo-v2.5-pro", "mimo-v2-flash"]
        messages = []
        if system_prompt:
            messages.append(MiMoMessage(role="system", content=system_prompt))
        messages.append(MiMoMessage(role="user", content=prompt))

        tasks = {
            m: self.chat(messages=messages, model=m, temperature=temperature, max_tokens=max_tokens)
            for m in models
        }

        responses = {}
        for model, task in tasks.items():
            try:
                responses[model] = await task
            except Exception as e:
                logger.warning(f"Model {model} failed in vote: {e}")

        directions = {}
        for model, resp in responses.items():
            t = resp.content.lower()
            if "做多" in resp.content or "long" in t or "买入" in resp.content:
                directions[model] = "long"
            elif "做空" in resp.content or "short" in t or "卖出" in resp.content:
                directions[model] = "short"
            else:
                directions[model] = "wait"

        counts = {}
        for d in directions.values():
            counts[d] = counts.get(d, 0) + 1
        consensus = max(counts, key=counts.get) if counts else "wait"
        agreement = counts.get(consensus, 0) / len(directions) if directions else 0

        best_model = "mimo-v2.5-pro" if "mimo-v2.5-pro" in responses else next(iter(responses))
        return {
            "responses": responses,
            "directions": directions,
            "consensus_direction": consensus,
            "agreement_pct": round(agreement * 100, 1),
            "best_response": responses[best_model],
        }

    async def structured_output(
        self,
        prompt: str,
        output_schema: dict,
        model: str = "mimo-v2.5-pro",
        temperature: float = 0.2,
    ) -> dict:
        """
        结构化输出：让模型按指定schema输出JSON
        """
        import json

        schema_str = json.dumps(output_schema, ensure_ascii=False, indent=2)
        system = (
            "你必须严格按照提供的JSON Schema输出结果。\n"
            f"Schema:\n{schema_str}\n\n"
            "只输出JSON，不要输出任何其他内容。"
        )
        messages = [
            MiMoMessage(role="system", content=system),
            MiMoMessage(role="user", content=prompt),
        ]
        response = await self.chat(
            messages=messages, model=model,
            temperature=temperature, max_tokens=2000,
        )

        try:
            text = response.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            return {"raw_response": response.content, "parse_error": True}

    async def analyze_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        model: str = "mimo-v2.5-pro",
        max_rounds: int = 5,
    ) -> dict:
        """
        工具调用：让模型使用工具完成任务（多轮）
        """
        messages = [
            MiMoMessage(role="system", content="你可以使用工具来完成任务。请按需调用工具。"),
            MiMoMessage(role="user", content=prompt),
        ]

        tool_calls_log = []
        for round_idx in range(max_rounds):
            response = await self.chat(
                messages=messages, model=model,
                tools=tools, temperature=0.3, max_tokens=3000,
            )

            if response.finish_reason != "tool_calls":
                break

            tool_calls_log.append({
                "round": round_idx + 1,
                "model": response.model,
            })

            messages.append(MiMoMessage(
                role="assistant",
                content=response.content,
            ))

        return {
            "final_response": response.content,
            "tool_rounds": len(tool_calls_log),
            "tool_calls_log": tool_calls_log,
            "model": response.model,
        }
