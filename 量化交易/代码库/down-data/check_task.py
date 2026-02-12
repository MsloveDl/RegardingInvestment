import time
import sys
import os
from datetime import datetime
from xtquant import xtdata
import pandas as pd
import logging

# Setup logging
log_file = 'check_data.log'
logging.basicConfig(filename=log_file, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_and_print(msg):
    print(msg)
    logging.info(msg)
    sys.stdout.flush()

def check_stock_data(stock):
    res = {'1d': False, '1m': False, '1d_count': 0, '1m_count': 0}
    try:
        # Check 1d
        d1d = xtdata.get_market_data(['close'], [stock], '1d', start_time='20240101')
        if stock in d1d['close'] and not d1d['close'].empty:
            res['1d'] = True
            res['1d_count'] = d1d['close'].columns.size
            
        # Check 1m
        d1m = xtdata.get_market_data(['close'], [stock], '1m', start_time='20260101')
        if stock in d1m['close'] and not d1m['close'].empty:
            res['1m'] = True
            res['1m_count'] = d1m['close'].columns.size
    except:
        pass
    return res

log_and_print("--- Market Data Validation Started (Fix: added os) ---")

try:
    xtdata.enable_hello = False
    if os.path.exists('out.csv'):
        df_old = pd.read_csv('out.csv')
        stocks = df_old['code'].tolist()
        # Clean potential encoding issues or duplicates
        stocks = list(dict.fromkeys(stocks)) 
        stock_names = dict(zip(df_old['code'], df_old['name']))
    else:
        stocks = xtdata.get_stock_list_in_sector('沪深A股')
        stock_names = {}

    log_and_print(f"Total stocks to validate: {len(stocks)}")
    
    results = []
    start_all = time.time()

    for i, stock in enumerate(stocks):
        if i % 100 == 0 and i > 0:
            elapsed = time.time() - start_all
            log_and_print(f"Progress: {i}/{len(stocks)} validated. Elapsed: {elapsed:.1f}s")

        check_res = check_stock_data(stock)
        name = stock_names.get(stock)
        if not name or name == "Unknown":
            detail = xtdata.get_instrument_detail(stock)
            name = detail.get('InstrumentName', stock)

        status = "Success" if (check_res['1d'] and check_res['1m']) else ("Partial" if (check_res['1d'] or check_res['1m']) else "Missing")
        
        results.append({
            'code': stock,
            'name': name,
            'status': status,
            'ok_1d': check_res['1d'],
            'ok_1m': check_res['1m'],
            'count_1d': check_res['1d_count'],
            'count_1m': check_res['1m_count']
        })

    df_new = pd.DataFrame(results)
    df_new.to_csv('out.csv', index=False, encoding='utf-8-sig')
    
    log_and_print(f"--- Validation Finished. Final out.csv saved. Total time: {time.time()-start_all:.1f}s ---")
    log_and_print(f"Summary: {df_new['status'].value_counts().to_dict()}")

except Exception as e:
    log_and_print(f"CRITICAL ERROR: {e}")
