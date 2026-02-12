"""
个股监控模块测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import DataAdapter, StockMonitor
from utils import logger, signal_bus, SignalType
import config


def test_stock_monitor():
    """测试个股监控器"""
    logger.setup(log_level='DEBUG')
    
    print("=" * 60)
    print("测试个股监控模块")
    print("=" * 60)
    
    # 初始化
    data_adapter = DataAdapter(cache_enabled=True)
    
    # 使用实际存在的板块名称（从 query_sector_names.py 查询结果）
    # 原来使用: ['电力设备', '通信', '计算机']
    # 实际存在: ['THY1电力设备', 'THY1通信', 'THY1计算机']
    top_sectors = ['THY1电力设备', 'THY1通信', 'THY1计算机']
    
    # 创建监控器
    monitor = StockMonitor(top_sectors, data_adapter)
    
    print(f"\n监控池大小: {len(monitor.monitor_pool)}")
    print(f"监控池: {monitor.monitor_pool[:10]}{'...' if len(monitor.monitor_pool) > 10 else ''}")
    
    # 订阅买入信号
    buy_signals = []
    
    def on_buy_signal(signal):
        buy_signals.append(signal)
        print(f"\n收到买入信号: {signal.data}")
    
    signal_bus.subscribe(SignalType.BUY, on_buy_signal)
    
    # 模拟监控（只运行一次轮询）
    print("\n开始监控（模拟一次轮询）...")
    
    # 获取实时行情
    realtime_batch = data_adapter.get_realtime_quote_batch(monitor.monitor_pool[:5])
    
    print(f"\n获取到 {len(realtime_batch)} 只股票的实时行情")
    for stock, data in list(realtime_batch.items())[:3]:
        print(f"  {stock}: 价格={data.get('last_price', 0):.2f}, "
              f"涨跌幅={data.get('change_rate', 0):.2f}%, "
              f"成交量={data.get('volume', 0)}")
    
    print(f"\n买入信号数量: {len(buy_signals)}")
    
    # 统计信息
    stats = data_adapter.get_stats()
    print(f"\n数据请求统计:")
    print(f"  请求次数: {stats['request_count']}")
    print(f"  缓存命中: {stats['cache_hit_count']}")
    print(f"  命中率: {stats['cache_hit_rate']*100:.2f}%")


if __name__ == '__main__':
    test_stock_monitor()
