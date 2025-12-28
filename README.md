# AI 股票分析 Agent

基于 LangGraph 构建的智能股票分析系统，通过多个专业 AI 代理协同工作，为股票投资提供全面的分析报告。

## 功能特性

- **多代理协作**：技术分析师、基本面分析师、舆情分析师、风控官、基金经理协同分析
- **多市场支持**：支持 A 股（6 位代码）和美股（字母代码）
- **智能数据源**：优先使用 AkShare 获取专业数据，失败自动切换至搜索引擎
- **技术指标**：自动计算 RSI、MACD 等技术指标
- **基本面分析**：评估 PE、PB、市值等财务指标
- **舆情监控**：实时搜索最新新闻并分析市场情绪
- **风险控制**：识别潜在风险并建议止损位
- **自动报告**：生成 Markdown 格式的投资决策报告

## 技术栈

- **LangGraph**：多代理工作流编排
- **LangChain**：LLM 应用框架
- **AkShare**：中国财经数据接口
- **DuckDuckGo Search**：网络搜索工具
- **OpenAI API**：大语言模型接口（支持 OpenRouter,OpenAI等）

## 安装步骤

### 1. 克隆项目

```bash
git clone https://github.com/hai426990-bot/stock_agent.git
cd stock_agent
```

### 2. 创建虚拟环境

```bash
python -m venv venv
```

### 3. 激活虚拟环境

Windows:
```bash
.\venv\Scripts\activate
```

Linux/Mac:
```bash
source venv/bin/activate
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

### API Key 配置

在 `agent_v2.py` 中配置你的 LLM API Key：

```python
llm = ChatOpenAI(
    model="mimo-v2-flash", 
    openai_api_key="your_api_key_here",
    openai_api_base="https://api.xiaomimimo.com/v1",
    temperature=0.3,
    default_headers={"HTTP-Referer": "https://github.com/stock-agent"},
    extra_body={"thinking": {"type": "enable"}}
)
```

或使用环境变量：

```bash
export OPENROUTER_API_KEY="your_api_key_here"
```

## 使用方法

### 运行程序

```bash
python agent_v2.py
```

### 输入股票代码

- **A 股**：输入 6 位数字代码（如 `600519` 贵州茅台）
- **美股**：输入字母代码（如 `AAPL` 苹果）

### 示例

```
请输入股票代码 (如 600519): 600519

🔄 [数据引擎] 正在请求 600519 数据 (源: 东方财富)...
   -> 识别为 A股，正在拉取行情...
✅ [数据引擎] AkShare 获取成功。
📈 [技术分析] 分析趋势...
🏢 [基本面] 审计估值...
📰 [舆情] 检索新闻...
🛡️ [风控] 评估风险...
👨‍💼 [基金经理] 生成最终报告...
```

### 输出报告

程序会自动生成 Markdown 格式的投资决策报告，保存为 `Report_{股票代码}_{时间戳}.md`

报告包含：
- 核心决策（BUY/SELL/HOLD）
- 详细理由（技术面、基本面、舆情）
- 风险提示
- 交易计划（建议仓位/止损）

## 项目结构

```
stock_agent/
├── agent_v2.py          # 主程序文件
├── requirements.txt     # Python 依赖
├── venv/               # 虚拟环境
└── README.md           # 项目说明文档
```

## 代理架构

```
数据采集
    ↓
技术分析师 → 分析 K 线形态、RSI、MACD
    ↓
基本面分析师 → 评估 PE、PB、财务健康度
    ↓
舆情分析师 → 搜索新闻、分析市场情绪
    ↓
风控官 → 识别风险、建议止损位
    ↓
基金经理 → 综合分析、生成最终决策
```

## 依赖说明

主要依赖包：

- `langchain-openai` - LangChain OpenAI 集成
- `langgraph` - 多代理工作流
- `langchain-community` - LangChain 社区工具
- `akshare` - 中国财经数据接口
- `pandas` - 数据处理
- `duckduckgo-search` - 网络搜索

## 注意事项

1. **API 限制**：免费 API 可能有调用次数限制，建议设置合理的 `max_tokens` 参数
2. **数据源**：AkShare 接口可能不稳定，程序会自动切换至搜索引擎模式
3. **网络环境**：确保网络连接正常，某些数据源可能需要科学上网
4. **投资风险**：本工具仅供参考，不构成投资建议，投资有风险，入市需谨慎

## 常见问题

### Q: AkShare 获取数据失败怎么办？

A: 程序会自动切换至搜索引擎模式，通过网络搜索获取股票信息。

### Q: 如何更换 LLM 模型？

A: 修改 `agent_v2.py` 中的 `model` 参数，例如：
```python
model="gpt-4o"  # 或 "claude-3.5-sonnet"
```

### Q: 支持哪些股票市场？

A: 目前支持 A 股（通过 AkShare）和美股（通过 AkShare 或搜索引擎）。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请提交 Issue 或联系项目维护者。

---

**免责声明**：本工具仅供学习和研究使用，不构成任何投资建议。股票投资存在风险，请谨慎决策。
