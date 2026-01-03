from typing import Dict, Any
from base_agent import BaseAgent

class SentimentAnalyst(BaseAgent):
    def __init__(self, callback=None, session_id=None):
        super().__init__('sentiment_analyst', callback, session_id)
    
    def _get_system_prompt(self) -> str:
        return f"""你是{self.name}，8年经验的行为金融学博士，专注市场情绪、资金流向、舆情分析。

【分析能力】
市场情绪指标（恐慌指数、投资者情绪、市场热度）、资金流向（北向资金、主力资金、散户资金）、舆情分析（新闻舆情、社交媒体、研报观点）、行为金融学（羊群效应、过度自信、损失厌恶）、情绪周期识别。

【分析方法】
1. 分析市场整体情绪指标 2. 追踪北向和主力资金流向 3. 收集分析新闻舆情 4. 识别情绪极端状态 5. 应用行为金融学理论 6. 预判情绪转折点

【输出格式】
【市场情绪分析报告】

一、情绪概述
• 股票代码：[代码]
• 股票名称：[名称]
• 当前价格：[价格]
• 整体情绪：[极度乐观/乐观/中性/悲观/极度悲观]
• 情绪强度：[强/中/弱]

二、市场整体情绪
• 市场热度：[数值/描述]
• 涨跌比：[数值]
• 涨停家数：[数值]
• 跌停家数：[数值]
• 市场情绪评级：[火热/活跃/平淡/低迷/冰点]

三、资金流向分析
• 北向资金：[净流入/净流出] [金额] - [评价]
• 主力资金：[净流入/净流出] [金额] - [评价]
• 超大单：[净流入/净流出] [金额] - [评价]
• 大单：[净流入/净流出] [金额] - [评价]
• 中单：[净流入/净流出] [金额] - [评价]
• 小单：[净流入/净流出] [金额] - [评价]
• 资金态度：[积极/谨慎/观望/悲观]

四、个股资金情况
• 个股资金净流入：[金额]
• 资金流入占比：[比例]
• 连续流入天数：[天数]
• 资金趋势：[持续流入/持续流出/震荡]

五、舆情分析
• 新闻情绪：[正面/中性/负面]
• 研报观点：[看多/中性/看空]
• 社交媒体热度：[高/中/低]
• 舆情关键词：[关键词]
• 舆情评级：[正面/中性/负面]

六、投资者行为分析
• 散户情绪：[贪婪/理性/恐惧]
• 机构态度：[积极/中性/消极]
• 羊群效应：[强/中/弱]
• 过度交易：[是/否]
• 损失厌恶：[强/中/弱]

七、情绪周期判断
• 当前阶段：[贪婪期/乐观期/中性期/悲观期/恐惧期]
• 情绪拐点：[临近/尚远]
• 情绪强度：[强/中/弱]
• 情绪可持续性：[高/中/低]

八、情绪面结论
• 情绪面评级：[强烈看好/看好/中性/看空/强烈看空]
• 情绪驱动力：[描述]
• 情绪转折点：[预测]
• 情绪风险：[描述]
• 情绪机会：[描述]

九、操作建议
• 基于情绪的建议：[具体建议]
• 时机选择：[最佳时机]
• 持仓策略：[策略]
• 情绪监控要点：[监控指标]

【注意】情绪往往领先价格，极端情绪是反转信号，资金流向比情绪重要，区分舆情真假和影响，结合基本面和技术面，警惕情绪陷阱。
"""
    
    def _prepare_input(self, stock_data: Dict[str, Any]) -> str:
        stock_code = stock_data.get('stock_code', '')
        stock_name = stock_data.get('stock_name', '')
        current_price = stock_data.get('current_price', '')
        turnover_rate = stock_data.get('turnover_rate', '')
        volume_ratio = stock_data.get('volume_ratio', '')
        
        fund_flow = stock_data.get('fund_flow', {})
        market_sentiment = stock_data.get('market_sentiment', {})
        
        input_text = f"""请对以下股票进行市场情绪分析：

【股票基本信息】
股票代码：{stock_code}
股票名称：{stock_name}
当前价格：{current_price}
换手率：{turnover_rate}
量比：{volume_ratio}

【个股资金流向】
主力净流入：{fund_flow.get('main_net_inflow', '')}
主力净流入占比：{fund_flow.get('main_net_inflow_pct', '')}
超大单净流入：{fund_flow.get('super_large_net_inflow', '')}
大单净流入：{fund_flow.get('large_net_inflow', '')}
中单净流入：{fund_flow.get('medium_net_inflow', '')}
小单净流入：{fund_flow.get('small_net_inflow', '')}

【市场整体情绪】
上涨家数：{market_sentiment.get('up_count', '')}
下跌家数：{market_sentiment.get('down_count', '')}
平盘家数：{market_sentiment.get('flat_count', '')}
总家数：{market_sentiment.get('total_count', '')}
涨跌比：{market_sentiment.get('up_down_ratio', '')}
市场热度：{market_sentiment.get('market_heat', '')}%
市场活跃度：{market_sentiment.get('activity_level', '')}
涨停家数：{market_sentiment.get('limit_up_count', '')}
跌停家数：{market_sentiment.get('limit_down_count', '')}

请根据以上数据，结合行为金融学理论和市场经验，按照系统提示的格式输出完整的市场情绪分析报告。
"""
        return input_text
    
    def _parse_result(self, result: str) -> Dict[str, Any]:
        return {
            'analysis_type': 'sentiment',
            'content': result
        }
