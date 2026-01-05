from typing import Dict, Any
from base_agent import BaseAgent

class TechnicalAnalyst(BaseAgent):
    def __init__(self, callback=None, session_id=None):
        super().__init__('technical_analyst', callback, session_id)
    
    def _get_system_prompt(self) -> str:
        return f"""你是{self.name}，15年经验的资深A股技术分析师，专注K线形态、技术指标、趋势分析。

【分析能力】
K线形态（头肩顶底、双顶双底、三角形等）、技术指标（MACD/KDJ/RSI/BOLL/MA/VOL）、趋势判断、量价关系、支撑阻力位。

【分析方法】
1. 识别K线形态 2. 分析技术指标 3. 判断趋势阶段 4. 评估量价关系 5. 确定支撑阻力 6. 综合判断买卖点

【输出格式】
【技术面分析报告】

一、K线形态分析
• 当前形态：[描述]
• 形态意义：[技术含义]
• 形态强度：[强/中/弱]

二、技术指标分析
• MACD：[数值] - [金叉/死叉/无信号] - [买入/卖出/中性]
• KDJ：[K,D,J] - [超买/超卖/正常] - [买入/卖出/中性]
• RSI：[数值] - [超买/超卖/正常] - [买入/卖出/中性]
• 布林带：[位置] - [上/中/下轨] - [买入/卖出/中性]
• 均线系统：[MA5/10/20/60] - [多头/空头/纠缠]

三、趋势分析
• 当前趋势：[上升/下降/横盘]
• 趋势强度：[强/中/弱]
• 趋势阶段：[初期/中期/末期/反转]

四、量价关系
• 量能状态：[放量/缩量/正常]
• 量价配合：[健康/背离]
• 资金态度：[积极/谨慎/观望]

五、关键价位
• 支撑位：[价位]
• 阻力位：[价位]
• 止损位：[价位]

六、技术面结论
• 技术面评级：[强烈买入/买入/持有/卖出/强烈卖出]
• 操作建议：[具体建议]
• 目标价位：[短期/中期目标价]
• 风险提示：[技术面风险]

【注意】基于客观数据，避免主观臆测，关注指标共振，警惕假突破，结合大盘环境。
"""
    
    def _prepare_input(self, stock_data: Dict[str, Any]) -> str:
        stock_code = stock_data.get('stock_code', '')
        stock_name = stock_data.get('stock_name', '')
        current_price = stock_data.get('current_price', '')
        market_cap = stock_data.get('market_cap', '')
        pe_ratio = stock_data.get('pe_ratio', '')
        pb_ratio = stock_data.get('pb_ratio', '')
        turnover_rate = stock_data.get('turnover_rate', '')
        volume_ratio = stock_data.get('volume_ratio', '')
        
        # 从技术指标获取数据，确保有默认值
        technical_indicators = stock_data.get('technical_indicators', {})
        
        # 从kline_data获取最新的价格数据
        kline_data = stock_data.get('kline_data', [])
        latest_kline = kline_data[-1] if kline_data else {}
        high = latest_kline.get('最高', '')
        low = latest_kline.get('最低', '')
        volume = latest_kline.get('成交量', '')
        
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
总市值：{market_cap}
市盈率：{pe_ratio}
市净率：{pb_ratio}

【技术指标数据】
均线系统：{technical_indicators.get('ma', {})}
MACD指标：{technical_indicators.get('macd', {})}
KDJ指标：{technical_indicators.get('kdj', {})}
RSI指标：{technical_indicators.get('rsi', {})}
布林带：{technical_indicators.get('boll', {})}
量价分析：{technical_indicators.get('volume_ratio', {})}
K线形态：{technical_indicators.get('patterns', {})}
支撑阻力：{technical_indicators.get('support_resistance', {})}
波动率：{technical_indicators.get('volatility', {})}
风险指标：{technical_indicators.get('risk_metrics', {})}

请根据以上数据，按照系统提示的格式输出完整的技术面分析报告。
"""
        return input_text
    
    def _parse_result(self, result: str) -> Dict[str, Any]:
        return {
            'analysis_type': 'technical',
            'content': result
        }
