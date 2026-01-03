import time
from functools import wraps
from typing import Dict, Any, Callable
import threading
from .logger import logger

# 性能统计存储
performance_stats: Dict[str, Any] = {
    'function_calls': {},
    'total_time': 0.0,
    'start_time': time.time()
}

_stats_lock = threading.Lock()

def reset_stats():
    """重置性能统计"""
    global performance_stats
    with _stats_lock:
        performance_stats = {
            'function_calls': {},
            'total_time': 0.0,
            'start_time': time.time()
        }

def get_stats():
    """获取性能统计信息"""
    return performance_stats

def performance_monitor(func: Callable) -> Callable:
    """性能监控装饰器，用于测量函数执行时间"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        # 执行原始函数
        result = func(*args, **kwargs)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 更新性能统计
        func_name = func.__qualname__
        with _stats_lock:
            if func_name not in performance_stats['function_calls']:
                performance_stats['function_calls'][func_name] = {
                    'call_count': 0,
                    'total_time': 0.0,
                    'avg_time': 0.0,
                    'min_time': float('inf'),
                    'max_time': 0.0
                }
            
            func_stats = performance_stats['function_calls'][func_name]
            func_stats['call_count'] += 1
            func_stats['total_time'] += elapsed_time
            func_stats['avg_time'] = func_stats['total_time'] / func_stats['call_count']
            func_stats['min_time'] = min(func_stats['min_time'], elapsed_time)
            func_stats['max_time'] = max(func_stats['max_time'], elapsed_time)
            
            performance_stats['total_time'] = end_time - performance_stats['start_time']
        
        logger.debug(f"[性能监控] {func_name} 执行时间: {elapsed_time:.4f}秒")
        
        return result
    
    return wrapper

def print_stats():
    """打印性能统计信息"""
    with _stats_lock:
        total_time = performance_stats.get('total_time', 0.0)
        function_calls = dict(performance_stats.get('function_calls', {}))
    
    logger.info("[性能监控] ====== 性能统计报告 ======")
    logger.info(f"[性能监控] 总运行时间: {total_time:.4f}秒")
    logger.info(f"[性能监控] 函数调用统计:")
    
    for func_name, stats in function_calls.items():
        logger.info(f"[性能监控]   {func_name}:")
        logger.info(f"[性能监控]     调用次数: {stats['call_count']}")
        logger.info(f"[性能监控]     总时间: {stats['total_time']:.4f}秒")
        logger.info(f"[性能监控]     平均时间: {stats['avg_time']:.4f}秒")
        logger.info(f"[性能监控]     最小时间: {stats['min_time']:.4f}秒")
        logger.info(f"[性能监控]     最大时间: {stats['max_time']:.4f}秒")
    
    logger.info("[性能监控] =========================")
