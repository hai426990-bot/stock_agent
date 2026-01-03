import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, date
import hashlib
import json
import os
import threading
from .logger import logger

_global_cache_lock = threading.RLock()
_global_memory_caches: Dict[str, Dict[str, Dict[str, Any]]] = {}

def _json_default(obj: Any):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    to_pydatetime = getattr(obj, "to_pydatetime", None)
    if callable(to_pydatetime):
        try:
            return to_pydatetime().isoformat()
        except Exception:
            pass
    return str(obj)

class DataCache:
    def __init__(self, cache_dir: str = 'cache', default_ttl: int = 300):
        self.cache_dir = cache_dir
        self.default_ttl = default_ttl
        with _global_cache_lock:
            self.memory_cache = _global_memory_caches.setdefault(cache_dir, {})
        # 智能TTL设置，根据数据类型设置不同的生存时间
        self.smart_ttl = {
            'stock_info': 60,  # 股票基本信息：60秒
            'kline_data': 300,  # K线数据：300秒
            'financial_data': 3600,  # 财务数据：3600秒
            'fund_flow': 1800,  # 资金流向数据：1800秒
            'market_sentiment': 1800,  # 市场情绪数据：1800秒
            'technical_indicators': 300,  # 技术指标：300秒
            'fundamental_analysis': 3600,  # 基本面分析：3600秒
            'risk_analysis': 3600,  # 风险分析：3600秒
            'sentiment_analysis': 1800,  # 情绪分析：1800秒
            'investment_strategy': 3600  # 投资策略：3600秒
        }
        # 缓存命中率统计
        self.hit_count = 0
        self.miss_count = 0
        # 缓存使用统计
        self.set_count = 0
        self.clear_count = 0
        
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    def _generate_key(self, prefix: str, params: Dict[str, Any]) -> str:
        params_str = json.dumps(params, sort_keys=True, default=str)
        hash_obj = hashlib.md5(params_str.encode())
        return f"{prefix}_{hash_obj.hexdigest()}"
    
    def _get_cache_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def _is_expired(self, cache_data: Dict[str, Any]) -> bool:
        if 'timestamp' not in cache_data:
            return True
        
        cache_time = datetime.fromisoformat(cache_data['timestamp'])
        ttl = cache_data.get('ttl', self.default_ttl)
        
        return datetime.now() > cache_time + timedelta(seconds=ttl)
    
    def get(self, prefix: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = self._generate_key(prefix, params)
        with _global_cache_lock:
            if key in self.memory_cache:
                cache_data = self.memory_cache[key]
                if not self._is_expired(cache_data):
                    self.hit_count += 1
                    return cache_data.get('data')
                else:
                    del self.memory_cache[key]
        
        cache_path = self._get_cache_path(key)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
            
                if not self._is_expired(cache_data):
                    with _global_cache_lock:
                        self.memory_cache[key] = cache_data
                    self.hit_count += 1  # 更新命中次数统计
                    return cache_data.get('data')
                else:
                    os.remove(cache_path)
            except Exception as e:
                logger.warning(f"读取缓存文件失败: {e}")
                try:
                    os.remove(cache_path)
                except Exception:
                    pass
        
        self.miss_count += 1  # 更新未命中次数统计
        return None
    
    def set(self, prefix: str, params: Dict[str, Any], data: Any, ttl: Optional[int] = None):
        key = self._generate_key(prefix, params)
        
        # 智能TTL选择：如果没有指定TTL，则根据前缀从smart_ttl中获取
        if ttl is None:
            ttl = self.smart_ttl.get(prefix, self.default_ttl)
        
        cache_data = {
            'data': data,
            'timestamp': datetime.now().isoformat(),
            'ttl': ttl
        }
        with _global_cache_lock:
            self.memory_cache[key] = cache_data
        self.set_count += 1  # 更新设置次数统计
        
        try:
            cache_path = self._get_cache_path(key)
            tmp_path = f"{cache_path}.tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=_json_default)
            os.replace(tmp_path, cache_path)
        except Exception as e:
            logger.warning(f"写入缓存文件失败: {e}")
            try:
                cache_path = self._get_cache_path(key)
                tmp_path = f"{cache_path}.tmp"
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    
    def clear(self, prefix: Optional[str] = None):
        self.clear_count += 1  # 更新清理次数统计
        
        if prefix:
            with _global_cache_lock:
                keys_to_remove = [k for k in list(self.memory_cache.keys()) if k.startswith(prefix)]
                for key in keys_to_remove:
                    del self.memory_cache[key]
            
            for key in keys_to_remove:
                cache_path = self._get_cache_path(key)
                if os.path.exists(cache_path):
                    try:
                        os.remove(cache_path)
                    except Exception as e:
                        logger.warning(f"删除缓存文件失败: {e}")
        else:
            with _global_cache_lock:
                self.memory_cache.clear()
            
            if os.path.exists(self.cache_dir):
                try:
                    for filename in os.listdir(self.cache_dir):
                        file_path = os.path.join(self.cache_dir, filename)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                except Exception as e:
                    logger.warning(f"清空缓存目录失败: {e}")
    
    def cleanup_expired(self):
        keys_to_remove = []
        with _global_cache_lock:
            for key, cache_data in list(self.memory_cache.items()):
                if self._is_expired(cache_data):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.memory_cache[key]
        
        if os.path.exists(self.cache_dir):
            try:
                for filename in os.listdir(self.cache_dir):
                    file_path = os.path.join(self.cache_dir, filename)
                    if os.path.isfile(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            
                            if self._is_expired(cache_data):
                                os.remove(file_path)
                        except Exception:
                            pass
            except Exception:
                pass
    
    def get_stats(self) -> Dict[str, Any]:
        with _global_cache_lock:
            memory_count = len(self.memory_cache)
        disk_count = 0
        
        if os.path.exists(self.cache_dir):
            try:
                disk_count = len([f for f in os.listdir(self.cache_dir) if f.endswith('.json')])
            except Exception as e:
                logger.warning(f"统计缓存文件数量失败: {e}")
        
        # 计算命中率
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'memory_cache_count': memory_count,
            'disk_cache_count': disk_count,
            'cache_dir': self.cache_dir,
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'total_requests': total_requests,
            'hit_rate': round(hit_rate, 2),
            'set_count': self.set_count,
            'clear_count': self.clear_count,
            'smart_ttl_config': self.smart_ttl
        }
