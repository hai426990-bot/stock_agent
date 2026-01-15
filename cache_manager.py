"""
缓存管理模块

提供统一的缓存管理功能,支持多种缓存策略和持久化方式。

功能特性:
    - TTL (Time To Live) 缓存
    - 文件持久化
    - 缓存统计和清理
    - 多级缓存支持
    - 缓存命中率监控
"""

import json
import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Callable
from functools import wraps
import pandas as pd
from logger import get_logger
from exceptions import CacheError

logger = get_logger(__name__)


class CacheEntry:
    """
    缓存条目类
    
    表示缓存中的一个条目,包含数据和元数据。
    """
    
    def __init__(self, data: Any, ttl: Optional[int] = None):
        """
        初始化缓存条目
        
        Args:
            data: 缓存的数据
            ttl: 生存时间(秒),None表示永不过期
        """
        self.data = data
        self.created_at = datetime.now()
        self.ttl = ttl
        self.access_count = 0
        self.last_accessed = self.created_at
    
    def is_expired(self) -> bool:
        """
        检查缓存是否过期
        
        Returns:
            bool: 如果已过期返回True,否则返回False
        """
        if self.ttl is None:
            return False
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl)
    
    def access(self) -> Any:
        """
        访问缓存数据
        
        Returns:
            Any: 缓存的数据
        """
        self.access_count += 1
        self.last_accessed = datetime.now()
        return self.data
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将缓存条目转换为字典(用于序列化)
        
        Returns:
            Dict[str, Any]: 可序列化的字典
        """
        return {
            "data": self._serialize_data(self.data),
            "created_at": self.created_at.isoformat(),
            "ttl": self.ttl,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat()
        }
    
    @staticmethod
    def from_dict(data_dict: Dict[str, Any]) -> 'CacheEntry':
        """
        从字典创建缓存条目
        
        Args:
            data_dict: 包含缓存信息的字典
            
        Returns:
            CacheEntry: 缓存条目对象
        """
        entry = CacheEntry(
            data=CacheEntry._deserialize_data(data_dict["data"]),
            ttl=data_dict.get("ttl")
        )
        entry.created_at = datetime.fromisoformat(data_dict["created_at"])
        entry.access_count = data_dict.get("access_count", 0)
        entry.last_accessed = datetime.fromisoformat(data_dict.get("last_accessed", data_dict["created_at"]))
        return entry
    
    @staticmethod
    def _serialize_data(data: Any) -> Any:
        """
        序列化数据
        
        Args:
            data: 要序列化的数据
            
        Returns:
            Any: 序列化后的数据
        """
        if isinstance(data, pd.DataFrame):
            return {
                "type": "DataFrame",
                "data": data.to_dict(orient='records')
            }
        elif isinstance(data, pd.Series):
            return {
                "type": "Series",
                "data": data.to_dict()
            }
        elif isinstance(data, (list, dict)):
            # 处理包含 Timestamp 的数据结构
            if isinstance(data, dict):
                return {k: CacheEntry._serialize_value(v) for k, v in data.items()}
            else:
                return [CacheEntry._serialize_value(v) for v in data]
        return data
    
    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """
        序列化单个值
        
        Args:
            value: 要序列化的值
            
        Returns:
            Any: 序列化后的值
        """
        if isinstance(value, pd.Timestamp):
            return {
                "type": "Timestamp",
                "value": value.isoformat()
            }
        elif isinstance(value, (list, dict)):
            return CacheEntry._serialize_data(value)
        return value
    
    @staticmethod
    def _deserialize_data(data: Any) -> Any:
        """
        反序列化数据
        
        Args:
            data: 要反序列化的数据
            
        Returns:
            Any: 反序列化后的数据
        """
        if isinstance(data, dict) and "type" in data:
            data_type = data["type"]
            if data_type == "DataFrame":
                return pd.DataFrame(data["data"])
            elif data_type == "Series":
                return pd.Series(data["data"])
            elif data_type == "Timestamp":
                return pd.Timestamp(data["value"])
        elif isinstance(data, (list, dict)):
            if isinstance(data, dict):
                return {k: CacheEntry._deserialize_value(v) for k, v in data.items()}
            else:
                return [CacheEntry._deserialize_value(v) for v in data]
        return data
    
    @staticmethod
    def _deserialize_value(value: Any) -> Any:
        """
        反序列化单个值
        
        Args:
            value: 要反序列化的值
            
        Returns:
            Any: 反序列化后的值
        """
        if isinstance(value, dict) and "type" in value:
            return CacheEntry._deserialize_data(value)
        elif isinstance(value, (list, dict)):
            return CacheEntry._deserialize_data(value)
        return value


class CacheManager:
    """
    缓存管理器
    
    提供统一的缓存管理接口,支持TTL、持久化、统计等功能。
    """
    
    def __init__(self, cache_file: Optional[str] = None, default_ttl: int = 3600):
        """
        初始化缓存管理器
        
        Args:
            cache_file: 缓存文件路径,默认为项目根目录下的.cache.json
            default_ttl: 默认TTL(秒),默认为1小时
        """
        if cache_file is None:
            project_root = Path(__file__).parent.parent
            cache_file = project_root / ".cache.json"
        
        self.cache_file = Path(cache_file)
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "errors": 0
        }
        
        # 加载持久化缓存
        self._load_cache()
        
        logger.info(f"缓存管理器初始化完成,缓存文件: {self.cache_file}")
    
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """
        生成缓存键
        
        Args:
            func_name: 函数名
            args: 位置参数
            kwargs: 关键字参数
            
        Returns:
            str: MD5哈希的缓存键
        """
        key_parts = [func_name]
        key_parts.extend([str(arg) for arg in args])
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    def get(self, func_name: str, args: tuple, kwargs: dict) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            func_name: 函数名
            args: 位置参数
            kwargs: 关键字参数
            
        Returns:
            Optional[Any]: 缓存的数据,如果不存在或已过期返回None
        """
        key = self._generate_key(func_name, args, kwargs)
        
        if key in self.cache:
            entry = self.cache[key]
            
            if entry.is_expired():
                # 缓存已过期,删除
                del self.cache[key]
                self.stats["misses"] += 1
                logger.debug(f"缓存已过期: {key}")
                return None
            
            # 缓存命中
            self.stats["hits"] += 1
            logger.debug(f"缓存命中: {key}")
            return entry.access()
        
        # 缓存未命中
        self.stats["misses"] += 1
        logger.debug(f"缓存未命中: {key}")
        return None
    
    def set(self, func_name: str, args: tuple, kwargs: dict, data: Any, ttl: Optional[int] = None):
        """
        设置缓存
        
        Args:
            func_name: 函数名
            args: 位置参数
            kwargs: 关键字参数
            data: 要缓存的数据
            ttl: 生存时间(秒),None表示使用默认TTL
        """
        key = self._generate_key(func_name, args, kwargs)
        ttl = ttl if ttl is not None else self.default_ttl
        
        self.cache[key] = CacheEntry(data, ttl)
        logger.debug(f"设置缓存: {key}, TTL: {ttl}s")
    
    def delete(self, func_name: str, args: tuple, kwargs: dict):
        """
        删除缓存
        
        Args:
            func_name: 函数名
            args: 位置参数
            kwargs: 关键字参数
        """
        key = self._generate_key(func_name, args, kwargs)
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"删除缓存: {key}")
    
    def clear(self):
        """清空所有缓存"""
        self.cache.clear()
        logger.info("清空所有缓存")
    
    def cleanup_expired(self) -> int:
        """
        清理过期的缓存
        
        Returns:
            int: 清理的缓存条目数
        """
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self.cache[key]
            self.stats["evictions"] += 1
        
        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存")
        
        return len(expired_keys)
    
    def _load_cache(self):
        """从文件加载缓存"""
        if not self.cache_file.exists():
            logger.debug("缓存文件不存在,创建新缓存")
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 反序列化缓存条目
            for key, entry_dict in cache_data.items():
                try:
                    self.cache[key] = CacheEntry.from_dict(entry_dict)
                except Exception as e:
                    logger.error(f"加载缓存条目失败: {key}, 错误: {e}")
                    self.stats["errors"] += 1
            
            logger.info(f"从文件加载了 {len(self.cache)} 个缓存条目")
        
        except Exception as e:
            logger.error(f"加载缓存文件失败: {e}")
            self.stats["errors"] += 1
    
    def _save_cache(self):
        """保存缓存到文件"""
        try:
            # 序列化缓存条目
            cache_data = {
                key: entry.to_dict()
                for key, entry in self.cache.items()
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"保存了 {len(self.cache)} 个缓存条目到文件")
        
        except Exception as e:
            logger.error(f"保存缓存文件失败: {e}")
            self.stats["errors"] += 1
            raise CacheError(f"保存缓存文件失败: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            Dict[str, Any]: 包含统计信息的字典
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0.0
        
        return {
            **self.stats,
            "total_entries": len(self.cache),
            "hit_rate": f"{hit_rate:.2%}",
            "cache_file": str(self.cache_file)
        }
    
    def cleanup_old_entries(self, days: int = 7) -> int:
        """
        清理指定天数之前的缓存条目
        
        Args:
            days: 天数,超过此天数的条目将被删除
            
        Returns:
            int: 清理的缓存条目数
        """
        cutoff_time = datetime.now() - timedelta(days=days)
        old_keys = [
            key for key, entry in self.cache.items()
            if entry.created_at < cutoff_time
        ]
        
        for key in old_keys:
            del self.cache[key]
            self.stats["evictions"] += 1
        
        if old_keys:
            logger.info(f"清理了 {len(old_keys)} 个超过 {days} 天的缓存")
        
        return len(old_keys)
    
    def __enter__(self):
        """支持上下文管理器"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时自动保存缓存"""
        self._save_cache()


# 全局缓存管理器实例
_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager(cache_file: Optional[str] = None, default_ttl: int = 3600) -> CacheManager:
    """
    获取全局缓存管理器实例
    
    Args:
        cache_file: 缓存文件路径
        default_ttl: 默认TTL
        
    Returns:
        CacheManager: 缓存管理器实例
    """
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager(cache_file, default_ttl)
    return _global_cache_manager


def cached(ttl: Optional[int] = None, cache_manager: Optional[CacheManager] = None):
    """
    缓存装饰器
    
    用于装饰函数,自动缓存函数的返回值。
    
    Args:
        ttl: 缓存生存时间(秒),None表示使用默认TTL
        cache_manager: 缓存管理器实例,None表示使用全局实例
        
    Returns:
        Callable: 装饰器函数
        
    Example:
        >>> @cached(ttl=3600)
        >>> def expensive_function(x, y):
        ...     return x + y
    """
    if cache_manager is None:
        cache_manager = get_cache_manager()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 尝试从缓存获取
            cached_data = cache_manager.get(func.__name__, args, kwargs)
            
            if cached_data is not None:
                return cached_data
            
            # 缓存未命中,执行函数
            result = func(*args, **kwargs)
            
            # 保存到缓存
            cache_manager.set(func.__name__, args, kwargs, result, ttl)
            
            return result
        
        return wrapper
    return decorator