import time
from xtquant import xtdata
import sys

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
    sys.stdout.flush()

log("Verification Script Started")
log("Attempting xtdata.download_sector_data()...")

start_time = time.time()
try:
    # Set a timeout-like behavior using a separate thread if we really wanted to, 
    # but let's just see if it finishes.
    xtdata.download_sector_data()
    end_time = time.time()
    log(f"SUCCESS: download_sector_data() finished in {end_time - start_time:.2f} seconds.")
    
    sectors = xtdata.get_sector_list()
    log(f"Verification: Found {len(sectors)} sectors.")
    
except Exception as e:
    log(f"FAILED: {e}")

log("Verification Script Ended")
