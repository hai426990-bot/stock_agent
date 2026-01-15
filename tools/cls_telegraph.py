"""
财联社电报实时新闻抓取工具
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
from typing import List, Dict, Optional
import json
import re


class CLSTelegraphFetcher:
    """财联社电报数据获取器"""
    
    def __init__(self):
        self.base_url = "https://www.cls.cn/telegraph"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def fetch_telegraph(self, limit: int = 20) -> List[Dict]:
        """
        获取财联社电报实时新闻
        
        Args:
            limit: 获取新闻数量限制
            
        Returns:
            新闻列表，每条新闻包含 title, time, content, url 等字段
        """
        try:
            response = self.session.get(self.base_url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            news_list = []
            
            # 尝试多种选择器来匹配财联社电报的结构
            selectors = [
                'div.telegraph-item',
                'div.telegraph-list-item',
                'article',
                'div.news-item',
                'li.news-item',
                'div[data-type="telegraph"]',
                '.telegraph-content',
                '.news-content'
            ]
            
            news_items = []
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    news_items = items
                    print(f"✅ 找到 {len(items)} 条新闻，使用选择器: {selector}")
                    break
            
            # 如果没有找到，尝试解析文本内容
            if not news_items:
                print("⚠️ 未找到标准新闻结构，尝试解析文本内容")
                return self._parse_text_content(response.text, limit)
            
            for item in news_items[:limit]:
                try:
                    news = self._parse_news_item(item)
                    if news:
                        news_list.append(news)
                except Exception as e:
                    print(f"⚠️ 解析新闻项失败: {e}")
                    continue
            
            return news_list
            
        except Exception as e:
            print(f"❌ 获取财联社电报失败: {e}")
            return []
    
    def _parse_news_item(self, item) -> Optional[Dict]:
        """解析单个新闻项"""
        try:
            # 尝试提取标题
            title = None
            title_selectors = ['h3', 'h4', 'h2', '.title', '.headline', 'a']
            for selector in title_selectors:
                title_elem = item.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            if not title:
                # 如果没有找到标题，尝试提取整个文本
                title = item.get_text(strip=True)
                # 截取前 100 个字符作为标题
                if len(title) > 100:
                    title = title[:100] + "..."
            
            # 尝试提取时间
            time_str = None
            time_selectors = ['.time', '.date', 'time', '.publish-time', '[data-time]']
            for selector in time_selectors:
                time_elem = item.select_one(selector)
                if time_elem:
                    time_str = time_elem.get_text(strip=True)
                    break
            
            # 尝试提取链接
            url = None
            link_elem = item.select_one('a')
            if link_elem:
                url = link_elem.get('href', '')
                if url and not url.startswith('http'):
                    url = 'https://www.cls.cn' + url
            
            # 提取内容
            content = item.get_text(strip=True)
            
            # 清理内容
            content = re.sub(r'\s+', ' ', content)
            content = content.replace('\n', ' ')
            
            return {
                'title': title or '无标题',
                'time': time_str or datetime.now().strftime('%H:%M:%S'),
                'content': content,
                'url': url,
                'source': '财联社电报',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"⚠️ 解析新闻项失败: {e}")
            return None
    
    def _parse_text_content(self, text: str, limit: int) -> List[Dict]:
        """从文本内容中解析新闻"""
        news_list = []
        
        # 清理 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        # 尝试按时间戳分割
        time_pattern = r'\d{2}:\d{2}:\d{2}'
        parts = re.split(time_pattern, text)
        times = re.findall(time_pattern, text)
        
        # 无效内容的关键词列表
        invalid_keywords = [
            '关于我们', '网站声明', '联系方式', '用户反馈', '网站地图', '帮助',
            '首页', '电报', '话题', '盯盘', 'VIP', 'FM', '投研', '下载', '全部',
            '加红', '公司', '看盘', '港美股', '基金', '提醒', '电报持续更新中',
            '财联社A股24小时电报', '上市公司动态', '今日股市行情报道'
        ]
        
        for i, (time_str, content) in enumerate(zip(times, parts)):
            if i >= limit:
                break
            
            content = content.strip()
            if not content or len(content) < 10:
                continue
            
            # 过滤无效内容
            is_invalid = False
            
            # 检查是否包含无效关键词（如果包含多个，说明是导航菜单）
            invalid_count = sum(1 for keyword in invalid_keywords if keyword in content)
            if invalid_count >= 3:
                is_invalid = True
            
            # 检查是否是页面标题
            if '财联社A股24小时电报' in content and invalid_count >= 2:
                is_invalid = True
            
            # 跳过无效内容
            if is_invalid:
                continue
            
            # 提取标题（通常是第一个括号内的内容）
            title_match = re.search(r'【(.*?)】', content)
            title = title_match.group(1) if title_match else None
            
            # 如果没有找到标题，使用内容的前 50 个字符
            if not title:
                title = content[:50] + "..." if len(content) > 50 else content
            
            # 清理内容，移除标题部分
            clean_content = content
            if title_match:
                clean_content = content.replace(f"【{title}】", "").strip()
            
            # 移除"财联社X月X日电"前缀
            clean_content = re.sub(r'财联社\d+月\d+日电[，,]?\s*', '', clean_content)
            
            # 再次清理，移除导航菜单残留
            for keyword in invalid_keywords:
                clean_content = clean_content.replace(keyword, '').strip()
            
            # 确保内容不为空
            if not clean_content or len(clean_content) < 5:
                continue
            
            news_list.append({
                'title': title,
                'time': time_str,
                'content': clean_content,
                'url': self.base_url,
                'source': '财联社电报',
                'timestamp': datetime.now().isoformat()
            })
        
        return news_list


def get_cls_telegraph(limit: int = 20) -> List[Dict]:
    """
    获取财联社电报实时新闻
    
    Args:
        limit: 获取新闻数量限制
        
    Returns:
        新闻列表
    """
    fetcher = CLSTelegraphFetcher()
    return fetcher.fetch_telegraph(limit)


if __name__ == "__main__":
    # 测试代码
    print("正在获取财联社电报...")
    news_list = get_cls_telegraph(limit=10)
    
    print(f"\n获取到 {len(news_list)} 条电报：\n")
    for i, news in enumerate(news_list, 1):
        print(f"{i}. 【{news['time']}】{news['title']}")
        print(f"   {news['content'][:100]}...")
        print()