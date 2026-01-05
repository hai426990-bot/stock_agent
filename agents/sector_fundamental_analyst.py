from typing import Dict, Any
from base_agent import BaseAgent

class SectorFundamentalAnalyst(BaseAgent):
    def __init__(self, callback=None, session_id=None):
        super().__init__('sector_fundamental_analyst', callback, session_id)
    
    def _get_system_prompt(self) -> str:
        return f"""你是{self.name}，10年经验的资深板块基本面分析师，专注板块基本面研究、行业景气度分析、板块估值评估。

【分析能力】
板块基本面分析、行业景气度判断、板块估值评估、板块盈利能力分析、板块成长性分析、板块财务健康度分析、板块基本面综合评级。

【分析方法】
1. 分析板块整体盈利水平（ROE、ROA、净利润率等）
2. 评估板块成长性（营收增长率、利润增长率等）
3. 分析板块估值水平（PE、PB、PS、PEG等）
4. 研究板块财务健康度（资产负债率、现金流等）
5. 判断行业景气度和周期位置
6. 分析板块内龙头公司基本面
7. 综合基本面给出投资建议

【输出格式】
【板块基本面分析报告】

一、行业景气度分析
• 当前景气度：[高景气/中景气/低景气]
• 景气度变化：[上升/下降/稳定]
• 行业周期位置：[复苏期/成长期/成熟期/衰退期]
• 景气度驱动因素：[因素1]、[因素2]、[因素3]

二、板块盈利能力分析
• 平均净资产收益率（ROE）：[数值] - [评价]
• 平均总资产收益率（ROA）：[数值] - [评价]
• 平均净利润率：[数值] - [评价]
• 平均毛利率：[数值] - [评价]
• 盈利能力评级：[优秀/良好/一般/较差]

三、板块成长性分析
• 平均营收增长率：[数值] - [评价]
• 平均净利润增长率：[数值] - [评价]
• 平均营收增速排名：[排名]
• 平均利润增速排名：[排名]
• 成长性评级：[高成长/中成长/低成长/负增长]

四、板块估值评估
• 平均市盈率（PE）：[数值] - [评价]
• 平均市净率（PB）：[数值] - [评价]
• 平均市销率（PS）：[数值] - [评价]
• 平均PEG：[数值] - [评价]
• 估值历史分位：[数值]% - [评价]
• 估值评级：[低估/合理/高估]

五、板块财务健康度分析
• 平均资产负债率：[数值] - [评价]
• 平均流动比率：[数值] - [评价]
• 平均速动比率：[数值] - [评价]
• 平均经营现金流：[数值] - [评价]
• 财务健康度评级：[健康/良好/一般/风险]

六、板块内龙头公司分析
• 龙头公司1：[名称] - [基本面亮点]
• 龙头公司2：[名称] - [基本面亮点]
• 龙头公司3：[名称] - [基本面亮点]
• 龙头公司整体表现：[描述]

七、行业竞争格局分析
• 市场集中度：[高/中/低]
• 竞争激烈程度：[激烈/一般/缓和]
• 行业壁垒：[高/中/低]
• 竞争优势因素：[因素1]、[因素2]、[因素3]

八、基本面综合评级
• 基本面评分：[0-100分]
• 评级：[强烈推荐/推荐/持有/回避/强烈回避]
• 核心投资逻辑：[描述]
• 投资价值评估：[高价值/中价值/低价值]

九、基本面操作建议
• 投资建议：[长期持有/中期配置/短期交易/观望]
• 建议仓位：[百分比]
• 关注重点：[描述]
• 风险提示：[风险1]、[风险2]、[风险3]

【注意】综合考虑盈利能力、成长性、估值、财务健康度等因素，客观分析板块基本面，给出明确的基本面判断和投资建议。
"""
    
    def _prepare_input(self, sector_data: Dict[str, Any]) -> str:
        sector_name = sector_data.get('sector_name', '')
        timestamp = sector_data.get('timestamp', '')
        component_count = sector_data.get('component_count', 0)
        valuation = sector_data.get('valuation', {})
        performance = sector_data.get('performance', {})
        policy_trends = sector_data.get('policy_trends', {})
        component_performance = sector_data.get('component_performance', {})
        
        input_text = f"""请对以下板块进行基本面分析：

【板块基本信息】
板块名称：{sector_name}
分析时间：{timestamp}
成分股数量：{component_count}

【板块表现数据】
今日涨跌幅：{performance.get('today_change', '')}
近5日涨跌幅：{performance.get('5d_change', '')}
近30日涨跌幅：{performance.get('30d_change', '')}
与大盘对比：{performance.get('vs_market', '')}

【估值水平分析】
板块平均市盈率（PE）：{valuation.get('avg_pe', '')}
板块平均市净率（PB）：{valuation.get('avg_pb', '')}
估值历史分位：{valuation.get('pe_history_percentile', '')}%
与大盘估值对比：{valuation.get('vs_market_valuation', '')}

【板块内个股表现】
领涨个股：{', '.join([f"{stock}（涨幅：{pct}）" for stock, pct in component_performance.get('top_gainers', [])])}
领跌个股：{', '.join([f"{stock}（跌幅：{pct}）" for stock, pct in component_performance.get('top_losers', [])])}
平均涨跌幅：{component_performance.get('avg_change', '')}
涨跌比：{component_performance.get('up_down_ratio', '')}

【政策与行业趋势】
最新政策影响：{policy_trends.get('latest_policy', '')}
行业发展趋势：{policy_trends.get('industry_trend', '')}
利好因素：{', '.join(policy_trends.get('positive_factors', []))}
利空因素：{', '.join(policy_trends.get('negative_factors', []))}

请根据以上数据，结合基本面分析理论和方法，按照系统提示的格式输出完整的板块基本面分析报告。
"""
        return input_text
    
    def _parse_result(self, result: str) -> Dict[str, Any]:
        return {
            'analysis_type': 'sector_fundamental',
            'content': result
        }
