"""
同花顺新闻实时抓取工具
"""
import requests
from datetime import datetime
from typing import List, Dict, Optional
import json


class News10jqkaFetcher:
    """同花顺新闻数据获取器"""
    
    def __init__(self):
        self.base_url = "https://news.10jqka.com.cn/tapp/news/push/stock/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://news.10jqka.com.cn/',
            'Origin': 'https://news.10jqka.com.cn'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def fetch_news(self, limit: int = 20, page: int = 1) -> List[Dict]:
        """
        获取同花顺实时新闻
        
        Args:
            limit: 获取新闻数量限制
            page: 页码，默认为1
            
        Returns:
            新闻列表，每条新闻包含 title, time, content, url 等字段
        """
        try:
            params = {
                'page': page,
                'tag': '',
                'track': 'website',
                'pagesize': limit
            }
            
            response = self.session.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 检查返回状态
            if data.get('code') != '200':
                print(f"⚠️ API返回异常: {data.get('msg', 'unknown')}")
                return []
            
            # 解析新闻列表
            news_list = []
            news_data = data.get('data', {}).get('list', [])
            
            for item in news_data[:limit]:
                try:
                    news = self._parse_news_item(item)
                    if news:
                        news_list.append(news)
                except Exception as e:
                    print(f"⚠️ 解析新闻项失败: {e}")
                    continue
            
            print(f"✅ 获取到 {len(news_list)} 条新闻")
            return news_list
            
        except Exception as e:
            print(f"❌ 获取同花顺新闻失败: {e}")
            return []
    
    def _parse_news_item(self, item: Dict) -> Optional[Dict]:
        """解析单个新闻项"""
        try:
            # 提取标题
            title = item.get('title', '无标题')
            
            # 提取时间
            ctime = item.get('ctime', 0)
            if ctime:
                try:
                    dt = datetime.fromtimestamp(int(ctime))
                    time_str = dt.strftime('%H:%M:%S')
                    date_str = dt.strftime('%Y-%m-%d')
                except:
                    time_str = datetime.now().strftime('%H:%M:%S')
                    date_str = datetime.now().strftime('%Y-%m-%d')
            else:
                time_str = datetime.now().strftime('%H:%M:%S')
                date_str = datetime.now().strftime('%Y-%m-%d')
            
            # 提取内容
            content = item.get('digest', item.get('short', ''))
            
            # 提取链接
            url = item.get('url', '')
            
            # 提取相关股票
            stocks = item.get('stock', [])
            stock_info = []
            if stocks:
                for stock in stocks[:5]:  # 最多显示5个相关股票
                    stock_name = stock.get('name', '')
                    stock_code = stock.get('stockCode', '')
                    if stock_name:
                        stock_info.append(f"{stock_name}({stock_code})")
            
            # 提取标签
            tags = item.get('tags', [])
            tag_list = [tag.get('name', '') for tag in tags if tag.get('name')]
            
            return {
                'title': title,
                'time': time_str,
                'date': date_str,
                'content': content,
                'url': url,
                'source': '同花顺新闻',
                'timestamp': datetime.now().isoformat(),
                'stocks': stock_info,
                'tags': tag_list,
                'id': item.get('id', '')
            }
            
        except Exception as e:
            print(f"⚠️ 解析新闻项失败: {e}")
            return None


def get_10jqka_news(limit: int = 20, page: int = 1) -> List[Dict]:
    """
    获取同花顺实时新闻
    
    Args:
        limit: 获取新闻数量限制
        page: 页码，默认为1
        
    Returns:
        新闻列表
    """
    fetcher = News10jqkaFetcher()
    return fetcher.fetch_news(limit, page)


if __name__ == "__main__":
    # 测试代码
    print("正在获取同花顺新闻...")
    news_list = get_10jqka_news(limit=10)
    
    print(f"\n获取到 {len(news_list)} 条新闻：\n")
    for i, news in enumerate(news_list, 1):
        print(f"{i}. 【{news['time']}】{news['title']}")
        if news['stocks']:
            print(f"   相关股票: {', '.join(news['stocks'])}")
        print(f"   {news['content'][:100]}...")
        print()