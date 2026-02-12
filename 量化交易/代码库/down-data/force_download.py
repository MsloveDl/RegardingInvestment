import time
import sys
from datetime import datetime
from xtquant import xtdata
import pandas as pd
import logging

# Setup logging
log_file = 'download_process.log'
logging.basicConfig(filename=log_file, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_and_print(msg):
    print(msg)
    logging.info(msg)
    sys.stdout.flush()

def validate_data(stock, period, start_time):
    try:
        data = xtdata.get_market_data(field_list=['close'], stock_list=[stock], period=period, start_time=start_time, count=1)
        if stock in data and not data[stock].empty:
            return True
    except:
        pass
    return False

log_and_print("--- Force Download Session (Skipping Sector Sync) ---")
try:
    xtdata.enable_hello = False
    stocks = xtdata.get_stock_list_in_sector('沪深A股')
    
    if not stocks:
        log_and_print("Critical: Could not fetch stock list. Exiting.")
        sys.exit(1)

    log_and_print(f"Targeting {len(stocks)} stocks.")
    results = []
    
    for i in range(0, len(stocks), 10):
        batch = stocks[i:i+10]
        log_and_print(f"[{i//10 + 1}] Downloading: {batch}")
        
        # Trigger downloads for the batch
        for stock in batch:
            try:
                xtdata.download_history_data(stock, period='1d', start_time='20240101')
                xtdata.download_history_data(stock, period='1m', start_time='20260101')
            except Exception as e:
                log_and_print(f"Trigger Error {stock}: {e}")

        # Small wait for requests to hit the server before validating
        time.sleep(2)
        
        # Validate and record
        for stock in batch:
            ok_1d = validate_data(stock, '1d', '20240101')
            ok_1m = validate_data(stock, '1m', '20260101')
            
            detail = xtdata.get_instrument_detail(stock)
            name = detail.get('InstrumentName', stock)
            
            status = "Success" if (ok_1d and ok_1m) else "Partial"
            results.append({'code': stock, 'name': name, 'status': status, '1d': ok_1d, '1m': ok_1m})

        # Save CSV progress
        pd.DataFrame(results).to_csv('out.csv', index=False, encoding='utf-8-sig')
        
        # Batch pause as requested
        log_and_print("Batch done. Sleeping 5s...")
        time.sleep(5)

    log_and_print("--- All Downloads Finished ---")

except Exception as e:
    log_and_print(f"GLOBAL ERROR: {e}")
