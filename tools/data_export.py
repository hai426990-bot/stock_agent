"""
数据导出模块

提供数据导出功能,支持CSV和Excel格式。
"""

import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from logger import get_logger
from exceptions import ValidationError, DataFetchError

logger = get_logger(__name__)


class DataExporter:
    """
    数据导出器
    
    支持将数据导出为CSV、Excel等格式。
    """
    
    def __init__(self, export_dir: Optional[Path] = None):
        """
        初始化数据导出器
        
        Args:
            export_dir: 导出目录,默认为项目根目录下的exports文件夹
        """
        if export_dir is None:
            project_root = Path(__file__).parent.parent
            export_dir = project_root / "exports"
        
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"数据导出器初始化完成,导出目录: {self.export_dir}")
    
    def export_to_csv(
        self,
        data: Union[pd.DataFrame, Dict, List],
        filename: str,
        encoding: str = 'utf-8-sig',
        **kwargs
    ) -> Path:
        """
        导出数据到CSV文件
        
        Args:
            data: 要导出的数据,可以是DataFrame、字典或列表
            filename: 文件名(不带扩展名)
            encoding: 文件编码,默认为utf-8-sig(支持Excel打开)
            **kwargs: 传递给pandas.to_csv的额外参数
            
        Returns:
            导出文件的完整路径
            
        Raises:
            ValidationError: 当数据格式无效时
        """
        try:
            # 转换数据为DataFrame
            df = self._convert_to_dataframe(data)
            
            # 生成文件路径
            filepath = self.export_dir / f"{filename}.csv"
            
            # 导出数据
            df.to_csv(filepath, index=False, encoding=encoding, **kwargs)
            
            logger.info(f"数据已导出到CSV: {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"导出CSV失败: {e}")
            raise DataFetchError(f"导出CSV失败: {str(e)}", source="CSV Export")
    
    def export_to_excel(
        self,
        data: Union[pd.DataFrame, Dict, List, Dict[str, pd.DataFrame]],
        filename: str,
        sheet_name: str = 'Sheet1',
        **kwargs
    ) -> Path:
        """
        导出数据到Excel文件
        
        Args:
            data: 要导出的数据,可以是DataFrame、字典、列表或多Sheet字典
            filename: 文件名(不带扩展名)
            sheet_name: 工作表名称(当data不是多Sheet字典时使用)
            **kwargs: 传递给pandas.to_excel的额外参数
            
        Returns:
            导出文件的完整路径
            
        Raises:
            ValidationError: 当数据格式无效时
        """
        try:
            # 生成文件路径
            filepath = self.export_dir / f"{filename}.xlsx"
            
            # 检查是否为多Sheet数据
            if isinstance(data, dict) and all(isinstance(v, (pd.DataFrame, dict, list)) for v in data.values()):
                # 多Sheet导出
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    for sheet_name, sheet_data in data.items():
                        df = self._convert_to_dataframe(sheet_data)
                        df.to_excel(writer, sheet_name=sheet_name, index=False, **kwargs)
                
                logger.info(f"多Sheet数据已导出到Excel: {filepath}")
            else:
                # 单Sheet导出
                df = self._convert_to_dataframe(data)
                df.to_excel(filepath, sheet_name=sheet_name, index=False, engine='openpyxl', **kwargs)
                
                logger.info(f"数据已导出到Excel: {filepath}")
            
            return filepath
        
        except Exception as e:
            logger.error(f"导出Excel失败: {e}")
            raise DataFetchError(f"导出Excel失败: {str(e)}", source="Excel Export")
    
    def export_backtest_results(
        self,
        backtest_results: List[Dict[str, Any]],
        stock_code: str,
        stock_name: str
    ) -> Dict[str, Path]:
        """
        导出回测结果
        
        Args:
            backtest_results: 回测结果列表
            stock_code: 股票代码
            stock_name: 股票名称
            
        Returns:
            包含导出文件路径的字典
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"{stock_code}_{stock_name}_{timestamp}"
            
            exported_files = {}
            
            # 导出回测结果汇总
            summary_data = []
            for result in backtest_results:
                summary_data.append({
                    "策略名称": result.get("name", ""),
                    "夏普比率": result.get("metrics", {}).get("sharpe", 0),
                    "年化收益率": result.get("metrics", {}).get("cagr", 0),
                    "最大回撤": result.get("metrics", {}).get("max_drawdown", 0),
                    "胜率": result.get("metrics", {}).get("win_rate", 0),
                    "交易次数": result.get("buy_count", 0) + result.get("sell_count", 0)
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_file = self.export_to_csv(summary_df, f"{base_filename}_summary")
            exported_files["summary"] = summary_file
            
            # 导出详细回测数据
            detailed_data = []
            for result in backtest_results:
                strategy_name = result.get("name", "")
                signals = result.get("signals", [])
                
                for signal in signals:
                    detailed_data.append({
                        "策略名称": strategy_name,
                        "日期": signal.get("date", ""),
                        "类型": signal.get("type", ""),
                        "价格": signal.get("price", 0)
                    })
            
            if detailed_data:
                detailed_df = pd.DataFrame(detailed_data)
                detailed_file = self.export_to_csv(detailed_df, f"{base_filename}_details")
                exported_files["details"] = detailed_file
            
            # 导出Excel版本(包含所有数据)
            excel_data = {
                "回测汇总": summary_df
            }
            
            if detailed_data:
                excel_data["交易明细"] = pd.DataFrame(detailed_data)
            
            excel_file = self.export_to_excel(excel_data, f"{base_filename}_full")
            exported_files["excel"] = excel_file
            
            logger.info(f"回测结果导出完成: {exported_files}")
            return exported_files
        
        except Exception as e:
            logger.error(f"导出回测结果失败: {e}")
            raise DataFetchError(f"导出回测结果失败: {str(e)}", source="Backtest Export")
    
    def export_stock_data(
        self,
        stock_data: pd.DataFrame,
        stock_code: str,
        stock_name: str,
        indicators: Optional[Dict[str, pd.Series]] = None
    ) -> Dict[str, Path]:
        """
        导出股票数据
        
        Args:
            stock_data: 股票历史数据DataFrame
            stock_code: 股票代码
            stock_name: 股票名称
            indicators: 技术指标字典
            
        Returns:
            包含导出文件路径的字典
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"{stock_code}_{stock_name}_{timestamp}"
            
            exported_files = {}
            
            # 导出基础股票数据
            csv_file = self.export_to_csv(stock_data, f"{base_filename}_stock")
            exported_files["csv"] = csv_file
            
            # 导出Excel版本(包含指标)
            excel_data = {
                "股票数据": stock_data
            }
            
            if indicators:
                # 将指标合并到股票数据
                indicator_df = stock_data.copy()
                for indicator_name, indicator_series in indicators.items():
                    indicator_df[indicator_name] = indicator_series
                
                excel_data["技术指标"] = indicator_df
            
            excel_file = self.export_to_excel(excel_data, f"{base_filename}_full")
            exported_files["excel"] = excel_file
            
            logger.info(f"股票数据导出完成: {exported_files}")
            return exported_files
        
        except Exception as e:
            logger.error(f"导出股票数据失败: {e}")
            raise DataFetchError(f"导出股票数据失败: {str(e)}", source="Stock Data Export")
    
    def _convert_to_dataframe(self, data: Any) -> pd.DataFrame:
        """
        将各种数据格式转换为DataFrame
        
        Args:
            data: 输入数据
            
        Returns:
            DataFrame对象
            
        Raises:
            ValidationError: 当数据格式无法转换时
        """
        if isinstance(data, pd.DataFrame):
            return data
        elif isinstance(data, dict):
            # 检查是否为列名到列表的映射
            if all(isinstance(v, list) for v in data.values()):
                # 确保所有列表长度相同
                lengths = [len(v) for v in data.values()]
                if len(set(lengths)) == 1:
                    return pd.DataFrame(data)
            # 否则作为单行处理
            return pd.DataFrame([data])
        elif isinstance(data, list):
            if all(isinstance(item, dict) for item in data):
                return pd.DataFrame(data)
            else:
                return pd.DataFrame({"data": data})
        else:
            raise ValidationError(f"不支持的数据格式: {type(data)}")
    
    def get_export_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取导出历史记录
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            导出历史记录列表
        """
        try:
            export_files = []
            
            # 获取所有导出文件
            for ext in ['*.csv', '*.xlsx']:
                for filepath in self.export_dir.glob(ext):
                    stat = filepath.stat()
                    export_files.append({
                        "filename": filepath.name,
                        "filepath": str(filepath),
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_ctime),
                        "modified": datetime.fromtimestamp(stat.st_mtime),
                        "format": ext.replace('*', '')
                    })
            
            # 按修改时间排序
            export_files.sort(key=lambda x: x['modified'], reverse=True)
            
            return export_files[:limit]
        
        except Exception as e:
            logger.error(f"获取导出历史失败: {e}")
            return []
    
    def clear_old_exports(self, days: int = 7) -> int:
        """
        清除旧的导出文件
        
        Args:
            days: 保留天数,超过此天数的文件将被删除
            
        Returns:
            删除的文件数量
        """
        try:
            from datetime import timedelta
            cutoff_time = datetime.now() - timedelta(days=days)
            
            deleted_count = 0
            for filepath in self.export_dir.glob('*'):
                if filepath.is_file():
                    modified_time = datetime.fromtimestamp(filepath.stat().st_mtime)
                    if modified_time < cutoff_time:
                        filepath.unlink()
                        deleted_count += 1
                        logger.info(f"已删除旧导出文件: {filepath.name}")
            
            logger.info(f"清除了 {deleted_count} 个旧导出文件")
            return deleted_count
        
        except Exception as e:
            logger.error(f"清除旧导出文件失败: {e}")
            return 0


# 便捷函数
def export_to_csv(data: Any, filename: str, **kwargs) -> Path:
    """
    导出数据到CSV文件的便捷函数
    
    Args:
        data: 要导出的数据
        filename: 文件名(不带扩展名)
        **kwargs: 额外参数
        
    Returns:
        导出文件的完整路径
    """
    exporter = DataExporter()
    return exporter.export_to_csv(data, filename, **kwargs)


def export_to_excel(data: Any, filename: str, **kwargs) -> Path:
    """
    导出数据到Excel文件的便捷函数
    
    Args:
        data: 要导出的数据
        filename: 文件名(不带扩展名)
        **kwargs: 额外参数
        
    Returns:
        导出文件的完整路径
    """
    exporter = DataExporter()
    return exporter.export_to_excel(data, filename, **kwargs)