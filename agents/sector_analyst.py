from typing import Dict, Any
from base_agent import BaseAgent

class SectorAnalyst(BaseAgent):
    def __init__(self, callback=None, session_id=None):
        super().__init__('sector_analyst', callback, session_id)
    
    def _get_system_prompt(self) -> str:
        return f"""你是{self.name}，10年经验的资深板块分析师，专注行业板块研究、板块轮动、板块间关系分析。

【分析能力】
板块整体表现分析、板块内个股表现比较、板块资金流向分析、板块估值水平评估、板块与大盘关系分析、板块轮动规律研究、板块政策影响分析。

【分析方法】
1. 分析板块整体涨跌幅与大盘对比 2. 研究板块内领涨领跌个股 3. 分析板块资金流向 4. 评估板块估值水平 5. 研究板块轮动规律 6. 结合政策和行业趋势给出投资建议

【输出格式】
【板块分析报告】

一、板块概况
• 板块名称：[名称]
• 分析时间：[时间]
• 成分股数量：[数量]
• 板块总市值：[市值]

二、板块整体表现
• 今日涨跌幅：[数值] - [评价]
• 近5日涨跌幅：[数值] - [评价]
• 近30日涨跌幅：[数值] - [评价]
• 与大盘对比：[强于大盘/弱于大盘/持平]
• 板块表现评级：[优秀/良好/一般/较差]

三、板块内个股表现
• 领涨个股：[股票1]（涨幅：[数值]）、[股票2]（涨幅：[数值]）、[股票3]（涨幅：[数值]）
• 领跌个股：[股票1]（跌幅：[数值]）、[股票2]（跌幅：[数值]）、[股票3]（跌幅：[数值]）
• 平均涨跌幅：[数值]
• 涨跌比：[上涨家数]:[下跌家数]

四、资金流向分析
• 板块资金净流入：[数值] - [评价]
• 主力资金净流入：[数值] - [评价]
• 北向资金净流入：[数值] - [评价]
• 资金热度：[高/中/低]

五、估值水平分析
• 板块平均市盈率（PE）：[数值] - [评价]
• 板块平均市净率（PB）：[数值] - [评价]
• 估值历史分位：[数值]% - [评价]
• 与大盘估值对比：[低估/合理/高估]

六、板块轮动分析
• 当前市场风格：[价值/成长/周期/消费/科技等]
• 板块在轮动中的位置：[启动期/上升期/顶部期/下跌期]
• 板块轮动信号：[信号描述]

七、政策与行业趋势
• 最新政策影响：[描述]
• 行业发展趋势：[描述]
• 利好因素：[因素1]、[因素2]、[因素3]
• 利空因素：[因素1]、[因素2]、[因素3]

八、板块投资建议
• 投资评级：[强烈推荐/推荐/持有/回避/强烈回避]
• 核心投资逻辑：[描述]
• 重点关注个股：[股票1]、[股票2]、[股票3]
• 操作建议：[描述]
• 风险提示：[风险1]、[风险2]、[风险3]

【注意】综合考虑板块基本面、资金面、技术面和政策面，客观分析板块投资价值，给出明确的投资建议和风险提示。
"""
    
    def _prepare_input(self, sector_data: Dict[str, Any]) -> str:
        sector_name = sector_data.get('sector_name', '')
        timestamp = sector_data.get('timestamp', '')
        component_count = sector_data.get('component_count', 0)
        total_market_cap = sector_data.get('total_market_cap', '')
        
        performance = sector_data.get('performance', {})
        component_performance = sector_data.get('component_performance', {})
        fund_flow = sector_data.get('fund_flow', {})
        valuation = sector_data.get('valuation', {})
        rotation = sector_data.get('rotation', {})
        policy_trends = sector_data.get('policy_trends', {})
        
        input_text = f"""请对以下板块进行综合分析：

【板块基本信息】
板块名称：{sector_name}
分析时间：{timestamp}
成分股数量：{component_count}
板块总市值：{total_market_cap}

【板块整体表现】
今日涨跌幅：{performance.get('today_change', '')}
近5日涨跌幅：{performance.get('5d_change', '')}
近30日涨跌幅：{performance.get('30d_change', '')}
与大盘对比：{performance.get('vs_market', '')}

【板块内个股表现】
领涨个股：{', '.join([f"{stock}（涨幅：{pct}）" for stock, pct in component_performance.get('top_gainers', [])])}
领跌个股：{', '.join([f"{stock}（跌幅：{pct}）" for stock, pct in component_performance.get('top_losers', [])])}
平均涨跌幅：{component_performance.get('avg_change', '')}
涨跌比：{component_performance.get('up_down_ratio', '')}

【资金流向分析】
板块资金净流入：{fund_flow.get('sector_net_inflow', '')}
主力资金净流入：{fund_flow.get('main_net_inflow', '')}
北向资金净流入：{fund_flow.get('north_net_inflow', '')}
资金热度：{fund_flow.get('heat_level', '')}

【估值水平分析】
板块平均市盈率（PE）：{valuation.get('avg_pe', '')}
板块平均市净率（PB）：{valuation.get('avg_pb', '')}
估值历史分位：{valuation.get('pe_history_percentile', '')}%
与大盘估值对比：{valuation.get('vs_market_valuation', '')}

【板块轮动分析】
当前市场风格：{rotation.get('current_style', '')}
板块在轮动中的位置：{rotation.get('position_in_rotation', '')}
板块轮动信号：{rotation.get('rotation_signal', '')}

【政策与行业趋势】
最新政策影响：{policy_trends.get('latest_policy', '')}
行业发展趋势：{policy_trends.get('industry_trend', '')}
利好因素：{', '.join(policy_trends.get('positive_factors', []))}
利空因素：{', '.join(policy_trends.get('negative_factors', []))}

请根据以上数据，结合行业常识和市场规律，按照系统提示的格式输出完整的板块分析报告。
"""
        return input_text
    
    def _parse_result(self, result: str) -> Dict[str, Any]:
        return {
            'analysis_type': 'sector',
            'content': result
        }
