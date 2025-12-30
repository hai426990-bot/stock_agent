from typing import Dict, Any, List
import json


class BacktestVisualizer:
    def __init__(self):
        pass
    
    def generate_equity_curve_chart(self, backtest_result: Dict[str, Any]) -> Dict[str, Any]:
        equity_curve = backtest_result.get('equity_curve', [])
        metrics = backtest_result.get('metrics', {})
        
        dates = [e['date'] for e in equity_curve]
        equity_values = [e['equity'] for e in equity_curve]
        prices = [e['price'] for e in equity_curve]
        
        initial_capital = metrics.get('initial_capital', 100000)
        
        return {
            'title': {
                'text': '资金曲线',
                'left': 'center'
            },
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {
                    'type': 'cross'
                }
            },
            'legend': {
                'data': ['资金曲线', '基准线'],
                'top': 30
            },
            'grid': {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'containLabel': True
            },
            'xAxis': {
                'type': 'category',
                'data': dates,
                'boundaryGap': False
            },
            'yAxis': [
                {
                    'type': 'value',
                    'name': '资金',
                    'position': 'left',
                    'axisLabel': {
                        'formatter': '¥{value}'
                    }
                },
                {
                    'type': 'value',
                    'name': '股价',
                    'position': 'right',
                    'axisLabel': {
                        'formatter': '¥{value}'
                    }
                }
            ],
            'series': [
                {
                    'name': '资金曲线',
                    'type': 'line',
                    'data': equity_values,
                    'smooth': True,
                    'lineStyle': {
                        'width': 2,
                        'color': '#3498db'
                    },
                    'areaStyle': {
                        'color': {
                            'type': 'linear',
                            'x': 0,
                            'y': 0,
                            'x2': 0,
                            'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(52, 152, 219, 0.3)'},
                                {'offset': 1, 'color': 'rgba(52, 152, 219, 0.05)'}
                            ]
                        }
                    }
                },
                {
                    'name': '基准线',
                    'type': 'line',
                    'data': [initial_capital] * len(dates),
                    'lineStyle': {
                        'type': 'dashed',
                        'color': '#95a5a6'
                    }
                },
                {
                    'name': '股价',
                    'type': 'line',
                    'yAxisIndex': 1,
                    'data': prices,
                    'lineStyle': {
                        'width': 1,
                        'color': '#e74c3c',
                        'opacity': 0.5
                    }
                }
            ]
        }
    
    def generate_drawdown_chart(self, backtest_result: Dict[str, Any]) -> Dict[str, Any]:
        equity_curve = backtest_result.get('equity_curve', [])
        
        if not equity_curve:
            return {}
        
        dates = [e['date'] for e in equity_curve]
        equity_values = [e['equity'] for e in equity_curve]
        
        import numpy as np
        max_equity = np.maximum.accumulate(equity_values)
        drawdowns = ((np.array(equity_values) - max_equity) / max_equity * 100).tolist()
        
        return {
            'title': {
                'text': '回撤曲线',
                'left': 'center'
            },
            'tooltip': {
                'trigger': 'axis',
                'formatter': '{b}<br/>回撤：{c}%'
            },
            'grid': {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'containLabel': True
            },
            'xAxis': {
                'type': 'category',
                'data': dates,
                'boundaryGap': False
            },
            'yAxis': {
                'type': 'value',
                'name': '回撤(%)',
                'axisLabel': {
                    'formatter': '{value}%'
                }
            },
            'series': [
                {
                    'name': '回撤',
                    'type': 'line',
                    'data': drawdowns,
                    'smooth': True,
                    'lineStyle': {
                        'width': 2,
                        'color': '#e74c3c'
                    },
                    'areaStyle': {
                        'color': {
                            'type': 'linear',
                            'x': 0,
                            'y': 0,
                            'x2': 0,
                            'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(231, 76, 60, 0.3)'},
                                {'offset': 1, 'color': 'rgba(231, 76, 60, 0.05)'}
                            ]
                        }
                    },
                    'markLine': {
                        'data': [
                            {'type': 'average', 'name': '平均回撤'}
                        ]
                    }
                }
            ]
        }
    
    def generate_trade_distribution_chart(self, backtest_result: Dict[str, Any]) -> Dict[str, Any]:
        metrics = backtest_result.get('metrics', {})
        completed_trades = metrics.get('completed_trades', [])
        
        if not completed_trades:
            return {}
        
        trade_returns = [t['profit_pct'] for t in completed_trades]
        trade_dates = [t['buy_date'] for t in completed_trades]
        
        colors = ['#2ecc71' if r > 0 else '#e74c3c' for r in trade_returns]
        
        return {
            'title': {
                'text': '交易收益分布',
                'left': 'center'
            },
            'tooltip': {
                'trigger': 'axis',
                'formatter': function_formatter
            },
            'grid': {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'containLabel': True
            },
            'xAxis': {
                'type': 'category',
                'data': trade_dates
            },
            'yAxis': {
                'type': 'value',
                'name': '收益率(%)',
                'axisLabel': {
                    'formatter': '{value}%'
                }
            },
            'series': [
                {
                    'name': '收益率',
                    'type': 'bar',
                    'data': [
                        {
                            'value': r,
                            'itemStyle': {'color': c}
                        }
                        for r, c in zip(trade_returns, colors)
                    ],
                    'markLine': {
                        'data': [
                            {'yAxis': 0, 'name': '盈亏平衡线'}
                        ]
                    }
                }
            ]
        }
    
    def generate_metrics_dashboard(self, backtest_result: Dict[str, Any]) -> Dict[str, Any]:
        metrics = backtest_result.get('metrics', {})
        
        return {
            'title': {
                'text': '回测指标概览',
                'left': 'center'
            },
            'tooltip': {},
            'radar': {
                'indicator': [
                    {'name': '总收益率', 'max': 100},
                    {'name': '胜率', 'max': 100},
                    {'name': '夏普比率', 'max': 3},
                    {'name': '盈亏比', 'max': 5},
                    {'name': '交易胜率', 'max': 100}
                ],
                'shape': 'polygon',
                'splitNumber': 5,
                'name': {
                    'textStyle': {
                        'color': '#999'
                    }
                },
                'splitLine': {
                    'lineStyle': {
                        'color': ['#eee', '#ddd', '#ccc']
                    }
                },
                'splitArea': {
                    'show': True,
                    'areaStyle': {
                        'color': ['rgba(114, 172, 209, 0.1)', 'rgba(114, 172, 209, 0.05)']
                    }
                },
                'axisLine': {
                    'lineStyle': {
                        'color': '#999'
                    }
                }
            },
            'series': [
                {
                    'name': '回测指标',
                    'type': 'radar',
                    'data': [
                        {
                            'value': [
                                abs(metrics.get('total_return', 0)),
                                metrics.get('trade_win_rate', 0),
                                max(0, metrics.get('sharpe_ratio', 0)),
                                metrics.get('profit_loss_ratio', 0),
                                metrics.get('trade_win_rate', 0)
                            ],
                            'name': '当前策略',
                            'areaStyle': {
                                'color': 'rgba(52, 152, 219, 0.3)'
                            },
                            'lineStyle': {
                                'color': '#3498db'
                            },
                            'itemStyle': {
                                'color': '#3498db'
                            }
                        }
                    ]
                }
            ]
        }


def function_formatter(params):
    return f'{params[0].name}<br/>收益率：{params[0].value:.2f}%'
