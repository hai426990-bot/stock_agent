from langgraph.graph import StateGraph, END
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 定义工作流状态模型
class AnalysisState(BaseModel):
    """分析工作流状态模型"""
    stock_code: Optional[str] = None           # 股票代码
    sector_name: Optional[str] = None          # 板块名称
    analysis_type: str = 'stock'              # 分析类型: 'stock' 或 'sector'
    status: str = 'init'                       # 工作流状态: init, downloading, analyzing, completed, failed
    stock_data: Optional[Dict[str, Any]] = None  # 股票数据
    sector_data: Optional[Dict[str, Any]] = None  # 板块数据
    analyses: Dict[str, Any] = {}             # 各分析师分析结果
    error: Optional[str] = None               # 错误信息
    timestamp: str = datetime.now().isoformat()  # 时间戳

# 定义工作流节点
class AnalysisWorkflow:
    def __init__(self, stock_agent):
        self.stock_agent = stock_agent
        self.workflow = self._build_workflow()
    
    def _build_workflow(self):
        """构建分析工作流"""
        # 使用Pydantic模型作为状态模式
        workflow = StateGraph(AnalysisState)
        
        # 添加节点
        workflow.add_node('download_data', self.download_data)
        workflow.add_node('analyze_data', self.analyze_data)
        workflow.add_node('generate_report', self.generate_report)
        workflow.add_node('handle_error', self.handle_error)
        
        # 添加边
        workflow.set_entry_point('download_data')
        
        # 添加条件边
        workflow.add_conditional_edges(
            'download_data',
            self.should_continue,
            {
                'continue': 'analyze_data',
                'error': 'handle_error'
            }
        )
        
        workflow.add_conditional_edges(
            'analyze_data',
            self.should_continue,
            {
                'continue': 'generate_report',
                'error': 'handle_error'
            }
        )
        
        workflow.add_conditional_edges(
            'generate_report',
            self.should_continue,
            {
                'continue': END,
                'error': 'handle_error'
            }
        )
        
        # 编译工作流
        return workflow.compile()
    
    def download_data(self, state: AnalysisState) -> AnalysisState:
        """下载数据节点"""
        logger.info(f"[工作流] download_data节点开始执行，当前状态: {state.status}, 分析类型: {state.analysis_type}")
        
        try:
            logger.info(f"[工作流] 开始下载数据，类型: {state.analysis_type}")
            
            if state.analysis_type == 'stock':
                # 下载股票数据
                logger.debug(f"[工作流] 开始下载股票数据，股票代码: {state.stock_code}")
                self.stock_agent._notify_agent('data_downloader', 'analyzing', 10, '开始下载股票数据...')
                stock_data = self.stock_agent.data_fetcher.get_comprehensive_data(state.stock_code)
                logger.debug(f"[工作流] 股票数据下载完成，数据类型: {type(stock_data)}")
                self.stock_agent._notify_agent('data_downloader', 'completed', 100, '股票数据下载完成')
                new_state = state.model_copy(update={
                    'status': 'downloaded',
                    'stock_data': stock_data,
                    'error': None
                })
                logger.info(f"[工作流] download_data节点完成，新状态: {new_state.status}")
                return new_state
            elif state.analysis_type == 'sector':
                # 下载板块数据
                logger.debug(f"[工作流] 开始下载板块数据，板块名称: {state.sector_name}")
                self.stock_agent._notify_agent('data_downloader', 'analyzing', 10, '开始下载板块数据...')
                sector_data = self.stock_agent.data_fetcher.get_sector_data(state.sector_name)
                logger.debug(f"[工作流] 板块数据下载完成，数据类型: {type(sector_data)}")
                self.stock_agent._notify_agent('data_downloader', 'completed', 100, '板块数据下载完成')
                new_state = state.model_copy(update={
                    'status': 'downloaded',
                    'sector_data': sector_data,
                    'error': None
                })
                logger.info(f"[工作流] download_data节点完成，新状态: {new_state.status}")
                return new_state
            else:
                raise ValueError(f"不支持的分析类型: {state.analysis_type}")
        except Exception as e:
            logger.error(f"[工作流] 数据下载失败: {e}")
            import traceback
            logger.error(f"[工作流] 数据下载失败堆栈: {traceback.format_exc()}")
            self.stock_agent._notify_agent('data_downloader', 'failed', 0, f'数据下载失败: {e}')
            new_state = state.model_copy(update={
                'status': 'failed',
                'error': str(e)
            })
            logger.info(f"[工作流] download_data节点失败，新状态: {new_state.status}")
            return new_state
    
    def analyze_data(self, state: AnalysisState) -> AnalysisState:
        """分析数据节点"""
        logger.info(f"[工作流] analyze_data节点开始执行，当前状态: {state.status}, 分析类型: {state.analysis_type}")
        
        try:
            logger.info(f"[工作流] 开始分析数据，类型: {state.analysis_type}")
            
            if state.analysis_type == 'stock':
                # 分析股票数据
                logger.debug(f"[工作流] 开始分析股票数据，股票代码: {state.stock_code}")
                result = self.stock_agent.analyze_stock(state.stock_code)
                new_state = state.model_copy(update={
                    'status': 'analyzed',
                    'analyses': result['analyses'],
                    'error': None
                })
                logger.info(f"[工作流] analyze_data节点完成，新状态: {new_state.status}")
                return new_state
            elif state.analysis_type == 'sector':
                # 分析板块数据 - 直接运行板块分析师
                sector_data = state.sector_data
                analyses = {}
                
                logger.info(f"[工作流] 板块数据类型: {type(sector_data)}")
                logger.info(f"[工作流] 板块数据键: {sector_data.keys() if isinstance(sector_data, dict) else 'N/A'}")
                logger.debug(f"[工作流] 启动板块分析师...")
                
                # 使用多个板块分析师进行分析
                sector_analysts = [
                    ('sector_analyst', '板块分析师'),
                    ('sector_technical_analyst', '板块技术分析师'),
                    ('sector_fundamental_analyst', '板块基本面分析师'),
                    ('sector_risk_analyst', '板块风险分析师')
                ]
                
                for agent_key, agent_name in sector_analysts:
                    try:
                        logger.info(f"[工作流] 开始执行 {agent_name} (agent_key: {agent_key})")
                        analyst = self.stock_agent.agents[agent_key]
                        self.stock_agent._notify(f"启动 {analyst.name} 分析...")
                        logger.debug(f"[工作流] 调用 {agent_name}.analyze() 方法...")
                        result = analyst.analyze(sector_data)
                        logger.info(f"[工作流] {agent_name}分析完成，结果类型: {type(result)}")
                        analyses[agent_key] = result
                    except Exception as e:
                        logger.error(f"[工作流] {agent_name}分析失败: {e}")
                        import traceback
                        logger.error(f"[工作流] {agent_name}分析失败堆栈: {traceback.format_exc()}")
                        analyses[agent_key] = {
                            'error': str(e),
                            'status': 'failed'
                        }
                
                logger.info(f"[工作流] 所有板块分析师执行完成，分析结果数量: {len(analyses)}")
                self.stock_agent._notify("板块分析完成！")
                
                new_state = state.model_copy(update={
                    'status': 'analyzed',
                    'analyses': analyses,
                    'error': None
                })
                logger.info(f"[工作流] analyze_data节点完成，新状态: {new_state.status}")
                return new_state
            else:
                raise ValueError(f"不支持的分析类型: {state.analysis_type}")
        except Exception as e:
            logger.error(f"[工作流] 数据分析失败: {e}")
            import traceback
            logger.error(f"[工作流] 数据分析失败堆栈: {traceback.format_exc()}")
            new_state = state.model_copy(update={
                'status': 'failed',
                'error': str(e)
            })
            logger.info(f"[工作流] analyze_data节点失败，新状态: {new_state.status}")
            return new_state
    
    def generate_report(self, state: AnalysisState) -> AnalysisState:
        """生成报告节点"""
        logger.info(f"[工作流] generate_report节点开始执行，当前状态: {state.status}, 分析类型: {state.analysis_type}")
        
        try:
            logger.info(f"[工作流] 开始生成报告，类型: {state.analysis_type}")
            
            # 确保所有分析师结果都已完成
            all_completed = all(
                analysis.get('status', 'completed') == 'completed' 
                for analysis in state.analyses.values()
            )
            
            logger.info(f"[工作流] 所有分析师完成状态: {all_completed}")
            
            if all_completed:
                new_state = state.model_copy(update={
                    'status': 'completed',
                    'error': None,
                    'timestamp': datetime.now().isoformat()
                })
                logger.info(f"[工作流] generate_report节点完成，新状态: {new_state.status}")
                return new_state
            else:
                raise Exception("部分分析师分析失败")
        except Exception as e:
            logger.error(f"[工作流] 报告生成失败: {e}")
            import traceback
            logger.error(f"[工作流] 报告生成失败堆栈: {traceback.format_exc()}")
            new_state = state.model_copy(update={
                'status': 'failed',
                'error': str(e)
            })
            logger.info(f"[工作流] generate_report节点失败，新状态: {new_state.status}")
            return new_state
    
    def handle_error(self, state: AnalysisState) -> AnalysisState:
        """处理错误节点"""
        logger.info(f"[工作流] handle_error节点开始执行，当前状态: {state.status}, 错误: {state.error}")
        logger.error(f"[工作流] 处理错误: {state.error}")
        new_state = state.model_copy(update={
            'status': 'failed',
            'timestamp': datetime.now().isoformat()
        })
        logger.info(f"[工作流] handle_error节点完成，新状态: {new_state.status}")
        return new_state
    
    def should_continue(self, state: AnalysisState) -> str:
        """条件判断函数"""
        should_continue = 'continue' if state.status != 'failed' else 'error'
        logger.debug(f"[工作流] should_continue判断: status={state.status}, result={should_continue}")
        return should_continue
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """运行工作流"""
        logger.info(f"[工作流] ========== 启动工作流 ==========")
        logger.info(f"[工作流] 输入数据: {input_data}")
        
        # 将输入字典转换为AnalysisState对象
        input_state = AnalysisState(**input_data)
        logger.info(f"[工作流] 初始状态: status={input_state.status}, type={input_state.analysis_type}")
        
        # 运行工作流
        logger.info(f"[工作流] 开始执行工作流...")
        result_dict = self.workflow.invoke(input_state)
        
        logger.info(f"[工作流] 工作流完成: status={result_dict.get('status')}")
        logger.info(f"[工作流] 最终状态: {result_dict}")
        logger.info(f"[工作流] ========== 工作流结束 ==========")
        
        # 直接返回字典结果
        return result_dict
