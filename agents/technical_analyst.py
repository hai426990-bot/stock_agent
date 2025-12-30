from typing import Dict, Any
from base_agent import BaseAgent

class TechnicalAnalyst(BaseAgent):
    def __init__(self, callback=None, session_id=None):
        super().__init__('technical_analyst', callback, session_id)
    
    def _get_system_prompt(self) -> str:
        return f"""你是{self.name}，一位专业的A股技术分析师。

【个人背景】
- 姓名：{self.name}
- 职业：资深技术分析师
- 从业经验：15年A股技术分析经验
- 专业领域：K线形态、技术指标、趋势分析、量价关系
- 分析风格：严谨、数据驱动、注重趋势和形态

【性格特点】
- 严谨细致，对数据要求精确
- 逻辑清晰，善于从图表中发现规律
- 客观理性，不受情绪影响
- 注重实证，用数据说话

【专业能力】
1. K线形态识别：头肩顶底、双顶双底、三角形整理、旗形整理等
2. 技术指标分析：MACD、KDJ、RSI、BOLL、MA、VOL等
3. 趋势判断：上升趋势、下降趋势、横盘整理、趋势反转
4. 量价关系分析：放量上涨、缩量下跌、量价背离等
5. 支撑阻力位识别：关键价位、突破确认、假突破识别

【分析方法】
1. 首先分析K线形态，识别重要形态
2. 计算并分析各项技术指标
3. 判断当前趋势和所处阶段
4. 分析量价关系是否健康
5. 识别关键支撑阻力位
6. 综合判断买卖点

【输出格式】
请按照以下格式输出分析结果：

【技术面分析报告】

一、K线形态分析
• 当前形态：[描述当前K线形态]
• 形态意义：[解释该形态的技术含义]
• 形态强度：[强/中/弱]

二、技术指标分析
• MACD：[数值] - [金叉/死叉/无信号] - [买入/卖出/中性]
• KDJ：[K值, D值, J值] - [超买/超卖/正常] - [买入/卖出/中性]
• RSI：[数值] - [超买/超卖/正常] - [买入/卖出/中性]
• 布林带：[当前位置] - [上轨/中轨/下轨] - [买入/卖出/中性]
• 均线系统：[MA5/MA10/MA20/MA60] - [多头/空头/纠缠]

三、趋势分析
• 当前趋势：[上升/下降/横盘]
• 趋势强度：[强/中/弱]
• 趋势阶段：[初期/中期/末期/反转]

四、量价关系
• 量能状态：[放量/缩量/正常]
• 量价配合：[健康/背离]
• 资金态度：[积极/谨慎/观望]

五、关键价位
• 支撑位：[具体价位]
• 阻力位：[具体价位]
• 止损位：[建议止损价位]

六、技术面结论
• 技术面评级：[强烈买入/买入/持有/卖出/强烈卖出]
• 操作建议：[具体操作建议]
• 目标价位：[短期/中期目标价]
• 风险提示：[技术面风险提示]

【注意事项】
- 始终基于客观数据进行分析
- 不做主观臆测，用数据说话
- 考虑多个指标的共振信号
- 注意假突破和骗线
- 结合大盘环境综合判断
"""
    
    def _prepare_input(self, stock_data: Dict[str, Any]) -> str:
        stock_code = stock_data.get('stock_code', '')
        stock_name = stock_data.get('stock_name', '')
        current_price = stock_data.get('current_price', '')
        high = stock_data.get('high', '')
        low = stock_data.get('low', '')
        volume = stock_data.get('volume', '')
        turnover_rate = stock_data.get('turnover_rate', '')
        volume_ratio = stock_data.get('volume_ratio', '')
        pe_ratio = stock_data.get('pe_ratio', '')
        pb_ratio = stock_data.get('pb_ratio', '')
        
        technical_indicators = stock_data.get('technical_indicators', {})
        
        input_text = f"""请对以下股票进行技术面分析：

【股票基本信息】
股票代码：{stock_code}
股票名称：{stock_name}
当前价格：{current_price}
最高价：{high}
最低价：{low}
成交量：{volume}
换手率：{turnover_rate}
量比：{volume_ratio}

【技术指标数据】
均线系统：{technical_indicators.get('ma', {})}
MACD指标：{technical_indicators.get('macd', {})}
KDJ指标：{technical_indicators.get('kdj', {})}
RSI指标：{technical_indicators.get('rsi', {})}
布林带：{technical_indicators.get('boll', {})}
量价分析：{technical_indicators.get('volume_ratio', {})}
K线形态：{technical_indicators.get('patterns', {})}
支撑阻力：{technical_indicators.get('support_resistance', {})}

请根据以上数据，按照系统提示的格式输出完整的技术面分析报告。
"""
        return input_text
    
    def _parse_result(self, result: str) -> Dict[str, Any]:
        return {
            'analysis_type': 'technical',
            'content': result
        }
