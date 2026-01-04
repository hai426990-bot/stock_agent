from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
import time
from agents.technical_analyst import TechnicalAnalyst
from agents.fundamental_analyst import FundamentalAnalyst
from agents.risk_manager import RiskManager
from agents.sentiment_analyst import SentimentAnalyst
from agents.investment_strategist import InvestmentStrategist
from tools.data_fetcher import DataFetcher
from tools.stock_analyzer import StockAnalyzer
from tools.backtest_engine import BacktestEngine
from tools.backtest_visualizer import BacktestVisualizer
from tools.logger import logger
from tools.performance_monitor import performance_monitor, print_stats, reset_stats

class StockAgent:
    def __init__(self, callback=None, session_id=None):
        self.data_fetcher = DataFetcher()
        self.stock_analyzer = StockAnalyzer()
        self.callback = callback
        self.session_id = session_id
        self._backtest_engine = None
        self._backtest_visualizer = None
        
        self.agents = {
            'technical_analyst': TechnicalAnalyst(callback, session_id),
            'fundamental_analyst': FundamentalAnalyst(callback, session_id),
            'risk_manager': RiskManager(callback, session_id),
            'sentiment_analyst': SentimentAnalyst(callback, session_id),
            'investment_strategist': InvestmentStrategist(callback, session_id)
        }

    @property
    def backtest_engine(self) -> BacktestEngine:
        if self._backtest_engine is None:
            self._backtest_engine = BacktestEngine()
        return self._backtest_engine

    @property
    def backtest_visualizer(self) -> BacktestVisualizer:
        if self._backtest_visualizer is None:
            self._backtest_visualizer = BacktestVisualizer()
        return self._backtest_visualizer
    
    def _notify(self, message: str):
        if self.callback:
            self.callback({
                'agent_type': 'system',
                'agent_name': '系统',
                'agent_title': '系统消息',
                'agent_icon': '🔔',
                'agent_color': '#607d8b',
                'status': 'analyzing',
                'progress': 0,
                'message': message,
                'session_id': self.session_id
            })
    
    def _notify_agent(self, agent_type: str, status: str, progress: int, message: str = ""):
        if self.callback:
            self.callback({
                'agent_type': agent_type,
                'agent_name': agent_type,
                'agent_title': agent_type,
                'agent_icon': '📥',
                'agent_color': '#95a5a6',
                'status': status,
                'progress': progress,
                'message': message,
                'session_id': self.session_id
            })
    
    @performance_monitor
    def analyze_stock(self, stock_code: str) -> Dict[str, Any]:
        # 重置性能统计
        reset_stats()
        logger.info(f"[股票分析] 开始分析股票代码: {stock_code}")
        self._notify(f"开始分析股票 {stock_code}...")
        
        self._notify_agent('data_downloader', 'analyzing', 10, '开始下载数据...')
        
        try:
            logger.debug("[股票分析] 并行获取所有数据...")
            self._notify("正在获取股票数据...")
            self._notify_agent('data_downloader', 'analyzing', 20, '正在并行获取数据...')
            
            def fetch_stock_info():
                self._notify("正在获取股票基本信息...")
                return self.data_fetcher.get_stock_info(stock_code)
            
            def fetch_kline_data():
                self._notify("正在获取K线数据...")
                return self.data_fetcher.get_kline_data(stock_code)
            
            def fetch_financial_data():
                self._notify("正在获取财务数据...")
                return self.data_fetcher.get_financial_data(stock_code)
            
            def fetch_fund_flow():
                self._notify("正在获取资金流向数据...")
                return self.data_fetcher.get_fund_flow(stock_code)
            
            def fetch_market_sentiment():
                self._notify("正在获取市场情绪数据...")
                return self.data_fetcher.get_market_sentiment()
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_name = {
                    executor.submit(fetch_stock_info): 'stock_info',
                    executor.submit(fetch_kline_data): 'kline_data',
                    executor.submit(fetch_financial_data): 'financial_data',
                    executor.submit(fetch_fund_flow): 'fund_flow',
                    executor.submit(fetch_market_sentiment): 'market_sentiment'
                }
                
                results = {}
                pending = set(future_to_name.keys())
                data_fetch_deadline = time.monotonic() + 15.0
                while pending:
                    remaining = data_fetch_deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
                    for future in done:
                        name = future_to_name[future]
                        try:
                            results[name] = future.result()
                            logger.debug(f"[股票分析] {name} 获取成功")
                        except Exception as e:
                            logger.error(f"[股票分析] {name} 获取失败: {e}")
                            results[name] = None if name != 'kline_data' else pd.DataFrame()
                
                if pending:
                    for future in pending:
                        name = future_to_name[future]
                        future.cancel()
                        logger.warning(f"[股票分析] {name} 获取超时，已跳过")
                        results[name] = None if name != 'kline_data' else pd.DataFrame()
            
            stock_info = results.get('stock_info') or {}
            kline_data = results.get('kline_data')
            if kline_data is None:
                kline_data = pd.DataFrame()
            financial_data = results.get('financial_data') or {}
            fund_flow = results.get('fund_flow') or {}
            market_sentiment = results.get('market_sentiment') or {}
            
            logger.debug(f"[股票分析] 股票信息获取成功: {stock_info}")
            logger.debug(f"[股票分析] K线数据获取成功, 长度: {len(kline_data) if isinstance(kline_data, pd.DataFrame) else 'N/A'}")
            logger.debug(f"[股票分析] 财务数据获取成功: {financial_data}")
            logger.debug(f"[股票分析] 资金流向数据获取成功: {fund_flow}")
            logger.debug(f"[股票分析] 市场情绪数据获取成功: {market_sentiment}")
            
            stock_data = {
                'stock_code': stock_code,
                'stock_name': stock_info.get('stock_name', ''),
                'current_price': stock_info.get('current_price', 0.0),
                'market_cap': stock_info.get('market_cap', ''),
                'pe_ratio': stock_info.get('pe_ratio', ''),
                'pb_ratio': stock_info.get('pb_ratio', ''),
                'turnover_rate': stock_info.get('turnover_rate', ''),
                'volume_ratio': stock_info.get('volume_ratio', ''),
                'high_52w': stock_info.get('high_52w', ''),
                'low_52w': stock_info.get('low_52w', ''),
                'timestamp': stock_info.get('timestamp', datetime.now().isoformat()),
                'kline_data': kline_data.to_dict('records') if isinstance(kline_data, pd.DataFrame) and not kline_data.empty else [],
                'financial_data': financial_data or {},
                'fund_flow': fund_flow or {},
                'market_sentiment': market_sentiment or {
                    'up_count': 0,
                    'down_count': 0,
                    'flat_count': 0,
                    'total_count': 0,
                    'up_down_ratio': 0,
                    'market_heat': 0,
                    'activity_level': '0%',
                    'limit_up_count': 0,
                    'limit_down_count': 0
                }
            }
            
            # 数据完整性检查和默认值处理
            logger.debug("[股票分析] 开始数据完整性检查...")
            
            # 确保财务数据有默认值
            if not stock_data['financial_data']:
                stock_data['financial_data'] = {
                    'roe': '',
                    'roa': '',
                    'gross_margin': '',
                    'net_margin': '',
                    'debt_ratio': '',
                    'current_ratio': '',
                    'revenue_growth': '',
                    'profit_growth': ''
                }
            
            # 确保资金流向数据有默认值
            if not stock_data['fund_flow']:
                stock_data['fund_flow'] = {
                    'main_net_inflow': '',
                    'main_net_inflow_pct': '',
                    'super_large_net_inflow': '',
                    'large_net_inflow': '',
                    'medium_net_inflow': '',
                    'small_net_inflow': ''
                }
            
            logger.debug("[股票分析] 数据完整性检查完成")
            logger.debug(f"[股票分析] 最终股票数据: {stock_data}")
            
            logger.debug("[股票分析] 正在计算技术指标...")
            self._notify("正在计算技术指标...")
            stock_data['technical_indicators'] = self.stock_analyzer.analyze_technical_indicators(stock_data)
            logger.debug(f"[股票分析] 技术指标计算完成: {stock_data['technical_indicators']}")
            
            self._notify_agent('data_downloader', 'completed', 100, '数据下载完成')
            
            analyses = {}
            
            parallel_agents = ['technical_analyst', 'fundamental_analyst', 'risk_manager', 'sentiment_analyst']
            
            logger.debug(f"[股票分析] 启动并行代理: {parallel_agents}")
            
            # 使用线程池并行执行代理分析
            with ThreadPoolExecutor(max_workers=len(parallel_agents)) as executor:
                future_to_agent = {
                    executor.submit(self.agents[agent_type].analyze, stock_data): agent_type 
                    for agent_type in parallel_agents
                }
                
                for future in as_completed(future_to_agent):
                    agent_type = future_to_agent[future]
                    try:
                        logger.debug(f"[股票分析] 开始 {agent_type} 分析...")
                        self._notify(f"启动 {self.agents[agent_type].name} 分析...")
                        result = future.result()
                        logger.debug(f"[股票分析] {agent_type} 分析完成: {result}")
                        analyses[agent_type] = result
                    except Exception as e:
                        logger.error(f"[股票分析] {agent_type} 分析失败: {e}")
                        self._notify(f"{self.agents[agent_type].name} 分析失败: {str(e)}")
                        analyses[agent_type] = {
                            'error': str(e),
                            'agent_name': self.agents[agent_type].name
                        }
            
            logger.debug("[股票分析] 汇总分析结果...")
            self._notify("正在汇总分析结果...")
            
            stock_data['analyses'] = analyses
            
            try:
                logger.debug("[股票分析] 启动投资策略制定...")
                self._notify(f"启动 {self.agents['investment_strategist'].name} 制定策略...")
                strategy_result = self.agents['investment_strategist'].analyze(stock_data)
                logger.debug(f"[股票分析] 投资策略制定完成: {strategy_result}")
                analyses['investment_strategist'] = strategy_result
            except Exception as e:
                logger.error(f"[股票分析] 投资策略制定失败: {e}")
                self._notify(f"{self.agents['investment_strategist'].name} 制定策略失败: {str(e)}")
                analyses['investment_strategist'] = {
                    'error': str(e),
                    'agent_name': self.agents['investment_strategist'].name
                }
            
            logger.info("[股票分析] 股票分析完成")
            self._notify("分析完成！")
            
            # 打印性能统计报告
            print_stats()
            
            return {
                'stock_code': stock_code,
                'stock_name': stock_data['stock_name'],
                'current_price': stock_data['current_price'],
                'analyses': analyses,
                'stock_data': stock_data,
                'status': 'completed'
            }
        
        except Exception as e:
            logger.error(f"[股票分析] 分析失败: {e}")
            import traceback
            logger.exception("[股票分析] 分析失败详细信息:")
            self._notify(f"分析失败: {str(e)}")
            
            # 打印性能统计报告（即使失败）
            print_stats()
            
            return {
                'stock_code': stock_code,
                'error': str(e),
                'status': 'failed'
            }
    
    def get_agent_info(self) -> List[Dict[str, Any]]:
        agent_info = []
        for agent_type, agent in self.agents.items():
            agent_info.append({
                'agent_type': agent_type,
                'name': agent.name,
                'title': agent.title,
                'icon': agent.icon,
                'color': agent.color
            })
        return agent_info
    
    @performance_monitor
    def backtest_strategy(self, stock_code: str, strategy_content: str = None, strategy_signals: Dict[str, Any] = None) -> Dict[str, Any]:
        # 重置性能统计
        reset_stats()
        logger.info(f"[策略回测] 开始回测股票代码: {stock_code}")
        self._notify(f"开始回测股票 {stock_code} 的策略...")
        
        try:
            logger.debug("[策略回测] 获取回测历史数据...")
            self._notify("正在获取历史数据...")
            
            kline_data = self.data_fetcher.get_kline_data(stock_code)
            
            if kline_data.empty:
                raise Exception("无法获取历史K线数据")
            
            logger.debug(f"[策略回测] 历史数据获取成功, 长度: {len(kline_data)}")
            
            if strategy_signals is None:
                strategy_signals = {}
            
            logger.debug("[策略回测] 运行回测引擎...")
            self._notify("正在运行回测引擎...")
            
            backtest_result = self.backtest_engine.run_backtest(
                stock_data=kline_data,
                strategy_signals=strategy_signals,
                strategy_content=strategy_content
            )
            
            logger.debug("[策略回测] 生成可视化图表...")
            self._notify("正在生成回测可视化...")
            
            visualizations = {
                'equity_curve': self.backtest_visualizer.generate_equity_curve_chart(backtest_result),
                'drawdown': self.backtest_visualizer.generate_drawdown_chart(backtest_result),
                'trade_distribution': self.backtest_visualizer.generate_trade_distribution_chart(backtest_result),
                'metrics_dashboard': self.backtest_visualizer.generate_metrics_dashboard(backtest_result)
            }
            
            backtest_result['visualizations'] = visualizations
            
            logger.debug("[策略回测] 生成回测报告...")
            self._notify("正在生成回测报告...")
            
            report = self.backtest_engine.generate_backtest_report(backtest_result)
            backtest_result['report'] = report
            
            logger.info("[策略回测] 回测完成")
            self._notify("回测完成！")
            
            # 打印性能统计报告
            print_stats()
            
            return {
                'stock_code': stock_code,
                'backtest_result': backtest_result,
                'status': 'completed'
            }
        
        except Exception as e:
            logger.error(f"[策略回测] 回测失败: {e}")
            import traceback
            logger.exception("[策略回测] 回测失败详细信息:")
            self._notify(f"回测失败: {str(e)}")
            
            # 打印性能统计报告（即使失败）
            print_stats()
            
            return {
                'stock_code': stock_code,
                'error': str(e),
                'status': 'failed'
            }
