from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime
from agents.technical_analyst import TechnicalAnalyst
from agents.fundamental_analyst import FundamentalAnalyst
from agents.risk_manager import RiskManager
from agents.sentiment_analyst import SentimentAnalyst
from agents.investment_strategist import InvestmentStrategist
from tools.data_fetcher import DataFetcher
from tools.stock_analyzer import StockAnalyzer
from tools.backtest_engine import BacktestEngine
from tools.backtest_visualizer import BacktestVisualizer

class StockAgent:
    def __init__(self, callback=None, session_id=None):
        self.data_fetcher = DataFetcher()
        self.stock_analyzer = StockAnalyzer()
        self.callback = callback
        self.session_id = session_id
        self.backtest_engine = BacktestEngine()
        self.backtest_visualizer = BacktestVisualizer()
        
        self.agents = {
            'technical_analyst': TechnicalAnalyst(callback, session_id),
            'fundamental_analyst': FundamentalAnalyst(callback, session_id),
            'risk_manager': RiskManager(callback, session_id),
            'sentiment_analyst': SentimentAnalyst(callback, session_id),
            'investment_strategist': InvestmentStrategist(callback, session_id)
        }
    
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
    
    def analyze_stock(self, stock_code: str) -> Dict[str, Any]:
        print(f"[DEBUG] Starting analysis for stock code: {stock_code}")
        self._notify(f"开始分析股票 {stock_code}...")
        
        self._notify_agent('data_downloader', 'analyzing', 10, '开始下载数据...')
        
        try:
            print("[DEBUG] Fetching stock information...")
            self._notify("正在获取股票基本信息...")
            self._notify_agent('data_downloader', 'analyzing', 20, '正在获取股票基本信息...')
            stock_info = self.data_fetcher.get_stock_info(stock_code)
            print(f"[DEBUG] Stock information retrieved: {stock_info}")
            
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
                'timestamp': stock_info.get('timestamp', datetime.now().isoformat())
            }
            
            print("[DEBUG] Fetching K-line data...")
            self._notify("正在获取K线数据...")
            self._notify_agent('data_downloader', 'analyzing', 40, '正在获取K线数据...')
            kline_data = self.data_fetcher.get_kline_data(stock_code)
            print(f"[DEBUG] K-line data retrieved, length: {len(kline_data) if isinstance(kline_data, pd.DataFrame) else 'N/A'}")
            if isinstance(kline_data, pd.DataFrame) and not kline_data.empty:
                kline_data = kline_data.to_dict('records')
            stock_data['kline_data'] = kline_data
            
            print("[DEBUG] Fetching financial data...")
            self._notify("正在获取财务数据...")
            self._notify_agent('data_downloader', 'analyzing', 60, '正在获取财务数据...')
            financial_data = self.data_fetcher.get_financial_data(stock_code)
            print(f"[DEBUG] Financial data retrieved: {financial_data}")
            stock_data['financial_data'] = financial_data
            
            print("[DEBUG] Fetching fund flow data...")
            self._notify("正在获取资金流向数据...")
            self._notify_agent('data_downloader', 'analyzing', 80, '正在获取资金流向数据...')
            fund_flow = self.data_fetcher.get_fund_flow(stock_code)
            print(f"[DEBUG] Fund flow data retrieved: {fund_flow}")
            stock_data['fund_flow'] = fund_flow
            
            print("[DEBUG] Fetching market sentiment data...")
            self._notify("正在获取市场情绪数据...")
            self._notify_agent('data_downloader', 'analyzing', 90, '正在获取市场情绪数据...')
            market_sentiment = self.data_fetcher.get_market_sentiment()
            print(f"[DEBUG] Market sentiment data retrieved: {market_sentiment}")
            stock_data['market_sentiment'] = market_sentiment
            
            print("[DEBUG] Calculating technical indicators...")
            self._notify("正在计算技术指标...")
            stock_data['technical_indicators'] = self.stock_analyzer.analyze_technical_indicators(stock_data)
            print(f"[DEBUG] Technical indicators calculated: {stock_data['technical_indicators']}")
            
            self._notify_agent('data_downloader', 'completed', 100, '数据下载完成')
            
            analyses = {}
            
            parallel_agents = ['technical_analyst', 'fundamental_analyst', 'risk_manager', 'sentiment_analyst']
            
            print(f"[DEBUG] Starting parallel agents: {parallel_agents}")
            for agent_type in parallel_agents:
                try:
                    print(f"[DEBUG] Starting {agent_type}...")
                    self._notify(f"启动 {self.agents[agent_type].name} 分析...")
                    result = self.agents[agent_type].analyze(stock_data)
                    print(f"[DEBUG] {agent_type} completed: {result}")
                    analyses[agent_type] = result
                except Exception as e:
                    print(f"[DEBUG] {agent_type} failed: {e}")
                    self._notify(f"{self.agents[agent_type].name} 分析失败: {str(e)}")
                    analyses[agent_type] = {
                        'error': str(e),
                        'agent_name': self.agents[agent_type].name
                    }
            
            print("[DEBUG] Summarizing analysis results...")
            self._notify("正在汇总分析结果...")
            
            stock_data['analyses'] = analyses
            
            try:
                print("[DEBUG] Starting investment strategist...")
                self._notify(f"启动 {self.agents['investment_strategist'].name} 制定策略...")
                strategy_result = self.agents['investment_strategist'].analyze(stock_data)
                print(f"[DEBUG] Investment strategist completed: {strategy_result}")
                analyses['investment_strategist'] = strategy_result
            except Exception as e:
                print(f"[DEBUG] Investment strategist failed: {e}")
                self._notify(f"{self.agents['investment_strategist'].name} 制定策略失败: {str(e)}")
                analyses['investment_strategist'] = {
                    'error': str(e),
                    'agent_name': self.agents['investment_strategist'].name
                }
            
            print("[DEBUG] Analysis completed successfully")
            self._notify("分析完成！")
            
            return {
                'stock_code': stock_code,
                'stock_name': stock_data['stock_name'],
                'current_price': stock_data['current_price'],
                'analyses': analyses,
                'stock_data': stock_data,
                'status': 'completed'
            }
        
        except Exception as e:
            print(f"[DEBUG] Analysis failed with error: {e}")
            import traceback
            traceback.print_exc()
            self._notify(f"分析失败: {str(e)}")
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
    
    def backtest_strategy(self, stock_code: str, strategy_content: str = None, strategy_signals: Dict[str, Any] = None) -> Dict[str, Any]:
        print(f"[DEBUG] Starting backtest for stock code: {stock_code}")
        self._notify(f"开始回测股票 {stock_code} 的策略...")
        
        try:
            print("[DEBUG] Fetching historical data for backtest...")
            self._notify("正在获取历史数据...")
            
            kline_data = self.data_fetcher.get_kline_data(stock_code)
            
            if kline_data.empty:
                raise Exception("无法获取历史K线数据")
            
            print(f"[DEBUG] Historical data retrieved, length: {len(kline_data)}")
            
            if strategy_signals is None:
                strategy_signals = {}
            
            print("[DEBUG] Running backtest engine...")
            self._notify("正在运行回测引擎...")
            
            backtest_result = self.backtest_engine.run_backtest(
                stock_data=kline_data,
                strategy_signals=strategy_signals,
                strategy_content=strategy_content
            )
            
            print("[DEBUG] Generating visualizations...")
            self._notify("正在生成回测可视化...")
            
            visualizations = {
                'equity_curve': self.backtest_visualizer.generate_equity_curve_chart(backtest_result),
                'drawdown': self.backtest_visualizer.generate_drawdown_chart(backtest_result),
                'trade_distribution': self.backtest_visualizer.generate_trade_distribution_chart(backtest_result),
                'metrics_dashboard': self.backtest_visualizer.generate_metrics_dashboard(backtest_result)
            }
            
            backtest_result['visualizations'] = visualizations
            
            print("[DEBUG] Generating backtest report...")
            self._notify("正在生成回测报告...")
            
            report = self.backtest_engine.generate_backtest_report(backtest_result)
            backtest_result['report'] = report
            
            print("[DEBUG] Backtest completed successfully")
            self._notify("回测完成！")
            
            return {
                'stock_code': stock_code,
                'backtest_result': backtest_result,
                'status': 'completed'
            }
        
        except Exception as e:
            print(f"[DEBUG] Backtest failed with error: {e}")
            import traceback
            traceback.print_exc()
            self._notify(f"回测失败: {str(e)}")
            return {
                'stock_code': stock_code,
                'error': str(e),
                'status': 'failed'
            }
