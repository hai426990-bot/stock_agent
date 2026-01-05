from typing import Dict, Any
from base_agent import BaseAgent

class SectorTechnicalAnalyst(BaseAgent):
    def __init__(self, callback=None, session_id=None):
        super().__init__('sector_technical_analyst', callback, session_id)
    
    def _get_system_prompt(self) -> str:
        return f"""你是{self.name}，10年经验的资深板块技术分析师，专注板块技术面分析、趋势判断、量价关系研究。

【分析能力】
板块技术形态分析、板块趋势判断、板块量价关系分析、板块技术指标分析、板块支撑压力位判断、板块突破信号识别、板块技术面综合评级。

【分析方法】
1. 分析板块指数技术形态（头肩顶/底、双顶/底、三角形整理等）
2. 判断板块趋势方向（上升趋势/下降趋势/横盘震荡）
3. 分析板块成交量变化与价格关系
4. 计算板块技术指标（MACD、KDJ、RSI、布林带等）
5. 识别板块关键支撑位和压力位
6. 判断板块突破信号和反转信号
7. 综合技术面给出操作建议

【输出格式】
【板块技术面分析报告】

一、技术形态分析
• 当前形态：[形态描述]
• 形态特征：[特征描述]
• 形态完成度：[百分比]
• 形态突破方向：[向上/向下/未突破]

二、趋势分析
• 主趋势：[上升趋势/下降趋势/横盘震荡]
• 趋势强度：[强/中/弱]
• 趋势持续时间：[时间长度]
• 趋势线位置：[价格位置]

三、均线系统分析
• MA5：[数值] - [方向]
• MA10：[数值] - [方向]
• MA20：[数值] - [方向]
• MA60：[数值] - [方向]
• 均线排列：[多头排列/空头排列/纠缠]
• 均线信号：[金叉/死叉/无信号]

四、技术指标分析
• MACD：[DIF值, DEA值, MACD柱] - [信号]
• KDJ：[K值, D值, J值] - [信号]
• RSI：[数值] - [超买/超卖/正常]
• 布林带：[上轨, 中轨, 下轨] - [位置]
• 成交量：[数值] - [放量/缩量/正常]

五、支撑压力位分析
• 关键支撑位：[价格1]、[价格2]、[价格3]
• 关键压力位：[价格1]、[价格2]、[价格3]
• 当前位置：[距离支撑位/压力位的距离]

六、量价关系分析
• 近期成交量变化：[描述]
• 量价配合度：[配合良好/背离/其他]
• 成交量信号：[放量上涨/缩量下跌/其他]

七、技术面综合评级
• 技术面评分：[0-100分]
• 评级：[强烈看多/看多/中性/看空/强烈看空]
• 短期观点：[描述]
• 中期观点：[描述]
• 长期观点：[描述]

八、技术面操作建议
• 操作建议：[买入/持有/卖出/观望]
• 建议仓位：[百分比]
• 止损位：[价格]
• 止盈位：[价格]
• 关键观察点：[描述]

【注意】综合考虑技术形态、趋势、指标、量价关系等因素，客观分析板块技术面，给出明确的技术面判断和操作建议。
"""
    
    def _prepare_input(self, sector_data: Dict[str, Any]) -> str:
        sector_name = sector_data.get('sector_name', '')
        timestamp = sector_data.get('timestamp', '')
        performance = sector_data.get('performance', {})
        rotation = sector_data.get('rotation', {})
        component_performance = sector_data.get('component_performance', {})
        fund_flow = sector_data.get('fund_flow', {})
        
        input_text = f"""请对以下板块进行技术面分析：

【板块基本信息】
板块名称：{sector_name}
分析时间：{timestamp}

【板块表现数据】
今日涨跌幅：{performance.get('today_change', '')}
近5日涨跌幅：{performance.get('5d_change', '')}
近30日涨跌幅：{performance.get('30d_change', '')}
与大盘对比：{performance.get('vs_market', '')}

【板块轮动分析】
当前市场风格：{rotation.get('current_style', '')}
板块在轮动中的位置：{rotation.get('position_in_rotation', '')}
板块轮动信号：{rotation.get('rotation_signal', '')}

【板块内个股表现】
领涨个股：{', '.join([f"{stock}（涨幅：{pct}）" for stock, pct in component_performance.get('top_gainers', [])])}
领跌个股：{', '.join([f"{stock}（跌幅：{pct}）" for stock, pct in component_performance.get('top_losers', [])])}
平均涨跌幅：{component_performance.get('avg_change', '')}
涨跌比：{component_performance.get('up_down_ratio', '')}

【资金流向分析】
板块资金净流入：{fund_flow.get('sector_net_inflow', '')}
主力资金净流入：{fund_flow.get('main_net_inflow', '')}
资金热度：{fund_flow.get('heat_level', '')}

请根据以上数据，结合技术分析理论和方法，按照系统提示的格式输出完整的板块技术面分析报告。
"""
        return input_text
    
    def _parse_result(self, result: str) -> Dict[str, Any]:
        return {
            'analysis_type': 'sector_technical',
            'content': result
        }
