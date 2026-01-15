import os
import json
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv


class ConfigManager:
    """
    配置管理器，实现系统默认配置的优先调用机制
    
    配置加载优先级（从高到低）:
    1. 运行时传入的参数（最高优先级）
    2. 用户自定义配置文件 (config_user.json)
    3. 环境变量
    4. 系统默认配置文件 (config_default.json)
    
    系统默认配置作为基础配置被优先调用和应用，
    用户配置在系统默认配置的基础上进行覆盖或扩展。
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        初始化配置管理器
        
        Args:
            project_root: 项目根目录路径，默认为当前文件所在目录的父目录
        """
        if project_root is None:
            self.project_root = Path(__file__).parent
        else:
            self.project_root = Path(project_root)
        
        self.default_config_file = self.project_root / "config_default.json"
        self.user_config_file = self.project_root / "config_user.json"
        self.env_file = self.project_root / ".env"
        
        self._default_config: Dict[str, Any] = {}
        self._user_config: Dict[str, Any] = {}
        self._env_config: Dict[str, Any] = {}
        self._runtime_config: Dict[str, Any] = {}
        self._merged_config: Dict[str, Any] = {}
        
        self._load_all_configs()
    
    def _load_json_file(self, file_path: Path) -> Dict[str, Any]:
        """
        加载 JSON 配置文件
        
        Args:
            file_path: JSON 文件路径
            
        Returns:
            配置字典，如果文件不存在或解析失败返回空字典
        """
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ 加载配置文件失败 {file_path}: {e}")
            return {}
    
    def _load_env_vars(self) -> Dict[str, Any]:
        """
        加载环境变量配置
        
        Returns:
            环境变量配置字典
        """
        env_config = {}
        
        env_mappings = {
            "OPENAI_API_KEY": "api_key",
            "OPENAI_API_BASE": "api_base",
            "OPENAI_BASE_URL": "api_base",
            "OPENAI_MODEL_NAME": "model_name",
            "OPENAI_MODEL": "model_name",
            "MODEL_NAME": "model_name",
            "SUPPORTED_MODELS": "supported_models",
            "PYTHONUTF8": "python_utf8"
        }
        
        for env_key, config_key in env_mappings.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                env_config[config_key] = env_value
        
        return env_config
    
    def _load_all_configs(self):
        """
        按优先级加载所有配置
        
        加载顺序（从低到高）:
        1. 系统默认配置文件 (config_default.json)
        2. 环境变量
        3. 用户自定义配置文件 (config_user.json)
        4. 运行时配置（通过 set_runtime_config 设置）
        """
        self._default_config = self._load_json_file(self.default_config_file)
        
        load_dotenv(self.env_file, override=True)
        self._env_config = self._load_env_vars()
        
        self._user_config = self._load_json_file(self.user_config_file)
        
        self._merge_configs()
    
    def _merge_configs(self):
        """
        合并所有配置，应用优先级规则
        
        合并顺序:
        1. 从系统默认配置开始
        2. 环境变量覆盖默认配置
        3. 用户配置覆盖环境变量
        4. 运行时配置覆盖用户配置
        """
        self._merged_config = {}
        
        self._deep_update(self._merged_config, self._default_config)
        self._deep_update(self._merged_config, self._env_config)
        self._deep_update(self._merged_config, self._user_config)
        self._deep_update(self._merged_config, self._runtime_config)
    
    def _deep_update(self, base: Dict[str, Any], override: Dict[str, Any]):
        """
        深度更新字典
        
        Args:
            base: 基础字典
            override: 覆盖字典
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点号分隔的嵌套键（如 "llm.temperature"）
            default: 默认值，如果配置不存在则返回此值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._merged_config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set_runtime_config(self, config: Dict[str, Any]):
        """
        设置运行时配置（最高优先级）
        
        Args:
            config: 运行时配置字典
        """
        self._runtime_config = config
        self._merge_configs()
    
    def get_all(self) -> Dict[str, Any]:
        """
        获取所有合并后的配置
        
        Returns:
            合并后的配置字典
        """
        return self._merged_config.copy()
    
    def get_default_config(self) -> Dict[str, Any]:
        """
        获取系统默认配置
        
        Returns:
            系统默认配置字典
        """
        return self._default_config.copy()
    
    def get_user_config(self) -> Dict[str, Any]:
        """
        获取用户自定义配置
        
        Returns:
            用户配置字典
        """
        return self._user_config.copy()
    
    def get_env_config(self) -> Dict[str, Any]:
        """
        获取环境变量配置
        
        Returns:
            环境变量配置字典
        """
        return self._env_config.copy()
    
    def reload(self):
        """
        重新加载所有配置
        """
        self._load_all_configs()
    
    def save_user_config(self, config: Dict[str, Any]):
        """
        保存用户自定义配置到文件
        
        Args:
            config: 用户配置字典
        """
        try:
            with open(self.user_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self._user_config = config
            self._merge_configs()
            print(f"✅ 用户配置已保存到 {self.user_config_file}")
        except IOError as e:
            print(f"❌ 保存用户配置失败: {e}")
    
    def clear_user_config(self):
        """
        清除用户自定义配置文件
        """
        if self.user_config_file.exists():
            try:
                os.remove(self.user_config_file)
                self._user_config = {}
                self._merge_configs()
                print(f"✅ 用户配置文件已删除: {self.user_config_file}")
            except IOError as e:
                print(f"❌ 删除用户配置文件失败: {e}")
    
    def get_config_source(self, key: str) -> Optional[str]:
        """
        查询配置值的来源
        
        Args:
            key: 配置键
            
        Returns:
            配置来源: "runtime", "user", "env", "default", 或 None（不存在）
        """
        keys = key.split('.')
        
        def _has_key(config: Dict[str, Any], keys: list) -> bool:
            value = config
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return False
            return True
        
        if _has_key(self._runtime_config, keys):
            return "runtime"
        if _has_key(self._user_config, keys):
            return "user"
        if _has_key(self._env_config, keys):
            return "env"
        if _has_key(self._default_config, keys):
            return "default"
        return None
    
    def print_config_hierarchy(self):
        """
        打印配置层次结构和来源
        """
        print("=" * 60)
        print("配置层次结构")
        print("=" * 60)
        print(f"项目根目录: {self.project_root}")
        print(f"系统默认配置: {self.default_config_file} {'✅' if self.default_config_file.exists() else '❌'}")
        print(f"环境变量文件: {self.env_file} {'✅' if self.env_file.exists() else '❌'}")
        print(f"用户自定义配置: {self.user_config_file} {'✅' if self.user_config_file.exists() else '❌'}")
        print("=" * 60)
        print("配置优先级（从高到低）:")
        print("  1. 运行时配置 (set_runtime_config)")
        print("  2. 用户自定义配置 (config_user.json)")
        print("  3. 环境变量")
        print("  4. 系统默认配置 (config_default.json)")
        print("=" * 60)


_global_config_manager: Optional[ConfigManager] = None


def get_config_manager(project_root: Optional[Path] = None) -> ConfigManager:
    """
    获取全局配置管理器实例
    
    Args:
        project_root: 项目根目录路径
        
    Returns:
        配置管理器实例
    """
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager(project_root)
    return _global_config_manager


def get_config(key: str, default: Any = None) -> Any:
    """
    获取配置值的便捷函数
    
    Args:
        key: 配置键
        default: 默认值
        
    Returns:
        配置值
    """
    return get_config_manager().get(key, default)


def set_runtime_config(config: Dict[str, Any]):
    """
    设置运行时配置的便捷函数
    
    Args:
        config: 运行时配置字典
    """
    get_config_manager().set_runtime_config(config)
