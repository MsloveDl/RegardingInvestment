import time
from xtquant import xtdata
import sys

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

log("--- Live Connection & Data Verification ---")

# 1. Connection Check
try:
    client = xtdata.get_client()
    log("Successfully got xtdata client.")
except Exception as e:
    log(f"Failed to get client: {e}")

# 2. Sector Check
try:
    sectors = xtdata.get_sector_list()
    log(f"Current local sectors count: {len(sectors)}")
    if '沪深A股' in sectors:
        stocks = xtdata.get_stock_list_in_sector('沪深A股')
        log(f"'沪深A股' exists, contains {len(stocks)} stocks.")
        if stocks:
            log(f"Sample stocks: {stocks[:5]}")
    else:
        log("'沪深A股' sector not found yet.")
except Exception as e:
    log(f"Error checking sectors: {e}")

# 3. Data Fetch Test (Non-blocking)
test_stock = '000001.SZ'
log(f"Testing non-blocking data fetch for {test_stock}...")
try:
    # Attempt to get very recent data (should be fast if cached)
    data = xtdata.get_market_data(field_list=['close'], stock_list=[test_stock], period='1d', count=1)
    if test_stock in data and not data[test_stock].empty:
        last_price = data[test_stock]['close'].iloc[-1]
        log(f"SUCCESS: Fetched last close for {test_stock}: {last_price}")
    else:
        log(f"INFO: No local data found for {test_stock} yet, but query executed.")
except Exception as e:
    log(f"Data fetch test failed: {e}")

log("--- Verification Complete ---")
