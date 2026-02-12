"""
数据适配器测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from modules import DataAdapter
from utils import logger


def test_data_adapter():
    """测试数据适配器"""
    logger.setup(log_level='DEBUG')
    
    print("=" * 60)
    print("测试数据适配器")
    print("=" * 60)
    
    # 初始化
    adapter = DataAdapter(cache_enabled=True)
    
    # 1. 测试获取全市场股票列表
    print("\n1. 测试获取全市场股票列表")
    start = time.time()
    all_stocks = adapter.get_all_stocks()
    elapsed = time.time() - start
    print(f"   获取 {len(all_stocks)} 只股票，耗时: {elapsed:.3f} 秒")
    print(f"   示例: {all_stocks[:5]}")
    
    # 2. 测试获取板块列表
    print("\n2. 测试获取板块列表")
    start = time.time()
    sectors = adapter.get_sector_list()
    elapsed = time.time() - start
    print(f"   获取 {len(sectors)} 个板块，耗时: {elapsed:.3f} 秒")
    print(f"   示例: {sectors[:5]}")
    
    # 3. 测试获取板块内股票
    print("\n3. 测试获取板块内股票")
    if sectors:
        sector = sectors[0]
        start = time.time()
        stocks = adapter.get_stocks_in_sector(sector)
        elapsed = time.time() - start
        print(f"   板块 {sector} 有 {len(stocks)} 只股票，耗时: {elapsed:.3f} 秒")
        print(f"   示例: {stocks[:5]}")
    
    # 4. 测试批量请求行情数据
    print("\n4. 测试批量请求行情数据")
    test_stocks = all_stocks[:10]
    start = time.time()
    quote_data = adapter.get_market_data_batch(
        stocks=test_stocks,
        fields=['open', 'close', 'high', 'low', 'volume'],
        period='1d'
    )
    elapsed = time.time() - start
    print(f"   批量请求 {len(test_stocks)} 只股票，耗时: {elapsed:.3f} 秒")
    print(f"   获取到 {len(quote_data)} 只股票的数据")
    if quote_data:
        stock = list(quote_data.keys())[0]
        print(f"   示例 {stock}: {quote_data[stock]}")
    
    # 5. 测试批量请求实时行情（免费接口，不使用 L2）
    print("\n5. 测试批量请求实时行情")
    start = time.time()
    realtime_data = adapter.get_realtime_quote_batch(test_stocks)
    elapsed = time.time() - start
    print(f"   批量请求 {len(test_stocks)} 只股票的实时行情，耗时: {elapsed:.3f} 秒")
    print(f"   获取到 {len(realtime_data)} 只股票的数据")
    if realtime_data:
        stock = list(realtime_data.keys())[0]
        data = realtime_data[stock]
        print(f"   示例 {stock}:")
        print(f"     最新价: {data.get('last_price', 0):.2f}")
        print(f"     成交量: {data.get('volume', 0)}")
        print(f"     涨跌幅: {data.get('change_rate', 0):.2f}%")
        print(f"     振幅: {((data.get('high', 0) - data.get('low', 0)) / data.get('pre_close', 1) * 100):.2f}%")
    
    # 6. 测试缓存
    print("\n6. 测试缓存")
    print("   第二次请求相同数据（应该命中缓存）...")
    start = time.time()
    all_stocks_2 = adapter.get_all_stocks()
    elapsed = time.time() - start
    print(f"   耗时: {elapsed:.3f} 秒（应该接近 0）")
    
    # 统计信息
    stats = adapter.get_stats()
    print(f"\n数据请求统计:")
    print(f"  请求次数: {stats['request_count']}")
    print(f"  缓存命中: {stats['cache_hit_count']}")
    print(f"  缓存大小: {stats['cache_size']}")
    print(f"  命中率: {stats['cache_hit_rate']*100:.2f}%")


if __name__ == '__main__':
    test_data_adapter()
