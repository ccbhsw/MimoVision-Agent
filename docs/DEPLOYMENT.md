# MimoVision-Agent 部署指南

## 环境要求

- Python 3.10+
- Node.js 18+（可选，前端开发用）
- Docker & Docker Compose（推荐部署方式）
- 网络代理（如需访问 Binance/Brave Search 等海外 API）

## 快速安装

### 方式一：Docker 部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/yourname/MimoVision-Agent-v2.git
cd MimoVision-Agent-v2

# 2. 配置环境变量
cp config/.env.example config/.env
# 编辑 config/.env，填入：
#   MIMO_API_KEY=你的MiMo API Key
#   BRAVE_API_KEY=你的Brave Search API Key
#   HTTP_PROXY=http://127.0.0.1:7890  （如需代理）

# 3. 启动
docker-compose -f docker/docker-compose.yml up -d

# 4. 访问
# 前端: http://localhost:8000
# API文档: http://localhost:8000/docs
```

### 方式二：本地安装

```bash
# 1. 克隆仓库
git clone https://github.com/yourname/MimoVision-Agent-v2.git
cd MimoVision-Agent-v2

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp config/.env.example config/.env
# 编辑 config/.env

# 5. 启动服务
python -m src.main
# 或
uvicorn src.api.server:create_app --factory --host 0.0.0.0 --port 8000
```

## 配置说明

### config/.env

```env
# MiMo API（必填）
MIMO_API_KEY=your_mimo_api_key
MIMO_BASE_URL=https://api.xiaomimimo.com/v1

# Brave Search（可选，不填则跳过新闻搜索）
BRAVE_API_KEY=your_brave_api_key

# 代理（可选）
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
NO_PROXY=localhost,127.0.0.1

# 服务端口
PORT=8000
```

### config/symbols.json

品种配置文件，定义支持的交易对及其参数。无需修改。

## 常见问题

### Q: Binance API 连接超时

A: 国内需要配置代理。在 `.env` 中设置 `HTTP_PROXY` 和 `HTTPS_PROXY`。

### Q: MiMo API 返回错误

A: 检查以下几点：
1. API Key 是否正确
2. 账户额度是否充足
3. 网络是否能访问 `api.xiaomimimo.com`

### Q: yfinance 下载失败

A: yfinance 访问 Yahoo Finance，可能需要代理或网络环境支持。非加密品种分析依赖此库。

### Q: Docker 构建慢

A: 建议使用国内镜像源：

```dockerfile
# Dockerfile 中添加
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q: 如何只分析加密货币（不用 Yahoo Finance）

A: 不影响。Yahoo Finance 模块只在分析非加密品种（如黄金 XAUUSD）时才会调用，加密货币品种全部走 Binance API。
