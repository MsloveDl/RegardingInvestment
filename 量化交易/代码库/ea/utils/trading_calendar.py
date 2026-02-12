"""
交易日历工具
提供交易日判断功能
"""

from datetime import datetime, timedelta
import os
import json


class TradingCalendar:
    """交易日历管理器"""
    
    def __init__(self, calendar_file='config/trading_calendar.json'):
        """
        初始化交易日历
        
        Args:
            calendar_file: 交易日历文件路径
        """
        self.calendar_file = calendar_file
        self.trading_days = set()
        self.holidays = set()
        self._load_calendar()
    
    def _load_calendar(self):
        """加载交易日历"""
        if os.path.exists(self.calendar_file):
            try:
                with open(self.calendar_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.trading_days = set(data.get('trading_days', []))
                    self.holidays = set(data.get('holidays', []))
            except Exception as e:
                print(f"加载交易日历失败: {e}")
    
    def is_trading_day(self, date=None):
        """
        判断是否为交易日
        
        Args:
            date: 日期字符串（格式：YYYY-MM-DD）或 datetime 对象，默认为今天
        
        Returns:
            bool: 是否为交易日
        """
        if date is None:
            date = datetime.now()
        
        if isinstance(date, datetime):
            date_str = date.strftime('%Y-%m-%d')
        else:
            date_str = date
        
        # 如果有交易日历数据，使用交易日历
        if self.trading_days:
            return date_str in self.trading_days
        
        # 否则使用简单规则：周一到周五，排除节假日
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        
        # 检查是否为周末
        if date.weekday() >= 5:  # 5=周六, 6=周日
            return False
        
        # 检查是否为节假日
        if date_str in self.holidays:
            return False
        
        return True
    
    def get_next_trading_day(self, date=None, n=1):
        """
        获取下一个交易日
        
        Args:
            date: 起始日期，默认为今天
            n: 第 n 个交易日
        
        Returns:
            datetime: 下一个交易日
        """
        if date is None:
            date = datetime.now()
        
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        
        count = 0
        current = date + timedelta(days=1)
        
        while count < n:
            if self.is_trading_day(current):
                count += 1
                if count == n:
                    return current
            current += timedelta(days=1)
        
        return current
    
    def get_prev_trading_day(self, date=None, n=1):
        """
        获取前一个交易日
        
        Args:
            date: 起始日期，默认为今天
            n: 第 n 个交易日
        
        Returns:
            datetime: 前一个交易日
        """
        if date is None:
            date = datetime.now()
        
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        
        count = 0
        current = date - timedelta(days=1)
        
        while count < n:
            if self.is_trading_day(current):
                count += 1
                if count == n:
                    return current
            current -= timedelta(days=1)
        
        return current
    
    def is_trading_time(self, time=None):
        """
        判断是否为交易时间
        
        Args:
            time: 时间对象，默认为当前时间
        
        Returns:
            bool: 是否为交易时间
        """
        if time is None:
            time = datetime.now()
        
        # 首先检查是否为交易日
        if not self.is_trading_day(time):
            return False
        
        # 检查是否在交易时间段内
        current_time = time.time()
        
        # 上午：09:30 - 11:30
        morning_start = datetime.strptime('09:30:00', '%H:%M:%S').time()
        morning_end = datetime.strptime('11:30:00', '%H:%M:%S').time()
        
        # 下午：13:00 - 15:00
        afternoon_start = datetime.strptime('13:00:00', '%H:%M:%S').time()
        afternoon_end = datetime.strptime('15:00:00', '%H:%M:%S').time()
        
        return (morning_start <= current_time <= morning_end) or \
               (afternoon_start <= current_time <= afternoon_end)
    
    def save_calendar(self, trading_days=None, holidays=None):
        """
        保存交易日历
        
        Args:
            trading_days: 交易日列表
            holidays: 节假日列表
        """
        if trading_days is not None:
            self.trading_days = set(trading_days)
        
        if holidays is not None:
            self.holidays = set(holidays)
        
        # 创建目录
        os.makedirs(os.path.dirname(self.calendar_file), exist_ok=True)
        
        # 保存到文件
        data = {
            'trading_days': list(self.trading_days),
            'holidays': list(self.holidays)
        }
        
        with open(self.calendar_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# 全局交易日历实例
trading_calendar = TradingCalendar()
