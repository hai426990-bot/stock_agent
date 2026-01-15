"""
日志系统配置模块

提供统一的日志记录接口,支持不同级别的日志输出、文件存储和格式化。
替换项目中的print语句,提供更专业的日志管理。
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
from config import get_config_manager


class Logger:
    """
    统一日志管理器
    
    功能:
    - 支持控制台和文件双输出
    - 支持日志级别动态配置
    - 支持彩色日志输出
    - 支持日志文件轮转
    """
    
    _loggers = {}
    _initialized = False
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }
    
    # Emoji映射
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '💥'
    }
    
    @classmethod
    def setup(cls, log_dir: Optional[Path] = None, log_level: str = 'INFO'):
        """
        初始化日志系统
        
        Args:
            log_dir: 日志文件存储目录,默认为项目根目录下的logs文件夹
            log_level: 日志级别,默认为INFO
        """
        if cls._initialized:
            return
        
        config_manager = get_config_manager()
        
        # 从配置读取日志设置,但优先使用传入的参数
        config_log_level = config_manager.get("logging.level", log_level)
        log_level = log_level if log_level != 'INFO' else config_log_level
        log_to_file = config_manager.get("logging.file.enabled", True)
        log_to_console = config_manager.get("logging.console.enabled", True)
        
        # 设置日志目录
        if log_dir is None:
            project_root = Path(__file__).parent
            log_dir = project_root / "logs"
        
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # 移除现有的处理器
        root_logger.handlers.clear()
        
        # 创建格式化器
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器(带颜色)
        if log_to_console:
            console_handler = ColoredConsoleHandler()
            console_handler.setLevel(getattr(logging, log_level.upper()))
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # 文件处理器
        if log_to_file:
            log_file = log_dir / f"alphaflow_{datetime.now().strftime('%Y%m%d')}.log"
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(getattr(logging, log_level.upper()))
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        
        cls._initialized = True
        
        # 记录初始化信息
        logger = cls.get_logger(__name__)
        logger.info("=" * 60)
        logger.info("AlphaFlow 日志系统初始化完成")
        logger.info(f"日志级别: {log_level}")
        logger.info(f"日志目录: {log_dir}")
        logger.info("=" * 60)
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        获取日志记录器
        
        Args:
            name: 日志记录器名称,通常使用 __name__
            
        Returns:
            日志记录器实例
        """
        if not cls._initialized:
            cls.setup()
        
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        
        return cls._loggers[name]


class ColoredConsoleHandler(logging.StreamHandler):
    """
    带颜色输出的控制台处理器
    
    支持不同日志级别的颜色显示和Emoji图标
    """
    
    def emit(self, record):
        """
        发出日志记录
        
        Args:
            record: 日志记录对象
        """
        try:
            # 添加颜色和Emoji
            level_name = record.levelname
            color = Logger.COLORS.get(level_name, '')
            emoji = Logger.EMOJIS.get(level_name, '')
            reset = Logger.COLORS['RESET']
            
            # 修改消息格式
            original_msg = record.getMessage()
            colored_msg = f"{color}{emoji} {original_msg}{reset}"
            
            # 更新记录的消息
            record.msg = colored_msg
            record.args = ()
            
            # 调用父类的emit方法
            super().emit(record)
        except Exception:
            self.handleError(record)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器的便捷函数
    
    Args:
        name: 日志记录器名称
        
    Returns:
        日志记录器实例
        
    Example:
        >>> from logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("这是一条信息")
    """
    return Logger.get_logger(name)


# 便捷函数
def debug(msg: str, *args, **kwargs):
    """记录DEBUG级别日志"""
    get_logger(__name__).debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """记录INFO级别日志"""
    get_logger(__name__).info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """记录WARNING级别日志"""
    get_logger(__name__).warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """记录ERROR级别日志"""
    get_logger(__name__).error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    """记录CRITICAL级别日志"""
    get_logger(__name__).critical(msg, *args, **kwargs)


# 模块加载时自动初始化
Logger.setup()