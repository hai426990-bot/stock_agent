import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4')
    FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    AGENT_TEMPERATURE = 0.3
    AGENT_MAX_TOKENS = 2048
    AGENT_TOP_P = 0.95
    AGENT_FREQUENCY_PENALTY = 0
    AGENT_PRESENCE_PENALTY = 0
    AGENT_TIMEOUT = 180
    
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
