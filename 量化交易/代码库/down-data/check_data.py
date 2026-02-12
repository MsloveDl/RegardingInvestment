from xtquant import xtdata
import pandas as pd
import sys

def check_stock_data(code, date_str, period='1d', start_time='', end_time=''):
    """
    通用检查函数
    code: 股票代码 (如 603360.SH)
    date_str: 日期 (如 20250710)
    period: 1d 或 1m
    """
    xtdata.enable_hello = False
    
    # 自动补全代码后缀
    if '.' not in code:
        if code.startswith('6') or code.startswith('5'):
            code += '.SH'
        else:
            code += '.SZ'
            
    print(f"--- 正在查询 {code} ({period}) ---")
    
    if period == '1d':
        xtdata.download_history_data(code, '1d', date_str, date_str)
        data = xtdata.get_market_data_ex([], [code], period='1d', start_time=date_str, end_time=date_str)
    else:
        xtdata.download_history_data(code, '1m', start_time, end_time)
        data = xtdata.get_market_data_ex([], [code], period='1m', start_time=start_time, end_time=end_time)
        
    if code in data and not data[code].empty:
        print(data[code])
    else:
        print(f"Error: 未找到 {code} 在指定时间段内的数据。")

def down_load_sector():
    client = xtdata.get_client()
    client.down_all_sector_data()

if __name__ == "__main__":
    # 示例用法
    # check_stock_data('002050.SZ', '20250710', '1d')
    # check_stock_data('002050.SZ', '', '1m', '20260210093000', '20260210093500')
    # down_load_sector()
    # sector_list = xtdata.get_sector_list()
    # print(sector_list)

    stocks_in_sector = xtdata.get_stock_list_in_sector("TDGN储能")
    print(stocks_in_sector)

    pass