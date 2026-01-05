# A股智能投资分析系统

基于LangChain和OpenAI的多Agent智能分析平台，实时展示A股投资分析过程。

## 系统架构

```
stock_agent/
├── config.py                    # 配置文件
├── base_agent.py               # Agent基类
├── stock_agent.py              # 主协调器
├── api.py                      # Web API服务
├── base_agent.py               # Agent基类
├── agents/                     # 各专业Agent
│   ├── technical_analyst.py    # 技术分析师
│   ├── fundamental_analyst.py  # 基本面分析师
│   ├── risk_manager.py         # 风险控制专家
│   ├── sentiment_analyst.py    # 市场情绪分析师
│   ├── investment_strategist.py # 投资策略师
│   ├── sector_analyst.py       # 板块分析师
│   ├── sector_technical_analyst.py # 板块技术分析师
│   ├── sector_fundamental_analyst.py # 板块基本面分析师
│   └── sector_risk_analyst.py  # 板块风险分析师
├── tools/                      # 工具模块
│   ├── data_fetcher.py        # 数据获取工具
│   ├── data_cache.py          # 数据缓存工具
│   ├── stock_analyzer.py      # 股票分析工具
│   ├── backtest_engine.py     # 回测引擎
│   ├── backtest_visualizer.py # 回测可视化
│   ├── logger.py              # 日志记录工具
│   └── performance_monitor.py # 性能监控工具
├── workflows/                  # 工作流模块
│   └── analysis_workflow.py    # 基于LangGraph的分析工作流
├── web/                        # Web界面
│   ├── templates/
│   │   └── index.html         # 主页面
│   └── static/
│       ├── css/
│       │   └── style.css      # 样式文件
│       └── js/
│           ├── modules/       # 前端功能模块
│           │   ├── chartManager.js
│           │   └── socket.js
│           └── app.js         # 前端逻辑
├── requirements.txt           # 依赖包
└── .env.example              # 环境变量示例
```

## 快速开始

### 1. 环境准备
确保已安装 Python 3.8 或更高版本

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置API密钥
复制环境变量示例文件：
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的OpenAI API密钥：
```
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4
FLASK_SECRET_KEY=your_secret_key_here
FLASK_DEBUG=True
```

### 4. 启动服务
```bash
python api.py
```

### 5. 访问系统
在浏览器中打开：`http://localhost:5000`

## 使用说明

### 基本分析流程
1. 在浏览器中打开 `http://localhost:5000`
2. 在输入框中输入6位股票代码（如：600519）
3. 点击"开始分析"按钮
4. 系统将实时展示5个Agent的分析过程
5. 分析完成后，查看各Agent的详细分析报告和最终投资策略

## 功能特性

### 核心功能
- 实时WebSocket通信，展示分析进度
- 9个专业Agent并行分析（5个股票级，4个板块级）
- 基于LangGraph的自动化分析工作流
- 美观的Web界面，支持响应式设计
- 历史分析记录功能
- 完整的分析报告格式

### 板块分析
- 行业板块综合分析
- 板块技术面、基本面、风险面全方位评估
- 板块轮动与政策趋势追踪
- 板块内龙头个股对比

### K线分析
- 支持日K、周K、月K三种周期切换
- 实时K线图表展示
- 技术指标叠加（MA5/MA10/MA20/MA30）
- 成交量分析
- 股票基本信息展示（价格、涨跌幅、成交量等）

### 技术分析图表
- 成交量趋势分析
- MACD技术指标分析
- RSI相对强弱指标
- 投资组合配置分析

## License

MIT License
