# AlphaFlow 股票分析与回测系统

AlphaFlow 是一个基于 LangGraph 和 LangChain 构建的股票分析系统。系统通过编排多个代理节点，整合了新闻资讯分析、技术指标计算、多策略回测以及风险审核流程，旨在为用户提供结构化的投资分析参考。

---

## 核心功能

### 1. 多代理协作架构
系统由四个主要代理节点组成，通过 LangGraph 进行工作流编排：
- 资讯分析代理 (NewsAgent): 负责检索市场资讯，进行行业政策解析并计算情感评分。
- 量化分析代理 (QuantAgent): 负责计算技术指标，识别 K 线形态，并执行量化回测。
- 策略生成代理 (StrategyAgent): 综合资讯与量化数据，分析不同策略的表现并生成投资分析报告。
- 风险审核代理 (RiskAgent): 负责审核报告的逻辑严密性，评估回测结果的可靠性。

### 2. 回测子系统
系统包含一个五层架构的回测模块：
- 数据层: 统一数据格式，支持 SHA-256 数据版本验证与 Parquet 本地缓存。
- 策略层: 基于 Pydantic 进行参数校验，支持自定义策略扩展。
- 引擎层: 提供向量化回测引擎，支持交易税费与滑点模拟。
- 分析层: 计算夏普比率、年化收益率、最大回撤、胜率等绩效指标。
- 持久化层: 记录回测历史数据，便于后续复盘。

### 3. 多指标组合测试
系统支持多种指标组合的逻辑验证，包括但不限于：
- 趋势与动量组合 (MACD + RSI)
- 均值回归与波动率组合 (Bollinger Bands + RSI)
- 成交量与趋势确认 (Moving Average + Volume)

---

## 快速开始

### 1. 环境配置
```bash
git clone https://github.com/your-username/stock_agent.git
cd stock_agent
python -m venv venv
source venv/bin/activate  # Windows 使用 venv\Scripts\activate
pip install -r requirements.txt
```

### 2. API 密钥设置
将 .env.example 重命名为 .env，并配置相关的 API 密钥：
```text
OPENAI_API_KEY=your_key_here
OPENAI_API_BASE=https://api.your-provider.com/v1
```

### 3. 启动方式
- Web 界面 (Streamlit):
  ```bash
  streamlit run app.py
  ```
- 命令行界面 (CLI):
  ```bash
  python main.py
  ```

---

## 项目结构

```text
stock_agent/
├── agents/              # 代理节点逻辑实现
│   ├── news_agent.py    # 资讯分析
│   ├── quant_agent.py   # 量化与回测调度
│   ├── strategy_agent.py # 报告生成
│   └── risk_agent.py    # 逻辑审核
├── backtest/            # 回测系统核心模块
│   ├── data.py          # 数据管理
│   ├── strategy.py      # 策略注册与定义
│   ├── engine.py        # 回测计算引擎
│   ├── analytics.py     # 绩效评估
│   └── persistence.py   # 结果存储
├── tools/               # 基础工具类
│   └── stock_data.py    # 数据接口封装
├── app.py               # Streamlit 界面入口
├── graph.py             # 工作流拓扑定义
└── main.py              # CLI 程序入口
```

---

## 技术栈
- 框架: LangGraph, LangChain
- 数据源: AkShare
- 数据处理: Pandas, NumPy
- UI 框架: Streamlit

---

## 许可证
本项目采用 MIT 许可证。分析结果仅供参考，不构成投资建议。
