# 股票分析代理系统

一个基于LangGraph和AI的智能股票分析系统，结合多种专业代理进行综合分析。

## 目录
- [项目介绍](#项目介绍)
- [安装说明](#安装说明)
- [使用说明](#使用说明)
- [项目结构](#项目结构)
- [贡献说明](#贡献说明)
- [许可证信息](#许可证信息)

## 项目介绍

股票分析代理系统是一个利用AI技术进行股票分析的智能系统。该项目使用LangGraph框架构建，集成了多个专业代理，包括：

- 新闻代理：分析市场新闻和事件
- 量化代理：进行技术指标分析
- 风险代理：评估投资风险
- 策略代理：制定投资策略

系统能够综合多方面信息，为用户提供全面的股票分析报告。

## 安装说明

1. 克隆项目到本地：
```bash
git clone https://github.com/your-username/stock_agent.git
cd stock_agent
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，添加必要的API密钥
```

## 使用说明

1. 运行主应用：
```bash
python main.py
```

2. 或运行Streamlit应用：
```bash
streamlit run app.py
```

3. 在应用中输入股票代码和分析需求，系统将自动调用各代理进行分析并生成报告。

## 项目结构

```
stock_agent/
├── app.py          # Streamlit Web应用
├── graph.py        # LangGraph工作流定义
├── main.py         # 主应用入口
├── state.py        # 应用状态管理
├── requirements.txt # 项目依赖
├── agents/         # 各种专业代理
│   ├── news_agent.py    # 新闻分析代理
│   ├── quant_agent.py   # 量化分析代理
│   ├── risk_agent.py    # 风险评估代理
│   └── strategy_agent.py # 策略制定代理
├── tools/          # 工具函数
├── analysis_history/ # 分析历史记录
└── test_cache.py   # 缓存测试文件
```

## 贡献说明

欢迎对本项目进行贡献！请遵循以下步骤：

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 发起Pull Request

## 许可证信息

本项目使用MIT许可证。详情请参见LICENSE文件。