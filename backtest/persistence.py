import json
import os
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

class BacktestPersistence:
    """
    Persistence layer: Store backtest results for reproducibility.
    Stores parameters, data version, metrics, and timestamps.
    """
    def __init__(self, storage_dir: str = ".backtest_results"):
        self.storage_dir = storage_dir
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)

    def save_result(self, strategy_name: str, params: Dict[str, Any], metrics: Dict[str, Any], 
                    data_info: Dict[str, Any]) -> str:
        """
        Save backtest result to a JSON file.
        Returns the path to the saved file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create a unique ID for this backtest run
        id_str = f"{strategy_name}_{json.dumps(params, sort_keys=True)}_{json.dumps(data_info, sort_keys=True)}"
        run_id = hashlib.md5(id_str.encode()).hexdigest()[:8]
        
        filename = f"{strategy_name}_{timestamp}_{run_id}.json"
        filepath = os.path.join(self.storage_dir, filename)
        
        record = {
            "run_id": run_id,
            "timestamp": timestamp,
            "strategy": strategy_name,
            "parameters": params,
            "data_info": data_info,
            "metrics": metrics
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, indent=4, ensure_ascii=False)
            
        return filepath

    def list_results(self, strategy_name: Optional[str] = None) -> list:
        """List all saved backtest results"""
        results = []
        for filename in os.listdir(self.storage_dir):
            if filename.endswith(".json"):
                if strategy_name and not filename.startswith(strategy_name):
                    continue
                with open(os.path.join(self.storage_dir, filename), 'r', encoding='utf-8') as f:
                    results.append(json.load(f))
        return sorted(results, key=lambda x: x["timestamp"], reverse=True)
