"""
循环调度器 (Loop Agent 主循环)

开盘 (09:30) 到收盘 (15:00) 期间按固定间隔轮询全市场实时行情:
    tick 流程:
        1. 拉取全市场快照 (东方财富实时行情, 不落缓存)
        2. 与上一快照做差值检测 + 单快照规则检测
        3. 指数异动检测
        4. 冷却去重 -> 取强度最高的 Top-N
        5. 对每个异动执行 LLM/规则分析判断
        6. 控制台输出 + JSONL 落盘

时段管理:
    - 盘前: 等到 09:30
    - 午间: 等到 13:00
    - 收盘后: 输出当日总结并退出
    - 非工作日: 等到下一工作日 09:30
"""
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from monitor import session
from monitor.analyzer import analyze_anomaly
from monitor.detector import build_snapshot, detect_anomalies, detect_index_anomalies
from tools.http_timeout import install_default_timeout

# akshare 全市场快照回退路径需要全局超时防护, 避免上游不可达时挂死循环
install_default_timeout()

# 事件落盘目录
DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent / "logs" / "monitor"

# 轮询间隔 / 每 tick 最多分析数 / 同信号冷却秒数
DEFAULT_INTERVAL = 30
DEFAULT_TOP_N = 5
DEFAULT_COOLDOWN = 300


class MonitorLoop:
    """盘中异动监控循环。"""

    def __init__(self, interval: int = DEFAULT_INTERVAL, top_n: int = DEFAULT_TOP_N,
                 cooldown: int = DEFAULT_COOLDOWN, detector_config: Optional[Dict[str, float]] = None,
                 llm_config: Optional[Dict[str, Any]] = None,
                 log_dir: Path = DEFAULT_LOG_DIR, once: bool = False,
                 data_source: str = "sina"):
        self.interval = max(5, int(interval))
        self.top_n = max(1, int(top_n))
        self.cooldown = max(10, int(cooldown))
        self.detector_config = detector_config or {}
        self.llm_config = llm_config or {}
        self.log_dir = Path(log_dir)
        self.once = once
        self.data_source = data_source

        self.prev_snapshot: Optional[Dict[str, Dict[str, Any]]] = None
        self._cooldown_map: Dict[tuple, float] = {}
        self._today_events: List[Dict[str, Any]] = []
        self._current_date: Optional[str] = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------
    def run(self) -> None:
        """从当前时刻开始循环监控，直到收盘或 Ctrl+C。"""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._print_banner()
        try:
            if self.once:
                # 单次扫描: 不等待交易时段，直接拉取最新行情扫描一轮
                self._tick()
            else:
                while not self._stop.is_set():
                    now = datetime.now()
                    in_watch, next_t, desc = session.next_session_info(now)

                    self._check_day_rollover(now)

                    if not in_watch:
                        self._wait_until(next_t, f"{desc}, 等待 {next_t:%H:%M}")
                        continue
                    if desc != "trading":
                        self._wait_until(next_t, desc)
                        continue

                    self._tick()
                    self._interruptible_sleep(self.interval)
        except KeyboardInterrupt:
            print("\n👋 收到中断信号，正在退出...")
        finally:
            self._print_daily_summary()

    def stop(self) -> None:
        """供外部线程调用的安全停止。"""
        self._stop.set()

    # ------------------------------------------------------------------
    # tick 流程
    # ------------------------------------------------------------------
    def _tick(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        snapshot = self._fetch_snapshot()
        if not snapshot:
            print(f"[{now}] ⚠️ 快照为空（数据源异常），跳过本轮")
            return

        anomalies = detect_anomalies(snapshot, self.prev_snapshot, self.detector_config)
        indices = self._fetch_indices()
        anomalies.extend(detect_index_anomalies(indices, self.detector_config))

        if anomalies:
            print(f"[{now}] 检测到 {len(anomalies)} 条异动候选")
        # 冷却去重 + 每只股票只保留最强信号 + 按强度取 Top-N
        fresh = [a for a in anomalies if self._not_in_cooldown(a)]
        fresh.sort(key=lambda a: (a.get("score", 0), abs(a.get("pct", 0))), reverse=True)
        by_code: Dict[str, Dict[str, Any]] = {}
        for a in fresh:
            by_code.setdefault(a.get("code"), a)  # 已按强度降序，首个即最强
        picked = list(by_code.values())[: self.top_n]

        for anomaly in picked:
            self._analyze_and_report(anomaly, now)

        self.prev_snapshot = snapshot

    def _analyze_and_report(self, anomaly: Dict[str, Any], tick_time: str) -> None:
        key = (anomaly.get("code"), anomaly.get("signal"))
        result = analyze_anomaly(anomaly, self.llm_config)
        self._cooldown_map[key] = time.time()

        event = {
            "time": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
            "tick": tick_time,
            "anomaly": anomaly,
            "judgment": result,
        }
        self._today_events.append(event)
        self._append_jsonl(event)
        self._print_event(event)

    # ------------------------------------------------------------------
    # 数据获取
    # ------------------------------------------------------------------
    def _fetch_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """拉取异动候选快照 (榜单 Top100 并集, 单轮 2-6 秒)。

        指定数据源失败时自动回退另一通道 (sina <-> eastmoney)；
        全部失败时回退 akshare 全市场快照 (慢, 但数据完整)。
        """
        from monitor.fetcher import fetch_movers_snapshot

        try:
            snapshot = fetch_movers_snapshot(self.data_source)
            if snapshot:
                return snapshot
        except Exception as e:
            print(f"⚠️ 榜单抓取失败 ({e})，回退 akshare 全市场抓取")

        import akshare as ak
        from tools.retry import retry

        @retry(max_retries=2, delay=1.5, backoff=2)
        def _fetch():
            df = ak.stock_zh_a_spot_em()
            return build_snapshot(df)

        try:
            return _fetch()
        except Exception as e:
            print(f"⚠️ 拉取全市场行情失败: {e}")
            return {}

    def _fetch_indices(self) -> List[Dict[str, Any]]:
        """指数行情 (复用 tools 层，60s 缓存可接受)。"""
        try:
            from tools.stock_data import get_market_indices
            return get_market_indices()
        except Exception as e:
            print(f"⚠️ 拉取指数行情失败: {e}")
            return []

    # ------------------------------------------------------------------
    # 冷却 / 等待 / 输出
    # ------------------------------------------------------------------
    def _check_day_rollover(self, now: datetime) -> None:
        """跨交易日时清空上一日的快照/冷却/事件，避免跨日污染。"""
        date_str = now.strftime("%Y-%m-%d")
        if self._current_date is None:
            self._current_date = date_str
        elif date_str != self._current_date:
            print(f"\n📅 已进入新交易日 {date_str}，重置监控状态")
            self._current_date = date_str
            self.prev_snapshot = None
            self._cooldown_map.clear()
            self._today_events.clear()

    def _not_in_cooldown(self, anomaly: Dict[str, Any]) -> bool:
        key = (anomaly.get("code"), anomaly.get("signal"))
        last = self._cooldown_map.get(key, 0.0)
        return time.time() - last >= self.cooldown

    def _wait_until(self, target: Optional[datetime], desc: str) -> None:
        if target is None:
            return
        wait_secs = (target - datetime.now()).total_seconds()
        if wait_secs <= 0:
            return
        print(f"⏳ {desc} ({wait_secs / 60:.0f} 分钟后开始)...")
        self._interruptible_sleep(min(wait_secs, 60.0))

    def _interruptible_sleep(self, seconds: float) -> None:
        """分段睡眠，保证 KeyboardInterrupt 与 stop() 及时生效。"""
        end = time.time() + seconds
        while time.time() < end and not self._stop.is_set():
            time.sleep(min(1.0, end - time.time()))

    def _append_jsonl(self, event: Dict[str, Any]) -> None:
        path = self.log_dir / f"{datetime.now():%Y-%m-%d}.jsonl"
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError as e:
            print(f"⚠️ 事件落盘失败: {e}")

    def _print_banner(self) -> None:
        mode = "单次扫描(--once)" if self.once else "循环监控"
        print("=" * 64)
        print(f"📡 盘中异动监控 Loop Agent  {mode}")
        print(f"   轮询间隔: {self.interval}s   每轮最多分析: {self.top_n} 个   "
              f"冷却时间: {self.cooldown}s")
        print(f"   监控时段: {session.WATCH_START:%H:%M} - {session.WATCH_END:%H:%M} (工作日)")
        print(f"   事件落盘: {self.log_dir}")
        print("=" * 64)

    def _print_event(self, event: Dict[str, Any]) -> None:
        a = event["anomaly"]
        j = event["judgment"]
        score = a.get("score", 0)
        price = a.get("price", 0) or 0
        pct = a.get("pct", 0) or 0
        amount = (a.get("amount") or 0) / 1e8
        vr = a.get("volume_ratio", 0) or 0
        turnover = a.get("turnover", 0) or 0
        print("-" * 64)
        print(f"⚡ [{event['tick']}] {a.get('name', a.get('code', ''))}({a.get('code', '')}) "
              f"{a.get('signal_label', '异动')} 强度{score:.0f}")
        detail = f"最新价 {price:.2f}  涨跌幅 {pct:+.2f}%"
        if vr > 0:
            detail += f"  量比 {vr:.1f}"
        if turnover > 0:
            detail += f"  换手 {turnover:.1f}%"
        detail += f"  成交额 {amount:.1f}亿"
        print(f"   {detail}")
        mode = "LLM" if j.get("sources", {}).get("mode") == "llm" else "规则"
        print(f"   🔎 [{mode}判断] {j.get('judgment', '')}")
        reasons = j.get("reasons") or {}
        if isinstance(reasons, dict):
            for k, v in reasons.items():
                if v:
                    print(f"      · {k}: {v}")
        print(f"   🚦 风险等级: {j.get('risk_level', '未知')}  |  "
              f"关注: {' / '.join(j.get('watch_points', []) or [])}")

    def _print_daily_summary(self) -> None:
        if not self._today_events:
            print("\n📋 今日无已分析的异动事件")
            return
        total = len(self._today_events)
        by_signal: Dict[str, int] = {}
        risk_high = 0
        for e in self._today_events:
            sig = e["anomaly"].get("signal_label", "其他")
            by_signal[sig] = by_signal.get(sig, 0) + 1
            if e["judgment"].get("risk_level") == "高":
                risk_high += 1

        lines = [
            "=" * 64,
            f"📋 当日异动监控总结  ({datetime.now():%Y-%m-%d})",
            f"   共分析异动事件 {total} 个，其中高风险 {risk_high} 个",
            "   按类型统计: " + "  ".join(f"{k}×{v}" for k, v in sorted(by_signal.items())),
            "=" * 64,
        ]
        for e in self._today_events:
            a, j = e["anomaly"], e["judgment"]
            lines.append(
                f"  [{e['time'][11:19]}] {a.get('name', '')}({a.get('code', '')}) "
                f"{a.get('signal_label', '')} 风险:{j.get('risk_level', '-')}  "
                f"{j.get('judgment', '')[:50]}"
            )
        lines.append("=" * 64)
        summary = "\n".join(lines)
        print(summary)

        try:
            path = self.log_dir / f"{datetime.now():%Y-%m-%d}-summary.md"
            with open(path, "w", encoding="utf-8") as f:
                f.write(summary + "\n")
            print(f"📄 总结已保存: {path}")
        except OSError as e:
            print(f"⚠️ 总结保存失败: {e}")


def run_loop(interval: int = DEFAULT_INTERVAL, top_n: int = DEFAULT_TOP_N,
             cooldown: int = DEFAULT_COOLDOWN, once: bool = False,
             detector_config: Optional[Dict[str, float]] = None,
             llm_config: Optional[Dict[str, Any]] = None,
             data_source: str = "sina") -> None:
    """便捷入口: 构造配置并启动监控循环。

    llm_config 不传时自动从系统配置管理器读取 (api_key/model_name/...)。
    data_source: "sina" (默认) 或 "eastmoney" (提供量比/涨速字段)。
    """
    if llm_config is None:
        from config import get_config_manager
        cm = get_config_manager()
        llm_config = {
            "api_key": cm.get("api_key", ""),
            "api_base": cm.get("api_base", "https://api.openai.com/v1"),
            "model_name": cm.get("model_name", "gpt-3.5-turbo"),
            "temperature": cm.get("llm.temperature", 0.3),
            "max_tokens": cm.get("llm.max_tokens", 2048),
            "thinking_mode": cm.get("llm.thinking_mode", False),
        }
    MonitorLoop(interval=interval, top_n=top_n, cooldown=cooldown,
                detector_config=detector_config, llm_config=llm_config,
                once=once, data_source=data_source).run()
