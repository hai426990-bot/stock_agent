from typing import Dict, Any
from base_agent import BaseAgent

class FundamentalAnalyst(BaseAgent):
    def __init__(self, callback=None, session_id=None):
        super().__init__('fundamental_analyst', callback, session_id)
    
    def _get_system_prompt(self) -> str:
        return f"""你是{self.name}，12年经验的CFA持证人，专注财务报表分析、估值模型、行业研究。

【分析能力】
财务报表（资产负债表、利润表、现金流量表）、估值模型（PE/PB/PEG/DCF/EV/EBITDA）、行业竞争格局、公司治理、成长性分析。

【分析方法】
1. 分析盈利/偿债/运营/成长/现金流能力 2. 多种估值交叉验证（PE/PB/PEG/DCF等） 3. 研究行业趋势和竞争格局 4. 评估核心竞争力和护城河 5. 考察管理层素质 6. 综合判断内在价值

【输出格式】
【基本面分析报告】

一、公司概况
• 股票代码：[代码]
• 股票名称：[名称]
• 所属行业：[行业]
• 主营业务：[业务描述]
• 市值规模：[描述]

二、盈利能力分析
• 净资产收益率（ROE）：[数值] - [评价]
• 总资产净利率（ROA）：[数值] - [评价]
• 销售毛利率：[数值] - [评价]
• 销售净利率：[数值] - [评价]
• 营业利润率：[数值] - [评价]
• 盈利能力评级：[优秀/良好/一般/较差]
• 与行业平均比较：[优于行业/符合行业/低于行业]

三、运营能力分析
• 存货周转率：[数值] - [评价]
• 应收账款周转率：[数值] - [评价]
• 总资产周转率：[数值] - [评价]
• 运营效率评级：[高效/良好/一般/低效]

四、偿债能力分析
• 资产负债率：[数值] - [评价]
• 流动比率：[数值] - [评价]
• 经营活动现金流量净额/负债合计：[数值] - [评价]
• 偿债能力评级：[强/中等/弱]

五、现金流分析
• 经营活动产生的现金流量净额：[数值] - [评价]
• 经营活动现金流量净额/基本每股收益：[数值] - [评价]
• 每股经营活动产生的现金流量净额：[数值] - [评价]
• 现金流健康度：[健康/一般/紧张]

六、成长性分析
• 营业收入增长率：[数值] - [评价]
• 净利润增长率：[数值] - [评价]
• 营业利润增长率：[数值] - [评价]
• 历史增长趋势：[描述]
• 与行业平均增长率比较：[高于行业/符合行业/低于行业]
• 成长性评级：[高成长/稳健成长/低成长/负增长]

七、估值分析
• 市盈率（PE）：[数值] - 行业平均：[数值] - [评价]
• 市净率（PB）：[数值] - 行业平均：[数值] - [评价]
• PEG（市盈率相对盈利增长比率）：[数值] - [评价]
• 股息率：[数值]% - [评价]
• 相对估值：[低估/合理/高估]
• 内在价值评估：[具体评估]
• 多种估值方法交叉验证：[描述]

八、行业地位与竞争力
• 行业地位：[龙头/领先/跟随/落后]
• 核心竞争力：[描述]
• 护城河：[品牌/技术/成本/网络效应/资源/规模等]
• 与行业平均财务指标比较：[全面优于行业/部分优于行业/符合行业/低于行业]
• 竞争优势持续性：[强/中/弱]

九、基本面结论
• 基本面综合评级：[强烈推荐/推荐/持有/回避/强烈回避]
• 核心投资逻辑：[清晰阐述核心投资价值]
• 合理估值区间：[价格区间]
• 投资亮点：[1-3个主要亮点]
• 关注要点：[持续关注的关键指标或事件]
• 风险提示：[基本面相关风险]

【注意】重视财务数据真实性和可持续性，关注现金流与利润的匹配度，考虑行业周期和宏观环境，警惕财务造假，注重安全边际。在分析中充分利用提供的所有财务指标和行业比较数据。
"""
    
    def _prepare_input(self, stock_data: Dict[str, Any]) -> str:
        stock_code = stock_data.get('stock_code', '')
        stock_name = stock_data.get('stock_name', '')
        current_price = stock_data.get('current_price', '')
        market_cap = stock_data.get('market_cap', '')
        pe_ratio = stock_data.get('pe_ratio', '')
        pb_ratio = stock_data.get('pb_ratio', '')
        
        financial_data = stock_data.get('financial_data', {})
        industry_comparison = stock_data.get('industry_comparison', {})
        valuation_data = stock_data.get('valuation_data', {})
        
        # 添加行业和主营业务信息（从stock_info获取）
        stock_info = stock_data.get('stock_info', {})
        industry = stock_info.get('industry', '')
        main_business = stock_info.get('main_business', '')
        
        input_text = f"""请对以下股票进行基本面分析：

【股票基本信息】
股票代码：{stock_code}
股票名称：{stock_name}
当前价格：{current_price}
总市值：{market_cap}
市盈率：{pe_ratio}
市净率：{pb_ratio}
所属行业：{industry}
主营业务：{main_business}

【财务指标数据】
# 盈利能力指标
净资产收益率（ROE）：{financial_data.get('roe', '')}
总资产净利率（ROA）：{financial_data.get('roa', '')}
销售毛利率：{financial_data.get('gross_margin', '')}
销售净利率：{financial_data.get('net_margin', '')}
营业利润率：{financial_data.get('operating_profit_margin', '')}

# 运营能力指标
存货周转率：{financial_data.get('inventory_turnover', '')}
应收账款周转率：{financial_data.get('accounts_receivable_turnover', '')}
总资产周转率：{financial_data.get('total_asset_turnover', '')}

# 偿债能力指标
资产负债率：{financial_data.get('debt_ratio', '')}
流动比率：{financial_data.get('current_ratio', '')}
经营活动现金流量净额/负债合计：{financial_data.get('cash_flow_ratio', '')}

# 成长能力指标
营业收入增长率：{financial_data.get('revenue_growth', '')}
净利润增长率：{financial_data.get('profit_growth', '')}
营业利润增长率：{financial_data.get('operating_profit_growth', '')}

# 现金流指标
经营活动产生的现金流量净额：{financial_data.get('operating_cash_flow', '')}
经营活动现金流量净额/基本每股收益：{financial_data.get('operating_cash_flow_per_share', '')}

# 每股指标
基本每股收益（EPS）：{financial_data.get('eps', '')}
每股净资产：{financial_data.get('book_value_per_share', '')}
每股经营活动产生的现金流量净额：{financial_data.get('cash_per_share', '')}

【行业比较数据】
行业平均市盈率（PE）：{industry_comparison.get('industry_pe', '')}
行业平均市净率（PB）：{industry_comparison.get('industry_pb', '')}
行业平均净资产收益率（ROE）：{industry_comparison.get('industry_roe', '')}
行业平均增长率：{industry_comparison.get('industry_growth_rate', '')}

【估值数据】
PEG（市盈率相对盈利增长比率）：{valuation_data.get('peg_ratio', '')}
股息率：{valuation_data.get('dividend_yield', '')}%

请根据以上数据，结合行业常识和估值标准，按照系统提示的格式输出完整的基本面分析报告。
"""
        return input_text
    
    def _parse_result(self, result: str) -> Dict[str, Any]:
        return {
            'analysis_type': 'fundamental',
            'content': result
        }
