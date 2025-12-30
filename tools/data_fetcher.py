import akshare as ak
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

class DataFetcher:
    def __init__(self):
        pass
    
    def get_stock_info(self, stock_code: str) -> Dict[str, Any]:
        try:
            spot_data = ak.stock_zh_a_spot_em()
            
            if spot_data is None or spot_data.empty:
                raise Exception("无法获取股票信息：返回数据为空")
            
            stock_row = spot_data[spot_data['代码'] == stock_code]
            
            if stock_row.empty:
                raise Exception(f"无法获取股票信息：未找到股票代码 {stock_code}")
            
            stock = stock_row.iloc[0]
            
            return {
                'stock_code': stock_code,
                'stock_name': stock.get('名称', ''),
                'current_price': stock.get('最新价', 0.0),
                'market_cap': stock.get('总市值', ''),
                'pe_ratio': stock.get('市盈率-动态', ''),
                'pb_ratio': stock.get('市净率', ''),
                'turnover_rate': stock.get('换手率', ''),
                'volume_ratio': stock.get('量比', ''),
                'high_52w': '',
                'low_52w': '',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            raise Exception(f"获取股票信息失败: {str(e)}")
    
    def get_kline_data(self, stock_code: str, period: str = 'daily', count: int = 120) -> pd.DataFrame:
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=count * 2)).strftime('%Y%m%d')
            
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            return df.tail(count)
        except Exception as e:
            raise Exception(f"获取K线数据失败: {str(e)}")
    
    def get_financial_data(self, stock_code: str) -> Dict[str, Any]:
        try:
            financial_abstract = ak.stock_financial_abstract(symbol=stock_code)
            
            if financial_abstract is None or financial_abstract.empty:
                return {}
            
            latest_col = '20250930'
            if latest_col not in financial_abstract.columns:
                latest_col = financial_abstract.columns[2]
            
            def get_indicator_value(indicator_name: str) -> str:
                try:
                    row = financial_abstract[financial_abstract['指标'] == indicator_name]
                    if not row.empty:
                        value = row.iloc[0][latest_col]
                        if pd.notna(value):
                            return str(value)
                except Exception:
                    pass
                return ''
            
            return {
                'roe': get_indicator_value('净资产收益率(ROE)'),
                'roa': get_indicator_value('总资产报酬率(ROA)'),
                'gross_margin': get_indicator_value('毛利率'),
                'net_margin': get_indicator_value('销售净利率'),
                'debt_ratio': get_indicator_value('资产负债率'),
                'current_ratio': get_indicator_value('流动比率'),
                'revenue_growth': get_indicator_value('营业总收入增长率'),
                'profit_growth': get_indicator_value('归属母公司净利润增长率')
            }
        except Exception as e:
            return {}
    
    def get_fund_flow(self, stock_code: str) -> Dict[str, Any]:
        try:
            fund_flow = ak.stock_individual_fund_flow_rank(indicator="今日")
            
            if fund_flow is None:
                return {}
            
            if isinstance(fund_flow, pd.DataFrame):
                if fund_flow.empty:
                    return {}
                
                filtered = fund_flow[fund_flow['代码'] == stock_code]
                if filtered.empty:
                    return {}
                
                try:
                    flow_data = filtered.iloc[0].to_dict()
                except Exception as e:
                    return {}
            else:
                try:
                    flow_data = dict(fund_flow)
                except Exception as e:
                    return {}
            
            return {
                'main_net_inflow': flow_data.get('今日主力净流入-净额', ''),
                'main_net_inflow_pct': flow_data.get('今日主力净流入-净占比', ''),
                'super_large_net_inflow': flow_data.get('今日超大单净流入-净额', ''),
                'large_net_inflow': flow_data.get('今日大单净流入-净额', ''),
                'medium_net_inflow': flow_data.get('今日中单净流入-净额', ''),
                'small_net_inflow': flow_data.get('今日小单净流入-净额', '')
            }
        except Exception as e:
            return {}
    
    def get_market_sentiment(self) -> Dict[str, Any]:
        try:
            market_sentiment = ak.stock_market_activity_legu()
            
            if market_sentiment is None:
                return {}
            
            if isinstance(market_sentiment, pd.DataFrame):
                if market_sentiment.empty:
                    return {}
                try:
                    sentiment_dict = {}
                    for _, row in market_sentiment.iterrows():
                        if 'item' in row and 'value' in row:
                            sentiment_dict[row['item']] = row['value']
                except Exception as e:
                    return {}
            else:
                try:
                    sentiment_dict = dict(market_sentiment)
                except Exception as e:
                    return {}
            
            up_count = sentiment_dict.get('上涨', 0)
            down_count = sentiment_dict.get('下跌', 0)
            limit_up_count = sentiment_dict.get('涨停', 0)
            limit_down_count = sentiment_dict.get('跌停', 0)
            flat_count = sentiment_dict.get('平盘', 0)
            activity_level = sentiment_dict.get('活跃度', '0%')
            
            total_count = up_count + down_count + flat_count
            up_down_ratio = round(up_count / down_count, 2) if down_count > 0 else 0
            market_heat = round(up_count / total_count * 100, 2) if total_count > 0 else 0
            
            return {
                'up_count': up_count,
                'down_count': down_count,
                'flat_count': flat_count,
                'total_count': total_count,
                'up_down_ratio': up_down_ratio,
                'market_heat': market_heat,
                'activity_level': activity_level,
                'limit_up_count': limit_up_count,
                'limit_down_count': limit_down_count
            }
        except Exception as e:
            return {}
    
    def get_comprehensive_data(self, stock_code: str) -> Dict[str, Any]:
        stock_info = self.get_stock_info(stock_code)
        kline_data = self.get_kline_data(stock_code)
        financial_data = self.get_financial_data(stock_code)
        fund_flow = self.get_fund_flow(stock_code)
        market_sentiment = self.get_market_sentiment()
        
        kline_records = []
        try:
            if not kline_data.empty:
                kline_records = kline_data.to_dict('records')
        except Exception as e:
            kline_records = []
        
        return {
            'stock_info': stock_info,
            'kline_data': kline_records,
            'financial_data': financial_data,
            'fund_flow': fund_flow,
            'market_sentiment': market_sentiment
        }
