from xtquant import xtdata
from multiprocessing import Process
import time

def sync_batch(stock_group, periods):
    xtdata.enable_hello = False
    for stock_code in stock_group:
        for period in periods:
            try:
                xtdata.download_history_data(stock_code=stock_code, period=period, incrementally=True)
            except:
                pass

def main():
    xtdata.enable_hello = False
    print("Step 1: Syncing sectors...")
    client = xtdata.get_client()
    client.down_all_sector_data()
    
    stocks = xtdata.get_stock_list_in_sector('沪深A股')
    bj_stocks = xtdata.get_stock_list_in_sector('BJ')
    all_stocks = list(set(stocks + bj_stocks))
    print(f"Total stocks: {len(all_stocks)}")
    
    periods = ['1d', '1m']
    group_size = 500
    processes = []
    
    for i in range(0, len(all_stocks), group_size):
        group = all_stocks[i : i + group_size]
        p = Process(target=sync_batch, args=(group, periods))
        p.start()
        processes.append(p)
    
    print(f"Started {len(processes)} sync processes.")
    for p in processes:
        p.join()
    print("All sync tasks completed.")

if __name__ == '__main__':
    main()
