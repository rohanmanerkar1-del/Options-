import csv
import os
import datetime

JOURNAL_FILE = "trade_journal.csv"

def log_trade(symbol, strike, expiry_type, entry, exit_price, pnl, reason, exit_reason):
    """
    Logs trade details to a CSV file.
    """
    file_exists = os.path.isfile(JOURNAL_FILE)
    
    with open(JOURNAL_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        
        # Header if new
        if not file_exists:
            writer.writerow(["Timestamp", "Symbol", "Strike", "ExpiryType", "Entry", "Exit", "PnL", "EntryReason", "ExitReason"])
            
        writer.writerow([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            symbol,
            strike,
            expiry_type,
            round(entry, 2),
            round(exit_price, 2),
            round(pnl, 2),
            reason,
            exit_reason
        ])
    
    print(f"[Journal] Trade saved to {JOURNAL_FILE}")
