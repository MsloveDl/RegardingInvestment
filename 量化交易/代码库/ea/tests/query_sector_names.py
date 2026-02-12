"""
查询 xtquant 实际的板块名称
用于修复板块名称不匹配问题
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from xtquant import xtdata
    XTDATA_AVAILABLE = True
except ImportError:
    XTDATA_AVAILABLE = False
    print("警告: xtquant 未安装")
    sys.exit(1)

from utils.logger import logger

def query_sector_names():
    """查询板块名称"""
    logger.setup(log_level='INFO')
    
    print("=" * 60)
    print("查询 xtquant 板块名称")
    print("=" * 60)
    
    # 获取所有板块
    sectors = xtdata.get_sector_list()
    print(f"\n共 {len(sectors)} 个板块\n")
    
    # 查找包含特定关键词的板块
    keywords = ['电力', '通信', '计算机', '电子', '医药', '申万', '行业']
    
    for keyword in keywords:
        matching = [s for s in sectors if keyword in s]
        if matching:
            print(f"\n包含 '{keyword}' 的板块 ({len(matching)} 个):")
            for sector in matching[:10]:  # 只显示前10个
                stocks = xtdata.get_stock_list_in_sector(sector)
                print(f"  - {sector}: {len(stocks)} 只股票")
    
    # 显示前50个板块
    print(f"\n前50个板块:")
    for i, sector in enumerate(sectors[:50], 1):
        stocks = xtdata.get_stock_list_in_sector(sector)
        print(f"{i:2d}. {sector}: {len(stocks)} 只股票")

if __name__ == '__main__':
    query_sector_names()
