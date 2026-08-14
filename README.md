# AlphaFlow 股票分析与回测系统

AlphaFlow 是一个基于 LangGraph 和 LangChain 构建的智能股票分析系统。系统通过编排多个专业代理节点，整合了新闻资讯分析、技术指标计算、多策略回测以及风险审核流程，旨在为用户提供结构化的投资分析参考。

## 核心功能

### 多智能体协作架构

系统由五个主要代理节点组成，通过 LangGraph 进行工作流编排：

- **资讯分析代理 (NewsAgent)**: 负责检索市场资讯，进行行业政策解析并计算情感评分
- **量化分析代理 (QuantAgent)**: 负责计算技术指标，识别 K 线形态，并执行量化回测
- **电报分析代理 (TelegraphAgent)**: 负责分析同花顺实时新闻动态（并行分析，不阻塞流水线）
- **策略生成代理 (StrategyAgent)**: 综合资讯、量化与电报数据，分析不同策略的表现并生成投资分析报告
- **风险审核代理 (RiskAgent)**: 负责审核报告的逻辑严密性，评估回测结果的可靠性（带熔断与修订循环）

### 回测子系统

系统包含一个五层架构的回测模块：

- **数据层**: 统一数据格式，支持 SHA-256 数据版本验证、Parquet 本地缓存（价格/宏观/指数数据均缓存，避免重复拉取），东方财富数据源不可用时自动回退到新浪源
- **策略层**: 基于 Pydantic 进行参数校验，支持自定义策略扩展（35 个注册策略，含 ATR 追踪止损、突破止损、回调买入、年线做多等风控策略）
- **引擎层**: 提供向量化回测引擎，支持交易税费与滑点模拟
- **分析层**: 计算夏普比率、年化收益率、最大回撤、胜率等绩效指标
- **持久化层**: 记录回测历史数据，便于后续复盘

### 多指标组合测试

系统支持多种指标组合的逻辑验证，包括但不限于：

- 趋势与动量组合 (MACD + RSI)
- 均值回归与波动率组合 (Bollinger Bands + RSI)
- 成交量与趋势确认 (Moving Average + Volume)

### Web 界面 (Django + React)

- **REST API** (django-ninja) + **SSE 实时进度流**（多节点事件推送、断线重连续传）
- **市场全览仪表盘**: 实时指数行情、市场情绪分布、热门板块追踪
- **智能分析页**: 输入股票/板块，实时查看多智能体分析进度与报告
- **配置面板**: 模型、LLM 参数、回测参数在线配置

## 快速开始

### 1. 环境配置

```bash
git clone https://github.com/your-username/stock_agent.git
cd stock_agent
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. API 密钥设置

将 `.env.example` 重命名为 `.env`，并配置相关的 API 密钥：

```env
OPENAI_API_KEY=your_key_here
OPENAI_API_BASE=https://api.your-provider.com/v1
MODEL_NAME=gpt-4o
```

### 3. 启动方式

**后端 API (Django + uvicorn)**:
```bash
cd backend
python manage.py migrate          # 首次运行：初始化数据库
cd ..
python -m uvicorn backend.backend.asgi:application --reload
```

**前端 (Vite 开发服务器，另开一个终端)**:
```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173（已配置 /api 代理到 8000）
```

**生产部署**: 先 `npm run build` 构建前端，再启动 uvicorn，Django 会直接伺服 `backend/staticfiles/frontend/` 下的 SPA。

**命令行界面 (CLI)**:
```bash
python main.py --stock 600519
python main.py --stock 贵州茅台
```

## 项目结构

```
stock_agent/
├── agents/                  # 代理节点逻辑实现
│   ├── llm.py              # 共享 LLM 工厂（4 个 Agent 统一使用）
│   ├── news_agent.py       # 资讯分析
│   ├── quant_agent.py      # 量化与回测调度
│   ├── telegraph_agent.py  # 同花顺新闻分析（并行）
│   ├── strategy_agent.py   # 报告生成
│   └── risk_agent.py       # 逻辑审核（带回退解析）
├── backtest/               # 回测系统核心模块
│   ├── data.py             # 数据管理（含宏观/指数缓存）
│   ├── strategy.py         # 策略注册与定义
│   ├── engine.py           # 回测计算引擎
│   ├── analytics.py        # 绩效评估
│   └── persistence.py      # 结果存储
├── tools/                  # 基础工具类
│   ├── stock_data.py       # 数据接口封装（TTL 缓存）
│   ├── news_fetcher.py     # 同花顺新闻获取
│   ├── news_sources.py     # RSS/Reddit/X 多源
│   ├── indicators.py       # 技术指标计算
│   └── retry.py            # 共享重试装饰器
├── backend/                # Django + django-ninja 后端
│   ├── backend/            # 项目配置 (settings/urls/asgi/wsgi/bootstrap)
│   ├── analysis/           # 分析任务 API + orchestrator (SSE 流)
│   ├── market/             # 行情仪表盘 API
│   ├── configapp/          # 配置 API
│   └── core/               # 健康检查
├── frontend/               # React + Vite + TypeScript 前端
├── graph.py                # 工作流拓扑定义
├── main.py                 # CLI 程序入口
├── state.py                # 工作流状态定义
├── config.py               # 配置管理（4 层优先级）
├── logger.py               # 日志系统
└── tests/                  # pytest 测试（agents/backtest/tools/backend）
```

## 技术栈

- **框架**: LangGraph, LangChain, Django, django-ninja
- **前端**: React, Vite, TypeScript, TanStack Query
- **数据源**: AkShare
- **数据处理**: Pandas, NumPy
- **测试**: pytest, pytest-django

## 工作流程

```
┌─────────────┐
│  Supervisor │
│   (调度)    │
└──────┬──────┘
       │
       ├──────────────┬──────────────┬──────────────┐
       │              │              │              │
┌──────▼──────┐ ┌────▼─────┐ ┌────▼──────┐ ┌────▼──────┐
│ News Agent  │ │Quant     │ │Telegraph  │ │           │
│ (资讯分析)  │ │Agent     │ │Agent      │ │           │
└──────┬──────┘ │(量化分析)│ │(新闻分析) │ │           │
       │        └────┬─────┘ └────┬──────┘ │           │
       └─────────────┼─────────────┤         │           │
                     │             │         │           │
              ┌──────▼─────────────▼──────┐  │           │
              │   Strategy Agent          │  │           │
              │   (策略生成)               │  │           │
              └──────┬─────────────┬──────┘  │           │
                     │             │         │           │
              ┌──────▼─────────────▼──────┐  │           │
              │    Risk Agent             │  │           │
              │    (风险审核)              │  │           │
              └──────┬─────────────┬──────┘  │           │
                     │             │         │           │
               需修订?           通过       │           │
                     │             │         │           │
                     └─────────────┴─────────┘           │
                               │                         │
                          ┌────▼─────┐                   │
                          │   END    │                   │
                          └──────────┘                   │
```

## 配置说明

### 模型配置

系统支持自动模型探测，按配置列表顺序尝试连接 API，返回第一个可用的模型。

在 `.env` 文件中配置支持的模型列表：
```env
SUPPORTED_MODELS=gpt-4o,gpt-4-turbo,gpt-3.5-turbo
```

### 回测参数

- **回测回溯天数**: 默认 365 天
- **初始资金**: 默认 100,000 元
- **交易税费**: 可配置
- **滑点模拟**: 可配置

### LLM 参数

- **Temperature**: 控制生成随机性，默认 0.3
- **Max Tokens**: 最大生成长度，默认 8192
- **深度思考模式**: 开启后启用 chain-of-thought 推理

## 开发

```bash
# 运行全部测试（agents / backtest / tools / backend API / SSE）
.venv/Scripts/python -m pytest

# 批量回测评估：在多个代表性股票上排名全部策略（默认 12 只股票，近 2 年）
.venv/Scripts/python scripts/benchmark_strategies.py
# 自定义：--days 1460  (4年)   --stocks 600519,000858   --top 15
# 结果输出到 scripts/benchmark_results.csv

# 前端类型检查与构建
cd frontend && npx tsc -b && npm run build
```

## 注意事项

1. **数据缓存**: 系统使用本地缓存减少 API 调用，缓存文件位于项目根目录（`.akshare_cache.json`、`.backtest_cache/`）
2. **并发分析**: 后端同时最多运行 2 个分析任务（超出返回 429）
3. **风险审核**: 报告生成后会自动进行风险审核，最多修订 3 次
4. **网络连接**: 需要稳定的网络连接以获取实时市场数据

## 许可证

本项目采用 MIT 许可证。

## 免责声明

本系统提供的分析结果仅供参考，不构成投资建议。投资有风险，入市需谨慎。
