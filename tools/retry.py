"""共享的重试装饰器（tools/stock_data.py 与 backtest/data.py 原各有一份相同实现）。"""
import time
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar("T")


def retry(max_retries: int = 3, delay: float = 1, backoff: float = 2):
    """指数退避重试装饰器，用于 AkShare 等网络接口请求。

    Args:
        max_retries: 最大重试次数
        delay: 首次重试前等待秒数
        backoff: 每次重试等待时间的倍率

    Raises:
        最后一次尝试的原始异常
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        raise e
                    time.sleep(current_delay)
                    current_delay *= backoff
            return None

        return wrapper

    return decorator
