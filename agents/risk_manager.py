from typing import Dict, Any
from base_agent import BaseAgent

class RiskManager(BaseAgent):
    def __init__(self, callback=None, session_id=None):
        super().__init__('risk_manager', callback, session_id)
    
    def _get_system_prompt(self) -> str:
        return f"""你是{self.name}，10年经验的FRM持证人，专注市场风险评估、仓位管理、止损策略。

【分析能力】
市场风险（系统性风险Beta、非系统性风险、波动率）、仓位管理、止损策略、压力测试、黑天鹅预警。

【分析方法】
1. 评估系统性和特有风险 2. 计算历史和预期波动率 3. 分析最大回撤和夏普比率 4. 根据风险水平建议仓位 5. 设置止损止盈位 6. 识别黑天鹅风险

【输出格式】
【风险评估报告】

一、风险概述
• 股票代码：[代码]
• 股票名称：[名称]
• 当前价格：[价格]
• 整体风险等级：[低风险/中等风险/高风险/极高风险]

二、市场风险评估
• 系统性风险（Beta）：[数值] - [评价]
• 历史波动率：[数值] - [评价]
• 最大回撤：[数值] - [评价]
• 风险收益比：[数值] - [评价]

三、流动性风险
• 换手率：[数值] - [评价]
• 成交额：[数值] - [评价]
• 流动性评级：[高/中/低]
• 流动性风险：[描述]

四、财务风险
• 资产负债率：[数值] - [评价]
• 财务杠杆：[数值] - [评价]
• 债务风险：[描述]
• 财务风险评级：[低/中/高]

五、行业与政策风险
• 行业风险：[描述]
• 政策风险：[描述]
• 监管风险：[描述]
• 宏观风险：[描述]

六、特殊风险
• 解禁风险：[描述]
• 质押风险：[描述]
• 诉讼风险：[描述]
• 其他风险：[描述]

七、仓位建议
• 建议仓位：[具体比例]
• 仓位理由：[详细理由]
• 分批建仓：[建议]
• 加仓条件：[条件]

八、止损止盈建议
• 止损位：[价格] - [跌幅：X%]
• 止损理由：[理由]
• 止盈位：[价格] - [涨幅：X%]
• 止盈理由：[理由]
• 动态调整：[调整策略]

九、风险控制方案
• 仓位控制：[具体措施]
• 止损纪律：[具体措施]
• 分散投资：[具体措施]
• 定期评估：[具体措施]

十、风险提示
• 主要风险：[列出主要风险]
• 应对策略：[应对措施]
• 黑天鹅预警：[潜在极端风险]
• 紧急预案：[紧急情况处理方案]

【注意】风险控制第一，不建议满仓，严格执行止损，警惕黑天鹅，定期评估调整，保留现金储备。
"""
    
    def _prepare_input(self, stock_data: Dict[str, Any]) -> str:
        stock_code = stock_data.get('stock_code', '')
        stock_name = stock_data.get('stock_name', '')
        current_price = stock_data.get('current_price', '')
        high = stock_data.get('high', '')
        low = stock_data.get('low', '')
        turnover_rate = stock_data.get('turnover_rate', '')
        
        financial_data = stock_data.get('financial_data', {})
        technical_indicators = stock_data.get('technical_indicators', {})
        
        volatility = technical_indicators.get('volatility', {})
        max_drawdown = technical_indicators.get('max_drawdown', {})
        risk_metrics = technical_indicators.get('risk_metrics', {})
        support_resistance = technical_indicators.get('support_resistance', {})
        
        volatility_daily = volatility.get('volatility_daily', '待计算')
        volatility_annual = volatility.get('volatility_annual', '待计算')
        max_dd_pct = max_drawdown.get('max_drawdown_pct', '待计算')
        sharpe_ratio = risk_metrics.get('sharpe_ratio', '待计算')
        sortino_ratio = risk_metrics.get('sortino_ratio', '待计算')
        annual_return = risk_metrics.get('annual_return', '待计算')
        nearest_support = support_resistance.get('nearest_support', '待计算')
        nearest_resistance = support_resistance.get('nearest_resistance', '待计算')
        
        input_text = f"""请对以下股票进行风险评估：

【股票基本信息】
股票代码：{stock_code}
股票名称：{stock_name}
当前价格：{current_price}
最高价：{high}
最低价：{low}
换手率：{turnover_rate}

【财务风险指标】
资产负债率：{financial_data.get('debt_ratio', '')}
流动比率：{financial_data.get('current_ratio', '')}

【市场风险指标】
日波动率：{volatility_daily}
年化波动率：{volatility_annual}
最大回撤：{max_dd_pct}%
年化收益率：{annual_return}
夏普比率：{sharpe_ratio}
索提诺比率：{sortino_ratio}

【技术面风险指标】
支撑位：{nearest_support}
阻力位：{nearest_resistance}

请根据以上数据，结合市场环境和风险控制原则，按照系统提示的格式输出完整的风险评估报告。
"""
        return input_text
    
    def _parse_result(self, result: str) -> Dict[str, Any]:
        return {
            'analysis_type': 'risk',
            'content': result
        }
