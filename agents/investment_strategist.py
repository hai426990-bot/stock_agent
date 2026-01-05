from typing import Dict, Any, List
from base_agent import BaseAgent

class InvestmentStrategist(BaseAgent):
    def __init__(self, callback=None, session_id=None):
        super().__init__('investment_strategist', callback, session_id)
        self.dependencies = ['technical_analyst', 'fundamental_analyst', 'risk_manager', 'sentiment_analyst']
    
    def _get_system_prompt(self) -> str:
        return f"""你是{self.name}，20年经验的资深投资策略师，专注投资策略制定、资产配置、综合分析。

【分析能力】
多维度信息整合（技术面、基本面、风险面、情绪面）、投资策略制定（短线/中线/长线）、资产配置建议（仓位/行业/风格配置）、投资组合优化、冲突解决。

【分析方法】
1. 收集整合技术面/基本面/风险面/情绪面分析 2. 识别各方意见一致性和分歧点 3. 权衡不同因素重要性 4. 制定综合投资策略 5. 给出明确操作建议 6. 制定风险控制方案

【输出格式】
【综合投资策略报告】

一、投资标的概述
• 股票代码：[代码]
• 股票名称：[名称]
• 当前价格：[价格]
• 分析时间：[时间]

二、各维度分析汇总
• 技术面：[评级] - [核心观点]
• 基本面：[评级] - [核心观点]
• 风险面：[评级] - [核心观点]
• 情绪面：[评级] - [核心观点]

三、综合评级
• 综合评级：[强烈买入/买入/持有/卖出/强烈卖出]
• 评级理由：[详细理由]
• 评级强度：[强/中/弱]
• 信心水平：[高/中/低]

四、投资策略
• 投资方向：[做多/做空/观望]
• 投资周期：[短线/中线/长线]
• 预期收益：[收益率]
• 风险等级：[低/中/高]

五、操作建议
• 买入价格：[价格区间]
• 目标价格：[短期目标/中期目标/长期目标]
• 止损价格：[价格]
• 建议仓位：[比例]
• 分批策略：[详细策略]

六、持仓周期
• 预计持仓时间：[时间]
• 加仓条件：[条件]
• 减仓条件：[条件]
• 清仓条件：[条件]

七、风险控制
• 最大亏损：[比例]
• 风险控制措施：[具体措施]
• 应对预案：[预案]
• 止损纪律：[纪律要求]

八、关键监控指标
• 技术面监控：[指标]
• 基本面监控：[指标]
• 资金面监控：[指标]
• 情绪面监控：[指标]

九、潜在机会
• 上涨催化剂：[因素]
• 超预期可能：[描述]
• 估值修复空间：[描述]

十、主要风险
• 下行风险：[风险]
• 黑天鹅风险：[风险]
• 应对策略：[策略]

十一、投资逻辑总结
• 核心投资逻辑：[逻辑]
• 关键假设：[假设]
• 证伪条件：[条件]

十二、最终建议
• 操作建议：[买入/持有/卖出/观望]
• 操作时机：[时机]
• 操作方式：[方式]
• 注意事项：[注意事项]

【注意】综合考虑所有维度信息，不盲从单一意见，风险可控前提下追求收益，保持投资纪律，定期复盘调整，严格执行止损止盈。
"""
    
    def _prepare_input(self, stock_data: Dict[str, Any]) -> str:
        stock_code = stock_data.get('stock_code', '')
        stock_name = stock_data.get('stock_name', '')
        current_price = stock_data.get('current_price', '')
        timestamp = stock_data.get('timestamp', '')
        
        analyses = stock_data.get('analyses', {})
        
        technical_analysis = analyses.get('technical_analyst', {}).get('result', {}).get('content', '暂无分析')
        fundamental_analysis = analyses.get('fundamental_analyst', {}).get('result', {}).get('content', '暂无分析')
        risk_analysis = analyses.get('risk_manager', {}).get('result', {}).get('content', '暂无分析')
        sentiment_analysis = analyses.get('sentiment_analyst', {}).get('result', {}).get('content', '暂无分析')
        
        input_text = f"""请综合以下各分析师的意见，制定最终的投资策略：

【股票基本信息】
股票代码：{stock_code}
股票名称：{stock_name}
当前价格：{current_price}
分析时间：{timestamp}

【技术分析师 - 张技术的分析】
{technical_analysis}

【基本面分析师 - 李价值的分析】
{fundamental_analysis}

【风险控制专家 - 王风控的分析】
{risk_analysis}

【市场情绪分析师 - 赵情绪的分析】
{sentiment_analysis}

请综合以上四位分析师的意见，识别一致性和分歧点，权衡不同因素的重要性，按照系统提示的格式输出完整的综合投资策略报告。
"""
        return input_text
    
    def _parse_result(self, result: str) -> Dict[str, Any]:
        # 解析综合评级文本，提取评级
        import re
        rating_pattern = r'• 综合评级：\[(强烈买入|买入|持有|卖出|强烈卖出)\]'
        match = re.search(rating_pattern, result)
        rating = match.group(1) if match else '持有'
        
        # 评分转换规则
        rating_score_map = {
            '强烈买入': 5,
            '买入': 4,
            '持有': 3,
            '卖出': 2,
            '强烈卖出': 1
        }
        
        # 计算综合评分
        comprehensive_score = rating_score_map.get(rating, 3)
        
        return {
            'analysis_type': 'strategy',
            'content': result,
            'is_final': True,
            'comprehensive_rating': rating,
            'comprehensive_score': comprehensive_score
        }
