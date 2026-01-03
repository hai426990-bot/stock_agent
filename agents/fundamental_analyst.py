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
1. 分析盈利/偿债/运营/成长能力 2. 多种估值交叉验证 3. 研究行业趋势和竞争格局 4. 评估核心竞争力和护城河 5. 考察管理层素质 6. 综合判断内在价值

【输出格式】
【基本面分析报告】

一、公司概况
• 股票代码：[代码]
• 股票名称：[名称]
• 所属行业：[行业]
• 主营业务：[业务描述]

二、盈利能力分析
• 净资产收益率（ROE）：[数值] - [评价]
• 总资产净利率（ROA）：[数值] - [评价]
• 销售毛利率：[数值] - [评价]
• 销售净利率：[数值] - [评价]
• 盈利能力评级：[优秀/良好/一般/较差]

三、成长性分析
• 营业收入增长率：[数值] - [评价]
• 净利润增长率：[数值] - [评价]
• 历史增长趋势：[描述]
• 成长性评级：[高成长/稳健成长/低成长/负增长]

四、财务健康度
• 资产负债率：[数值] - [评价]
• 流动比率：[数值] - [评价]
• 现金流状况：[描述]
• 财务风险评级：[低风险/中等风险/高风险]

五、估值分析
• 市盈率（PE）：[数值] - 行业平均：[数值] - [评价]
• 市净率（PB）：[数值] - 行业平均：[数值] - [评价]
• 相对估值：[低估/合理/高估]
• 内在价值评估：[具体评估]

六、行业地位与竞争力
• 行业地位：[龙头/领先/跟随/落后]
• 核心竞争力：[描述]
• 护城河：[品牌/技术/成本/网络效应等]
• 竞争优势持续性：[强/中/弱]

七、管理层与公司治理
• 管理层评价：[优秀/良好/一般/较差]
• 公司治理结构：[描述]
• 激励机制：[描述]
• 治理风险：[描述]

八、基本面结论
• 基本面评级：[强烈推荐/推荐/持有/回避/强烈回避]
• 投资逻辑：[核心投资逻辑]
• 合理估值区间：[价格区间]
• 关注要点：[持续关注要点]
• 风险提示：[基本面风险]

【注意】重视财务数据真实性和可持续性，关注现金流，考虑行业周期和宏观环境，警惕财务造假，注重安全边际。
"""
    
    def _prepare_input(self, stock_data: Dict[str, Any]) -> str:
        stock_code = stock_data.get('stock_code', '')
        stock_name = stock_data.get('stock_name', '')
        current_price = stock_data.get('current_price', '')
        market_cap = stock_data.get('market_cap', '')
        pe_ratio = stock_data.get('pe_ratio', '')
        pb_ratio = stock_data.get('pb_ratio', '')
        
        financial_data = stock_data.get('financial_data', {})
        
        input_text = f"""请对以下股票进行基本面分析：

【股票基本信息】
股票代码：{stock_code}
股票名称：{stock_name}
当前价格：{current_price}
总市值：{market_cap}

【财务指标数据】
净资产收益率（ROE）：{financial_data.get('roe', '')}
总资产净利率（ROA）：{financial_data.get('roa', '')}
销售毛利率：{financial_data.get('gross_margin', '')}
销售净利率：{financial_data.get('net_margin', '')}
资产负债率：{financial_data.get('debt_ratio', '')}
流动比率：{financial_data.get('current_ratio', '')}
营业收入增长率：{financial_data.get('revenue_growth', '')}
净利润增长率：{financial_data.get('profit_growth', '')}

【估值指标】
市盈率（PE）：{pe_ratio}
市净率（PB）：{pb_ratio}

请根据以上数据，结合行业常识和估值标准，按照系统提示的格式输出完整的基本面分析报告。
"""
        return input_text
    
    def _parse_result(self, result: str) -> Dict[str, Any]:
        return {
            'analysis_type': 'fundamental',
            'content': result
        }
