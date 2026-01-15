"""
异常处理模块

定义项目中使用的自定义异常类,提供统一的错误处理机制。
"""

from typing import Optional, Any, Dict
from logger import get_logger

logger = get_logger(__name__)


class AlphaFlowException(Exception):
    """
    AlphaFlow 基础异常类
    
    所有自定义异常的基类,提供统一的异常处理接口。
    """
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        初始化异常
        
        Args:
            message: 错误消息
            error_code: 错误代码,用于错误分类和追踪
            details: 错误详细信息字典
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        
        # 记录异常日志
        logger.error(f"[{self.error_code}] {message}", extra=self.details)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将异常转换为字典格式
        
        Returns:
            包含异常信息的字典
        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }
    
    def __str__(self) -> str:
        """返回异常的字符串表示"""
        if self.details:
            return f"[{self.error_code}] {self.message} - Details: {self.details}"
        return f"[{self.error_code}] {self.message}"


class ConfigurationError(AlphaFlowException):
    """
    配置错误
    
    当配置文件缺失、格式错误或配置值无效时抛出。
    """
    
    def __init__(self, message: str, config_key: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        初始化配置错误
        
        Args:
            message: 错误消息
            config_key: 导致错误的配置键
            details: 错误详细信息
        """
        if details is None:
            details = {}
        if config_key:
            details["config_key"] = config_key
        
        super().__init__(message, error_code="CONFIG_ERROR", details=details)


class DataFetchError(AlphaFlowException):
    """
    数据获取错误
    
    当从数据源获取数据失败时抛出。
    """
    
    def __init__(self, message: str, source: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        初始化数据获取错误
        
        Args:
            message: 错误消息
            source: 数据源名称
            details: 错误详细信息
        """
        if details is None:
            details = {}
        if source:
            details["source"] = source
        
        super().__init__(message, error_code="DATA_FETCH_ERROR", details=details)


class BacktestError(AlphaFlowException):
    """
    回测错误
    
    当回测过程中发生错误时抛出。
    """
    
    def __init__(self, message: str, strategy: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        初始化回测错误
        
        Args:
            message: 错误消息
            strategy: 策略名称
            details: 错误详细信息
        """
        if details is None:
            details = {}
        if strategy:
            details["strategy"] = strategy
        
        super().__init__(message, error_code="BACKTEST_ERROR", details=details)


class AgentError(AlphaFlowException):
    """
    代理错误
    
    当智能体执行过程中发生错误时抛出。
    """
    
    def __init__(self, message: str, agent_name: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        初始化代理错误
        
        Args:
            message: 错误消息
            agent_name: 代理名称
            details: 错误详细信息
        """
        if details is None:
            details = {}
        if agent_name:
            details["agent_name"] = agent_name
        
        super().__init__(message, error_code="AGENT_ERROR", details=details)


class LLMError(AlphaFlowException):
    """
    LLM调用错误
    
    当调用大语言模型API失败时抛出。
    """
    
    def __init__(self, message: str, model: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        初始化LLM错误
        
        Args:
            message: 错误消息
            model: 模型名称
            details: 错误详细信息
        """
        if details is None:
            details = {}
        if model:
            details["model"] = model
        
        super().__init__(message, error_code="LLM_ERROR", details=details)


class ValidationError(AlphaFlowException):
    """
    验证错误
    
    当数据验证失败时抛出。
    """
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        初始化验证错误
        
        Args:
            message: 错误消息
            field: 验证失败的字段名
            details: 错误详细信息
        """
        if details is None:
            details = {}
        if field:
            details["field"] = field
        
        super().__init__(message, error_code="VALIDATION_ERROR", details=details)


class CacheError(AlphaFlowException):
    """
    缓存错误
    
    当缓存操作失败时抛出。
    """
    
    def __init__(self, message: str, cache_key: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        初始化缓存错误
        
        Args:
            message: 错误消息
            cache_key: 缓存键
            details: 错误详细信息
        """
        if details is None:
            details = {}
        if cache_key:
            details["cache_key"] = cache_key
        
        super().__init__(message, error_code="CACHE_ERROR", details=details)


def handle_exception(exc: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    统一的异常处理函数
    
    将异常转换为统一的错误响应格式。
    
    Args:
        exc: 异常对象
        context: 额外的上下文信息
        
    Returns:
        标准化的错误响应字典
    """
    if isinstance(exc, AlphaFlowException):
        # 已知的自定义异常
        error_response = exc.to_dict()
    else:
        # 未知的异常
        logger.exception(f"未处理的异常: {str(exc)}")
        error_response = {
            "error_code": "UNKNOWN_ERROR",
            "message": str(exc),
            "details": {
                "exception_type": type(exc).__name__,
                "context": context or {}
            }
        }
    
    return error_response


def safe_execute(func, *args, default_return: Any = None, **kwargs):
    """
    安全执行函数,捕获并记录异常
    
    Args:
        func: 要执行的函数
        *args: 函数的位置参数
        default_return: 发生异常时返回的默认值
        **kwargs: 函数的关键字参数
        
    Returns:
        函数执行结果或默认值
    """
    try:
        return func(*args, **kwargs)
    except AlphaFlowException as e:
        logger.error(f"函数执行失败: {e}")
        return default_return
    except Exception as e:
        logger.exception(f"未预期的错误: {e}")
        return default_return


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """
    重试装饰器
    
    在函数执行失败时自动重试。
    
    Args:
        max_retries: 最大重试次数
        delay: 重试之间的延迟(秒)
        exceptions: 需要重试的异常类型
        
    Returns:
        装饰器函数
    """
    import time
    import functools
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(f"函数 {func.__name__} 执行失败,第 {attempt + 1} 次重试... 错误: {e}")
                        time.sleep(delay)
                    else:
                        logger.error(f"函数 {func.__name__} 执行失败,已达最大重试次数 {max_retries}")
            
            raise last_exception
        
        return wrapper
    return decorator