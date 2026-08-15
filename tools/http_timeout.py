"""全局 HTTP 超时防护 (Global HTTP timeout guard).

背景
----
akshare 内部大量通过 requests / curl_cffi 直接请求上游数据源
(东方财富 / 新浪 / 同花顺)，且多数调用不传 timeout —— 标准 requests
默认 timeout=None 表示无限期等待，上游变慢或不可达时整个调用链
(以及持有它的线程) 会一直挂死。这是本项目 "akshare 总是超时"
(实为无限期挂起) 的根因之一。

方案
----
在本模块被导入的进程内，给以下两个统一入口注入默认超时:

    - requests.sessions.Session.request   (requests.get/post 等都经由它)
    - curl_cffi.requests.Session.request  (curl_cffi 模块级 get/post 经由它)

仅当调用方未显式传入 timeout (即 kwargs 中 timeout 为 None) 时才注入，
显式 timeout (如 akshare 内部个别接口的 timeout=15) 保持不变。

配置
----
环境变量 AKSHARE_HTTP_TIMEOUT 可覆盖默认值，格式:

    "15"    -> 连接 + 读取共用 15 秒
    "5,15"  -> 连接 5 秒 / 读取 15 秒

默认 (5, 15) 秒。install_default_timeout() 幂等，可安全地在多个
入口模块重复调用 (tools/stock_data.py、backtest/data.py、monitor/loop.py)。
"""

import os
import sys
import threading
from typing import Optional, Tuple, Union

from curl_cffi.requests import Session as CurlCffiSession
from requests.sessions import Session as RequestsSession

# 默认: 连接 5s / 读取 15s
DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 15.0)

_lock = threading.Lock()
_state = {
    "installed": False,
    "timeout": DEFAULT_TIMEOUT,
    "originals": {},
}


_env_file_loaded = False


def _load_env_file_once() -> None:
    """尽力从项目 .env 加载配置 (不覆盖已存在的环境变量)。

    main.py 在导入 tools.stock_data 之后才实例化 ConfigManager 并加载
    .env, 因此这里需要自行尝试加载一次, 保证 .env 里的
    AKSHARE_HTTP_TIMEOUT 也能生效。
    """
    global _env_file_loaded
    if _env_file_loaded:
        return
    _env_file_loaded = True
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass


def _parse_env_timeout() -> Optional[Tuple[float, float]]:
    """解析 AKSHARE_HTTP_TIMEOUT 环境变量, 非法时返回 None。"""
    _load_env_file_once()
    raw = (os.environ.get("AKSHARE_HTTP_TIMEOUT") or "").strip()
    if not raw:
        return None
    try:
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) == 1:
            t = float(parts[0])
            return (t, t)
        if len(parts) == 2:
            return (float(parts[0]), float(parts[1]))
    except ValueError:
        pass
    print(f"⚠️ 无法解析 AKSHARE_HTTP_TIMEOUT={raw!r}, 使用默认 {DEFAULT_TIMEOUT}")
    return None


def get_default_timeout() -> Tuple[float, float]:
    """当前默认超时 (连接秒, 读取秒)。"""
    return _state["timeout"]


def set_default_timeout(timeout: Union[float, Tuple[float, float]]) -> None:
    """运行时修改默认超时; 已在途的请求不受影响。"""
    if isinstance(timeout, (int, float)):
        timeout = (float(timeout), float(timeout))
    with _lock:
        _state["timeout"] = timeout


def _ensure_utf8_stdout() -> None:
    """Windows 控制台默认 GBK 编码无法输出 emoji, 统一切到 UTF-8。

    仅调整当前进程的标准输出编码, 失败时静默忽略 (打印会走替换模式)。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _make_patch(original):
    def patched(self, method, url, **kwargs):
        # 仅当调用方未显式传 timeout (None 或缺失) 时注入默认值;
        # 显式的 timeout=0 在 requests 语义下同样表示不设限, 但
        # akshare 不会传 0, 为稳妥起见仅替换 None。
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = _state["timeout"]
        return original(self, method, url, **kwargs)

    return patched


def install_default_timeout(verbose: bool = True) -> bool:
    """幂等安装全局默认超时; 返回 True 表示本次执行了安装。

    需要在所有会发起 akshare 请求的入口模块调用 (模块导入时即可):
        - tools/stock_data.py
        - backtest/data.py
        - monitor/loop.py
    """
    with _lock:
        if _state["installed"]:
            return False
        _ensure_utf8_stdout()
        env_t = _parse_env_timeout()
        if env_t is not None:
            _state["timeout"] = env_t
        for cls in (RequestsSession, CurlCffiSession):
            _state["originals"][cls] = cls.request
            cls.request = _make_patch(cls.request)
        _state["installed"] = True
        installed_timeout = _state["timeout"]
    if verbose:
        print(
            f"⏱️ 已安装全局 HTTP 超时防护: "
            f"连接 {installed_timeout[0]}s / 读取 {installed_timeout[1]}s "
            f"(仅对未显式传 timeout 的请求生效)"
        )
    return True


def uninstall_default_timeout() -> None:
    """测试用: 还原被 patch 的方法, 并允许重新安装。"""
    with _lock:
        for cls, original in _state["originals"].items():
            cls.request = original
        _state["originals"].clear()
        _state["installed"] = False
