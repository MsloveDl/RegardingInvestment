"""
板块扫描模块测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import DataAdapter, SectorScanner
from utils import logger
import config


def test_sector_scanner():
    """测试板块扫描器"""
    logger.setup(log_level='DEBUG')
    
    print("=" * 60)
    print("测试板块扫描模块")
    print("=" * 60)
    
    # 初始化
    data_adapter = DataAdapter(cache_enabled=True)
    scanner = SectorScanner(data_adapter)
    
    # 执行扫描
    top_sectors = scanner.scan_at_925()
    
    print("\n扫描结果:")
    print(f"目标板块: {top_sectors}")
    
    # 获取详细结果
    result = scanner.get_last_scan_result()
    if result:
        print(f"\n板块评分:")
        for sector, score in sorted(result['sector_ss'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {sector}: {score:.2f}")
    
    # 统计信息
    stats = data_adapter.get_stats()
    print(f"\n数据请求统计:")
    print(f"  请求次数: {stats['request_count']}")
    print(f"  缓存命中: {stats['cache_hit_count']}")
    print(f"  缓存大小: {stats['cache_size']}")
    print(f"  命中率: {stats['cache_hit_rate']*100:.2f}%")


if __name__ == '__main__':
    test_sector_scanner()
