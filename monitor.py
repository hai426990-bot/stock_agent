"""
AlphaFlow 盘中异动监控 Loop Agent (CLI 入口)

开盘到收盘期间循环监控全市场行情，对盘中异动（急涨急跌、放量、
封板/炸板、指数急变等）及时做 LLM 分析判断。

使用方式:
    python monitor.py                        # 循环监控 (默认每 30s 一轮)
    python monitor.py --interval 60          # 每 60s 轮询一次
    python monitor.py --top 10               # 每轮最多分析 10 个异动
    python monitor.py --cooldown 600         # 同一信号 10 分钟内不重复分析
    python monitor.py --surge 5 --plunge -5  # 收紧急涨急跌阈值
    python monitor.py --once                 # 单次扫描 (测试/复盘用)

依赖:
    - AkShare: 全市场实时行情
    - LLM: 异动分析判断 (未配置 API Key 时降级为规则判断)
"""
import argparse
import sys

from logger import get_logger
from monitor.loop import run_loop, DEFAULT_INTERVAL, DEFAULT_TOP_N, DEFAULT_COOLDOWN

logger = get_logger(__name__)


def main() -> None:
    # 行缓冲: 循环监控长时间运行，实时输出不能被管道缓冲吞掉
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(
        description="AlphaFlow 盘中异动监控 Loop Agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help="轮询间隔（秒），最短 5 秒")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N,
                        help="每轮最多分析的异动数量")
    parser.add_argument("--cooldown", type=int, default=DEFAULT_COOLDOWN,
                        help="同一股票同一信号的分析冷却时间（秒）")
    parser.add_argument("--once", action="store_true",
                        help="单次扫描后退出（不等待交易时段）")
    parser.add_argument("--surge", type=float, default=None,
                        help="急涨触发阈值（涨跌幅 %）")
    parser.add_argument("--plunge", type=float, default=None,
                        help="急跌触发阈值（涨跌幅 %，传负数）")
    parser.add_argument("--volume-ratio", type=float, default=None,
                        help="放量异动量比阈值")
    parser.add_argument("--amplitude", type=float, default=None,
                        help="振幅异动阈值（%）")
    parser.add_argument("--data-source", choices=("sina", "eastmoney"), default="sina",
                        help="榜单数据源: sina(默认, 稳定) / eastmoney(含量比涨速字段)")

    args = parser.parse_args()

    detector_config = {}
    if args.surge is not None:
        detector_config["surge_pct"] = args.surge
    if args.plunge is not None:
        detector_config["plunge_pct"] = args.plunge
    if args.volume_ratio is not None:
        detector_config["volume_ratio"] = args.volume_ratio
    if args.amplitude is not None:
        detector_config["amplitude_pct"] = args.amplitude

    run_loop(interval=args.interval, top_n=args.top, cooldown=args.cooldown,
             once=args.once, detector_config=detector_config,
             data_source=args.data_source)


if __name__ == "__main__":
    main()
