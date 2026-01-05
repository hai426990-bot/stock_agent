import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import re
from .logger import logger


class SignalParser:
    def __init__(self):
        self.signal_keywords = {
            'buy': ['买入', '建仓', '强烈买入', '推荐买入', '积极配置', '逢低吸纳', '加仓'],
            'sell': ['卖出', '清仓', '减仓', '强烈卖出', '回避', '逢高减持', '止盈'],
            'hold': ['持有', '观望', '中性', '维持', '继续持有']
        }
    
    def parse_strategy_report(self, strategy_content: str) -> Dict[str, Any]:
        signals = {
            'recommendation': None,
            'buy_price': None,
            'sell_price': None,
            'stop_loss': None,
            'target_price': None,
            'position_size': None,
            'hold_period': None
        }
        logger.debug(f"开始解析策略内容，长度: {len(strategy_content)}")
        
        content_lower = strategy_content.lower()
        
        for buy_keyword in self.signal_keywords['buy']:
            if buy_keyword in strategy_content:
                signals['recommendation'] = 'buy'
                logger.debug(f"检测到买入信号: {buy_keyword}")
                break
        
        for sell_keyword in self.signal_keywords['sell']:
            if sell_keyword in strategy_content:
                signals['recommendation'] = 'sell'
                logger.debug(f"检测到卖出信号: {sell_keyword}")
                break
        
        for hold_keyword in self.signal_keywords['hold']:
            if hold_keyword in strategy_content:
                if signals['recommendation'] is None:
                    signals['recommendation'] = 'hold'
                    logger.debug(f"检测到持有信号: {hold_keyword}")
        
        buy_price = self._extract_price(strategy_content, ['买入价格', '建仓价格', '买入价'])
        if buy_price:
            signals['buy_price'] = buy_price
            logger.debug(f"提取到买入价格: {buy_price}")
        
        target_price = self._extract_price(strategy_content, ['目标价格', '目标价', '目标价位'])
        if target_price:
            signals['target_price'] = target_price
            logger.debug(f"提取到目标价格: {target_price}")
        
        stop_loss = self._extract_price(strategy_content, ['止损价格', '止损价', '止损位'])
        if stop_loss:
            signals['stop_loss'] = stop_loss
            logger.debug(f"提取到止损价格: {stop_loss}")
        
        position_size = self._extract_percentage(strategy_content, ['建议仓位', '仓位', '配置比例'])
        if position_size:
            signals['position_size'] = position_size
            logger.debug(f"提取到仓位比例: {position_size}")
        
        hold_period = self._extract_period(strategy_content, ['持仓周期', '预计持仓', '持有时间'])
        if hold_period:
            signals['hold_period'] = hold_period
            logger.debug(f"提取到持仓周期: {hold_period}")
        
        logger.debug(f"解析完成，信号: {signals}")
        return signals
    
    def _extract_price(self, text: str, keywords: List[str]) -> Optional[float]:
        for keyword in keywords:
            pattern = rf'{keyword}[：:：]\s*([0-9]+\.?[0-9]*)'
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1))
                except:
                    continue
        return None
    
    def _extract_percentage(self, text: str, keywords: List[str]) -> Optional[float]:
        for keyword in keywords:
            pattern = rf'{keyword}[：:：]\s*([0-9]+\.?[0-9]*)%'
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1)) / 100
                except (ValueError, TypeError, AttributeError):
                    continue
        return None
    
    def _extract_period(self, text: str, keywords: List[str]) -> Optional[str]:
        for keyword in keywords:
            pattern = rf'{keyword}[：:：]\s*([^\n]+)'
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None


class BacktestEngine:
    def __init__(self, initial_capital: float = 100000.0, commission: float = 0.0003):
        self.initial_capital = initial_capital
        self.commission = commission
        self.signal_parser = SignalParser()
    
    def run_backtest(self, 
                    stock_data: pd.DataFrame,
                    strategy_signals: Dict[str, Any],
                    strategy_content: str = None) -> Dict[str, Any]:
        if strategy_content:
            parsed_signals = self.signal_parser.parse_strategy_report(strategy_content)
            strategy_signals.update(parsed_signals)
        
        if stock_data.empty:
            raise Exception("股票数据为空，无法进行回测")
        
        stock_data = stock_data.copy()
        stock_data = stock_data.sort_values('日期').reset_index(drop=True)
        
        capital = self.initial_capital
        position = 0
        trades = []
        equity_curve = []
        daily_returns = []
        
        buy_price = strategy_signals.get('buy_price')
        sell_price = strategy_signals.get('sell_price')
        stop_loss = strategy_signals.get('stop_loss')
        target_price = strategy_signals.get('target_price')
        position_size = strategy_signals.get('position_size', 1.0)
        
        if not buy_price:
            current_price = stock_data.iloc[0]['收盘']
            buy_price = current_price
            logger.debug(f"未找到买入价格，使用当前价格: {buy_price}")
        
        if not stop_loss:
            stop_loss = buy_price * 0.95
            logger.debug(f"未找到止损价格，设置为买入价的95%: {stop_loss}")
        
        if not target_price:
            target_price = buy_price * 1.10
            logger.debug(f"未找到目标价格，设置为买入价的110%: {target_price}")
        
        in_position = False
        
        for idx, row in stock_data.iterrows():
            date = row['日期']
            close_price = row['收盘']
            high_price = row['最高']
            low_price = row['最低']
            
            if not in_position:
                if buy_price and close_price <= buy_price * 1.02:
                    shares = int((capital * position_size) / close_price)
                    if shares > 0:
                        cost = shares * close_price * (1 + self.commission)
                        capital -= cost
                        position = shares
                        in_position = True
                        
                        trades.append({
                            'date': date,
                            'type': 'buy',
                            'price': close_price,
                            'shares': shares,
                            'amount': cost,
                            'capital_after': capital + position * close_price
                        })
            
            if in_position:
                current_value = position * close_price
                total_value = capital + current_value
                
                should_sell = False
                sell_reason = ''
                
                if sell_price and close_price >= sell_price:
                    should_sell = True
                    sell_reason = 'target_price'
                elif stop_loss and close_price <= stop_loss:
                    should_sell = True
                    sell_reason = 'stop_loss'
                elif target_price and close_price >= target_price:
                    should_sell = True
                    sell_reason = 'target_price'
                
                if should_sell:
                    revenue = position * close_price * (1 - self.commission)
                    capital += revenue
                    profit = revenue - trades[-1]['amount']
                    profit_pct = (profit / trades[-1]['amount']) * 100
                    
                    trades.append({
                        'date': date,
                        'type': 'sell',
                        'price': close_price,
                        'shares': position,
                        'amount': revenue,
                        'profit': profit,
                        'profit_pct': profit_pct,
                        'reason': sell_reason,
                        'capital_after': capital
                    })
                    
                    position = 0
                    in_position = False
                
                equity_curve.append({
                    'date': date,
                    'equity': total_value,
                    'price': close_price
                })
                
                if len(equity_curve) > 1:
                    daily_return = (equity_curve[-1]['equity'] / equity_curve[-2]['equity']) - 1
                    daily_returns.append(daily_return)
        
        if in_position:
            current_value = position * stock_data.iloc[-1]['收盘']
            total_value = capital + current_value
            revenue = position * stock_data.iloc[-1]['收盘'] * (1 - self.commission)
            capital += revenue
            profit = revenue - trades[-1]['amount']
            profit_pct = (profit / trades[-1]['amount']) * 100
            
            trades.append({
                'date': stock_data.iloc[-1]['日期'],
                'type': 'sell',
                'price': stock_data.iloc[-1]['收盘'],
                'shares': position,
                'amount': revenue,
                'profit': profit,
                'profit_pct': profit_pct,
                'reason': 'end_of_period',
                'capital_after': capital
            })
            
            equity_curve.append({
                'date': stock_data.iloc[-1]['日期'],
                'equity': total_value,
                'price': stock_data.iloc[-1]['收盘']
            })
        
        metrics = self._calculate_metrics(equity_curve, daily_returns, trades)
        
        return {
            'trades': trades,
            'equity_curve': equity_curve,
            'metrics': metrics,
            'signals_used': strategy_signals
        }
    
    def _calculate_metrics(self, 
                          equity_curve: List[Dict[str, Any]],
                          daily_returns: List[float],
                          trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not equity_curve:
            return {}
        
        final_equity = equity_curve[-1]['equity']
        total_return = ((final_equity - self.initial_capital) / self.initial_capital) * 100
        
        equity_values = [e['equity'] for e in equity_curve]
        max_equity = np.maximum.accumulate(equity_values)
        drawdowns = (np.array(equity_values) - max_equity) / max_equity
        max_drawdown = abs(drawdowns.min()) * 100
        
        if daily_returns:
            avg_daily_return = np.mean(daily_returns) * 100
            std_daily_return = np.std(daily_returns) * 100
            
            if std_daily_return > 0:
                sharpe_ratio = (avg_daily_return / std_daily_return) * np.sqrt(252)
            else:
                sharpe_ratio = 0
            
            positive_returns = [r for r in daily_returns if r > 0]
            negative_returns = [r for r in daily_returns if r < 0]
            
            if positive_returns and negative_returns:
                avg_profit = np.mean(positive_returns) * 100
                avg_loss = np.mean(negative_returns) * 100
                profit_loss_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else 0
            else:
                avg_profit = 0
                avg_loss = 0
                profit_loss_ratio = 0
            
            win_rate = (len(positive_returns) / len(daily_returns)) * 100
        else:
            avg_daily_return = 0
            std_daily_return = 0
            sharpe_ratio = 0
            avg_profit = 0
            avg_loss = 0
            profit_loss_ratio = 0
            win_rate = 0
        
        buy_trades = [t for t in trades if t['type'] == 'buy']
        sell_trades = [t for t in trades if t['type'] == 'sell']
        
        completed_trades = []
        for i, buy_trade in enumerate(buy_trades):
            if i < len(sell_trades):
                completed_trades.append({
                    'buy_date': buy_trade['date'],
                    'sell_date': sell_trades[i]['date'],
                    'buy_price': buy_trade['price'],
                    'sell_price': sell_trades[i]['price'],
                    'profit': sell_trades[i].get('profit', 0),
                    'profit_pct': sell_trades[i].get('profit_pct', 0),
                    'reason': sell_trades[i].get('reason', '')
                })
        
        if completed_trades:
            trade_returns = [t['profit_pct'] for t in completed_trades]
            win_trades = [t for t in completed_trades if t['profit_pct'] > 0]
            trade_win_rate = (len(win_trades) / len(completed_trades)) * 100
            avg_trade_return = np.mean(trade_returns)
            max_trade_profit = max(trade_returns)
            max_trade_loss = min(trade_returns)
        else:
            trade_win_rate = 0
            avg_trade_return = 0
            max_trade_profit = 0
            max_trade_loss = 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_equity': final_equity,
            'total_return': round(total_return, 2),
            'max_drawdown': round(max_drawdown, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'avg_daily_return': round(avg_daily_return, 2),
            'std_daily_return': round(std_daily_return, 2),
            'profit_loss_ratio': round(profit_loss_ratio, 2),
            'win_rate': round(win_rate, 2),
            'trade_count': len(completed_trades),
            'trade_win_rate': round(trade_win_rate, 2),
            'avg_trade_return': round(avg_trade_return, 2),
            'max_trade_profit': round(max_trade_profit, 2),
            'max_trade_loss': round(max_trade_loss, 2),
            'completed_trades': completed_trades
        }
    
    def generate_backtest_report(self, backtest_result: Dict[str, Any]) -> str:
        metrics = backtest_result['metrics']
        trades = backtest_result['trades']
        
        report = f"""【回测报告】

一、回测概览
• 初始资金：¥{metrics['initial_capital']:,.2f}
• 最终资金：¥{metrics['final_equity']:,.2f}
• 总收益率：{metrics['total_return']:.2f}%
• 交易次数：{metrics['trade_count']}次
• 胜率：{metrics['trade_win_rate']:.2f}%

二、风险指标
• 最大回撤：{metrics['max_drawdown']:.2f}%
• 夏普比率：{metrics['sharpe_ratio']:.2f}
• 日均收益率：{metrics['avg_daily_return']:.2f}%
• 日均波动率：{metrics['std_daily_return']:.2f}%

三、交易分析
• 平均每笔收益：{metrics['avg_trade_return']:.2f}%
• 最大单笔盈利：{metrics['max_trade_profit']:.2f}%
• 最大单笔亏损：{metrics['max_trade_loss']:.2f}%
• 盈亏比：{metrics['profit_loss_ratio']:.2f}

四、交易明细
"""
        
        for i, trade in enumerate(trades, 1):
            if trade['type'] == 'buy':
                report += f"\n交易{i} - 买入：{trade['date']} @ ¥{trade['price']:.2f}，{trade['shares']}股"
            else:
                report += f"\n交易{i} - 卖出：{trade['date']} @ ¥{trade['price']:.2f}，"
                if 'profit' in trade:
                    profit_color = "盈利" if trade['profit'] > 0 else "亏损"
                    report += f"{profit_color} ¥{trade['profit']:,.2f} ({trade['profit_pct']:.2f}%)，原因：{trade.get('reason', '')}"
        
        return report
