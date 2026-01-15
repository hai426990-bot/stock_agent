# AlphaFlow 股票分析与回测系统

AlphaFlow 是一个基于 LangGraph 和 LangChain 构建的智能股票分析系统。系统通过编排多个专业代理节点，整合了新闻资讯分析、技术指标计算、多策略回测以及风险审核流程，旨在为用户提供结构化的投资分析参考。

## 核心功能

### 多智能体协作架构

系统由五个主要代理节点组成，通过 LangGraph 进行工作流编排：

- **资讯分析代理 (NewsAgent)**: 负责检索市场资讯，进行行业政策解析并计算情感评分
- **量化分析代理 (QuantAgent)**: 负责计算技术指标，识别 K 线形态，并执行量化回测
- **电报分析代理 (TelegraphAgent)**: 负责分析财联社电报等实时市场动态
- **策略生成代理 (StrategyAgent)**: 综合资讯、量化与电报数据，分析不同策略的表现并生成投资分析报告
- **风险审核代理 (RiskAgent)**: 负责审核报告的逻辑严密性，评估回测结果的可靠性

### 回测子系统

系统包含一个五层架构的回测模块：

- **数据层**: 统一数据格式，支持 SHA-256 数据版本验证与 Parquet 本地缓存
- **策略层**: 基于 Pydantic 进行参数校验，支持自定义策略扩展
- **引擎层**: 提供向量化回测引擎，支持交易税费与滑点模拟
- **分析层**: 计算夏普比率、年化收益率、最大回撤、胜率等绩效指标
- **持久化层**: 记录回测历史数据，便于后续复盘

### 多指标组合测试

系统支持多种指标组合的逻辑验证，包括但不限于：

- 趋势与动量组合 (MACD + RSI)
- 均值回归与波动率组合 (Bollinger Bands + RSI)
- 成交量与趋势确认 (Moving Average + Volume)

### 市场全览仪表盘

- **实时指数行情**: 展示主要市场指数的实时价格和涨跌幅
- **市场情绪分布**: 可视化展示上涨、平盘、下跌家数及市场宽度
- **热门板块追踪**: 实时展示领涨行业板块及其表现
- **新闻实时动态**: 同花顺新闻实时推送

## 快速开始

### 1. 环境配置

```bash
git clone https://github.com/your-username/stock_agent.git
cd stock_agent
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. API 密钥设置

将 `.env.example` 重命名为 `.env`，并配置相关的 API 密钥：

```env
OPENAI_API_KEY=your_key_here
OPENAI_API_BASE=https://api.your-provider.com/v1
MODEL_NAME=gpt-4o
```

支持的配置项：
- `OPENAI_API_KEY` / `OPENAI_API_KEY`: API 密钥
- `OPENAI_API_BASE` / `OPENAI_BASE_URL`: API 基础 URL
- `MODEL_NAME` / `OPENAI_MODEL_NAME` / `OPENAI_MODEL`: 模型名称

### 3. 启动方式

**Web 界面 (Streamlit)**:
```bash
streamlit run app.py
```

**命令行界面 (CLI)**:
```bash
python main.py --stock 600519
python main.py --stock 贵州茅台
```

## 项目结构

```
stock_agent/
├── agents/                  # 代理节点逻辑实现
│   ├── news_agent.py       # 资讯分析
│   ├── quant_agent.py      # 量化与回测调度
│   ├── telegraph_agent.py  # 电报分析
│   ├── strategy_agent.py   # 报告生成
│   └── risk_agent.py       # 逻辑审核
├── backtest/               # 回测系统核心模块
│   ├── data.py             # 数据管理
│   ├── strategy.py         # 策略注册与定义
│   ├── engine.py           # 回测计算引擎
│   ├── analytics.py        # 绩效评估
│   └── persistence.py      # 结果存储
├── tools/                  # 基础工具类
│   ├── stock_data.py       # 数据接口封装
│   ├── news_fetcher.py     # 新闻获取
│   ├── indicators.py       # 技术指标计算
│   └── backtest.py         # 回测工具
├── app.py                  # Streamlit 界面入口
├── graph.py                # 工作流拓扑定义
├── main.py                 # CLI 程序入口
├── state.py                # 工作流状态定义
├── config.py               # 配置管理
├── logger.py               # 日志系统
└── cache_manager.py        # 缓存管理
```

## 技术栈

- **框架**: LangGraph, LangChain
- **数据源**: AkShare
- **数据处理**: Pandas, NumPy
- **UI 框架**: Streamlit, Plotly
- **测试**: pytest

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
└──────┬──────┘ │(量化分析)│ │(财联社电报分析) │ │           │
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

## 注意事项

1. **数据缓存**: 系统使用本地缓存减少 API 调用，缓存文件位于项目根目录
2. **模型探测**: 首次运行会自动探测可用模型，结果缓存 24 小时
3. **风险审核**: 报告生成后会自动进行风险审核，最多修订 3 次
4. **网络连接**: 需要稳定的网络连接以获取实时市场数据

## 许可证

本项目采用 MIT 许可证。

## 免责声明

本系统提供的分析结果仅供参考，不构成投资建议。投资有风险，入市需谨慎。