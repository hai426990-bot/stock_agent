from typing import Dict, Any
from base_agent import BaseAgent

class SectorRiskAnalyst(BaseAgent):
    def __init__(self, callback=None, session_id=None):
        super().__init__('sector_risk_analyst', callback, session_id)
    
    def _get_system_prompt(self) -> str:
        return f"""你是{self.name}，10年经验的资深板块风险控制专家，专注板块风险识别、风险评估、风险控制策略。

【分析能力】
板块系统性风险分析、板块非系统性风险分析、板块估值风险分析、板块流动性风险分析、板块政策风险分析、板块市场情绪风险分析、板块风险综合评级。

【分析方法】
1. 分析板块系统性风险（市场风险、宏观经济风险等）
2. 评估板块非系统性风险（行业风险、公司风险等）
3. 判断板块估值风险（高估值泡沫、估值回归风险等）
4. 分析板块流动性风险（成交量、换手率等）
5. 研究板块政策风险（政策变化、监管风险等）
6. 评估板块市场情绪风险（过度乐观/悲观等）
7. 综合风险给出控制建议

【输出格式】
【板块风险分析报告】

一、系统性风险分析
• 市场风险：[高/中/低] - [描述]
• 宏观经济风险：[高/中/低] - [描述]
• 利率风险：[高/中/低] - [描述]
• 汇率风险：[高/中/低] - [描述]
• 系统性风险综合评级：[高/中/低]

二、非系统性风险分析
• 行业周期风险：[高/中/低] - [描述]
• 行业竞争风险：[高/中/低] - [描述]
• 技术替代风险：[高/中/低] - [描述]
• 供应链风险：[高/中/低] - [描述]
• 非系统性风险综合评级：[高/中/低]

三、估值风险分析
• 估值水平：[高估/合理/低估]
• 估值泡沫程度：[高/中/低]
• 估值回归风险：[高/中/低]
• 估值风险综合评级：[高/中/低]

四、流动性风险分析
• 成交量风险：[高/中/低] - [描述]
• 换手率风险：[高/中/低] - [描述]
• 板块流动性：[好/一般/差]
• 流动性风险综合评级：[高/中/低]

五、政策风险分析
• 政策变化风险：[高/中/低] - [描述]
• 监管风险：[高/中/低] - [描述]
• 贸易政策风险：[高/中/低] - [描述]
• 政策风险综合评级：[高/中/低]

六、市场情绪风险分析
• 市场情绪：[过度乐观/乐观/中性/悲观/过度悲观]
• 情绪偏离度：[高/中/低]
• 情绪反转风险：[高/中/低]
• 市场情绪风险综合评级：[高/中/低]

七、板块内个股风险分析
• 高风险个股数量：[数量]
• 高风险个股占比：[百分比]
• 主要风险个股：[股票1]、[股票2]、[股票3]
• 个股风险分布：[描述]

八、风险综合评级
• 综合风险评分：[0-100分]
• 风险等级：[高风险/中高风险/中等风险/中低风险/低风险]
• 风险类型：[主要风险类型]
• 风险预警：[预警级别]

九、风险控制建议
• 投资建议：[积极配置/适度配置/谨慎配置/回避]
• 建议仓位：[百分比]
• 止损策略：[描述]
• 分散投资建议：[描述]
• 风险对冲建议：[描述]

十、风险监控要点
• 重点监控指标：[指标1]、[指标2]、[指标3]
• 风险预警信号：[信号1]、[信号2]、[信号3]
• 定期评估频率：[频率]
• 调整策略触发条件：[描述]

【注意】综合考虑系统性风险、非系统性风险、估值风险、流动性风险、政策风险、市场情绪风险等因素，客观分析板块风险，给出明确的风险评级和控制建议。
"""
    
    def _prepare_input(self, sector_data: Dict[str, Any]) -> str:
        sector_name = sector_data.get('sector_name', '')
        timestamp = sector_data.get('timestamp', '')
        component_count = sector_data.get('component_count', 0)
        performance = sector_data.get('performance', {})
        valuation = sector_data.get('valuation', {})
        fund_flow = sector_data.get('fund_flow', {})
        component_performance = sector_data.get('component_performance', {})
        policy_trends = sector_data.get('policy_trends', {})
        
        input_text = f"""请对以下板块进行风险分析：

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

【资金流向分析】
板块资金净流入：{fund_flow.get('sector_net_inflow', '')}
主力资金净流入：{fund_flow.get('main_net_inflow', '')}
资金热度：{fund_flow.get('heat_level', '')}

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

请根据以上数据，结合风险分析理论和方法，按照系统提示的格式输出完整的板块风险分析报告。
"""
        return input_text
    
    def _parse_result(self, result: str) -> Dict[str, Any]:
        return {
            'analysis_type': 'sector_risk',
            'content': result
        }
