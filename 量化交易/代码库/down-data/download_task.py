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
    except Exception as e:
        logging.error(f"Validation error for {stock} ({period}): {e}")
    return False

log_and_print("--- New Download Session ---")
try:
    # 1. Get stock list
    log_and_print("Downloading sector data...")
    # Try a faster way to get stock list if this hangs
    # stocks = xtdata.get_stock_list_in_sector('沪深A股')
    # If it hangs, we might need to use get_client() or similar
    
    # Let's try to get the list without a full download if possible, or just download it
    xtdata.download_sector_data()
    stocks = xtdata.get_stock_list_in_sector('沪深A股')
    
    if not stocks:
        log_and_print("Error: No stocks found in '沪深A股'")
        sys.exit(1)

    results = []
    today = datetime.now().strftime('%Y%m%d')
    
    log_and_print(f"Total stocks to process: {len(stocks)}")

    for i in range(0, len(stocks), 10):
        batch = stocks[i:i+10]
        log_and_print(f"Batch {i//10 + 1}: Downloading {batch}")
        
        for stock in batch:
            try:
                # 1d (20240101 ~)
                xtdata.download_history_data(stock, period='1d', start_time='20240101')
                # 1m (20260101 ~)
                xtdata.download_history_data(stock, period='1m', start_time='20260101')
                
                # Validation
                ok_1d = validate_data(stock, '1d', '20240101')
                ok_1m = validate_data(stock, '1m', '20260101')
                
                detail = xtdata.get_instrument_detail(stock)
                name = detail.get('InstrumentName', stock)
                
                status = "Success" if (ok_1d and ok_1m) else "Partial"
                results.append({'code': stock, 'name': name, 'status': status, '1d': ok_1d, '1m': ok_1m})
                
                # Periodically save CSV in case of crash
                if len(results) % 50 == 0:
                    pd.DataFrame(results).to_csv('out.csv', index=False, encoding='utf-8-sig')
            
            except Exception as e:
                log_and_print(f"Error {stock}: {e}")
                results.append({'code': stock, 'name': 'Error', 'status': 'Failed', '1d': False, '1m': False})
        
        if i + 10 < len(stocks):
            time.sleep(5)

    pd.DataFrame(results).to_csv('out.csv', index=False, encoding='utf-8-sig')
    log_and_print("Task Finished Successfully.")

except Exception as e:
    log_and_print(f"CRITICAL ERROR: {e}")
