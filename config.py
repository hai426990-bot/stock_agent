import os
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()

class Config:
    OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY', '')
    OPENAI_BASE_URL: str = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-4')
    FLASK_SECRET_KEY: str = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
    FLASK_DEBUG: bool = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    AGENT_TEMPERATURE: float = 0.3
    AGENT_MAX_TOKENS: int = 2048
    AGENT_TOP_P: float = 0.95
    AGENT_FREQUENCY_PENALTY: float = 0
    AGENT_PRESENCE_PENALTY: float = 0
    AGENT_TIMEOUT: int = 300
    
    @classmethod
    def validate(cls) -> Dict[str, Any]:
        """验证配置是否完整"""
        errors = []
        warnings = []
        
        if not cls.OPENAI_API_KEY:
            errors.append('OPENAI_API_KEY 未设置，请在.env文件中配置')
        
        if cls.FLASK_SECRET_KEY == 'dev-secret-key' and not cls.FLASK_DEBUG:
            warnings.append('FLASK_SECRET_KEY 使用默认值，建议在生产环境中设置强密钥')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    AGENT_CONFIGS = {
        'technical_analyst': {
            'name': '张技术',
            'title': '技术分析师',
            'icon': '📈',
            'color': '#3498db'
        },
        'fundamental_analyst': {
            'name': '李价值',
            'title': '基本面分析师',
            'icon': '💰',
            'color': '#2ecc71'
        },
        'risk_manager': {
            'name': '王风控',
            'title': '风险控制专家',
            'icon': '⚠️',
            'color': '#e74c3c'
        },
        'sentiment_analyst': {
            'name': '赵情绪',
            'title': '市场情绪分析师',
            'icon': '😊',
            'color': '#9b59b6'
        },
        'investment_strategist': {
            'name': '陈策略',
            'title': '投资策略师',
            'icon': '🎯',
            'color': '#f39c12'
        },
        'sector_analyst': {
            'name': '刘板块',
            'title': '板块分析师',
            'icon': '🏢',
            'color': '#1abc9c'
        },
        'sector_technical_analyst': {
            'name': '孙板块技术',
            'title': '板块技术分析师',
            'icon': '📊',
            'color': '#3498db'
        },
        'sector_fundamental_analyst': {
            'name': '周板块基本面',
            'title': '板块基本面分析师',
            'icon': '💹',
            'color': '#2ecc71'
        },
        'sector_risk_analyst': {
            'name': '吴板块风险',
            'title': '板块风险分析师',
            'icon': '🛡️',
            'color': '#e74c3c'
        }
    }
