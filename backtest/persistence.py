import json
import os
import hashlib
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List

class BacktestPersistence:
    """
    Persistence layer: Store backtest results in JSON files and index them in SQLite.
    Stores parameters, data version, metrics, and timestamps.
    """
    def __init__(self, storage_dir: str = ".backtest_results"):
        self.storage_dir = storage_dir
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
        
        self.db_path = os.path.join(storage_dir, "backtest_history.db")
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for indexing"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtests (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT,
                strategy_name TEXT,
                stock_code TEXT,
                sharpe REAL,
                cagr REAL,
                max_drawdown REAL,
                win_rate REAL,
                filepath TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_result(self, strategy_name: str, params: Dict[str, Any], metrics: Dict[str, Any], 
                    data_info: Dict[str, Any], engine_info: Optional[Dict[str, Any]] = None) -> str:
        """
        Save backtest result to a JSON file and index it in SQLite.
        Returns the path to the saved file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stock_code = data_info.get("symbol", "UNKNOWN")
        
        # Create a unique ID for this backtest run
        engine_info = engine_info or {}
        id_str = (
            f"{strategy_name}_"
            f"{stock_code}_"
            f"{json.dumps(params, sort_keys=True, ensure_ascii=False)}_"
            f"{json.dumps(data_info, sort_keys=True, ensure_ascii=False)}_"
            f"{json.dumps(engine_info, sort_keys=True, ensure_ascii=False)}"
        )
        run_id = hashlib.sha256(id_str.encode("utf-8")).hexdigest()[:12]
        
        filename = f"{strategy_name}_{stock_code}_{timestamp}_{run_id}.json"
        filepath = os.path.join(self.storage_dir, filename)
        
        record = {
            "run_id": run_id,
            "timestamp": timestamp,
            "strategy": strategy_name,
            "parameters": params,
            "engine": engine_info,
            "data_info": data_info,
            "metrics": metrics
        }
        
        # Save JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, indent=4, ensure_ascii=False)
            
        # Index in SQLite
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO backtests 
                (run_id, timestamp, strategy_name, stock_code, sharpe, cagr, max_drawdown, win_rate, filepath)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, 
                record["timestamp"], 
                strategy_name, 
                stock_code,
                metrics.get("sharpe", 0),
                metrics.get("cagr", 0),
                metrics.get("max_drawdown", 0),
                metrics.get("win_rate", 0),
                filepath
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to index backtest in SQLite: {e}")
            
        return filepath

    def list_results(self, strategy_name: Optional[str] = None, stock_code: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List saved backtest results from SQLite"""
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT filepath FROM backtests WHERE 1=1"
            params = []
            if strategy_name:
                query += " AND strategy_name = ?"
                params.append(strategy_name)
            if stock_code:
                query += " AND stock_code = ?"
                params.append(stock_code)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                fpath = row[0]
                if os.path.exists(fpath):
                    with open(fpath, 'r', encoding='utf-8') as f:
                        results.append(json.load(f))
        except Exception as e:
            print(f"Failed to query backtests from SQLite: {e}")
            # Fallback to file scanning if DB fails
            for filename in os.listdir(self.storage_dir):
                if filename.endswith(".json") and filename != "backtest_history.db":
                    with open(os.path.join(self.storage_dir, filename), 'r', encoding='utf-8') as f:
                        results.append(json.load(f))
        
        return sorted(results, key=lambda x: x["timestamp"], reverse=True)