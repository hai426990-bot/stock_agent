from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from config import Config
import time

class BaseAgent(ABC):
    def __init__(self, agent_type: str, callback: Optional[Callable] = None, session_id: Optional[str] = None):
        self.agent_type = agent_type
        self.config = Config.AGENT_CONFIGS[agent_type]
        self.name = self.config['name']
        self.title = self.config['title']
        self.icon = self.config['icon']
        self.color = self.config['color']
        self.callback = callback
        self.session_id = session_id
        
        self.llm = ChatOpenAI(
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_BASE_URL,
            model=Config.OPENAI_MODEL,
            temperature=Config.AGENT_TEMPERATURE,
            max_tokens=Config.AGENT_MAX_TOKENS,
            top_p=Config.AGENT_TOP_P,
            frequency_penalty=Config.AGENT_FREQUENCY_PENALTY,
            presence_penalty=Config.AGENT_PRESENCE_PENALTY,
            timeout=Config.AGENT_TIMEOUT,
            extra_body={"thinking": {"type": "enable"}}
        )
        
        self.system_prompt = self._get_system_prompt()
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}")
        ])
        
        self.chain = self.prompt_template | self.llm
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        pass
    
    def _notify(self, status: str, progress: int, message: str = ""):
        if self.callback:
            self.callback({
                'agent_type': self.agent_type,
                'agent_name': self.name,
                'agent_title': self.title,
                'agent_icon': self.icon,
                'agent_color': self.color,
                'status': status,
                'progress': progress,
                'message': message,
                'session_id': self.session_id
            })
    
    def _notify_stream(self, chunk: str):
        if self.callback:
            self.callback({
                'agent_type': self.agent_type,
                'agent_name': self.name,
                'agent_title': self.title,
                'agent_icon': self.icon,
                'agent_color': self.color,
                'status': 'streaming',
                'progress': 0,
                'message': chunk,
                'is_stream': True,
                'session_id': self.session_id
            })
    
    def analyze(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        self._notify('analyzing', 10, f"{self.name}开始分析...")
        
        try:
            analysis_input = self._prepare_input(stock_data)
            self._notify('analyzing', 30, f"{self.name}正在分析数据...")
            
            messages = [
                ("system", self.system_prompt),
                ("human", analysis_input)
            ]
            
            print(f"[DEBUG] {self.name}: Sending request to LLM with timeout {Config.AGENT_TIMEOUT}s")
            start_time = time.time()
            response = self.llm.invoke(messages)
            end_time = time.time()
            print(f"[DEBUG] {self.name}: LLM response received after {end_time - start_time:.2f}s")
            
            full_response = response.content
            
            self._notify('analyzing', 90, f"{self.name}正在生成报告...")
            
            analysis_result = self._parse_result(full_response)
            self._notify('completed', 100, f"{self.name}分析完成")
            
            return {
                'agent_type': self.agent_type,
                'agent_name': self.name,
                'agent_title': self.title,
                'agent_icon': self.icon,
                'agent_color': self.color,
                'result': analysis_result,
                'raw_response': full_response
            }
        except Exception as e:
            print(f"[DEBUG] {self.name}: Analysis error: {str(e)}")
            self._notify('error', 0, f"{self.name}分析出错: {str(e)}")
            raise
    
    @abstractmethod
    def _prepare_input(self, stock_data: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def _parse_result(self, result: str) -> Dict[str, Any]:
        pass
