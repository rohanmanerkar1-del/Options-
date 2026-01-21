import datetime
import trade_journal

def get_float(prompt):
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("Invalid number. Please try again.")

def main():
    print("\n--- MANUAL TRADE LOGGER ---")
    print("Record your trade details below.\n")

    try:
        symbol = input("Symbol (e.g. NIFTY26JAN...): ").strip().upper()
        if not symbol:
            print("Symbol is required!")
            return

        trade_type = input("Type (BUY/SELL) [BUY]: ").strip().upper()
        if not trade_type: trade_type = "BUY"

        entry_price = get_float("Entry Price: ")
        exit_price = get_float("Exit Price: ")
        
        # Auto-calc PnL/Qty if user wants, or just manual PnL
        # Let's keep it simple: Entry/Exit + Quantity to calc PnL, or just raw PnL?
        # User said "2.5k profit", likely aggregate. Let's ask for Total PnL directly.
        
        calc_mode = input("Calculate PnL from Qty? (y/n) [n]: ").lower()
        
        pnl = 0.0
        if calc_mode == 'y':
            qty = get_float("Quantity: ")
            if trade_type == "BUY":
                pnl = (exit_price - entry_price) * qty
            else:
                pnl = (entry_price - exit_price) * qty
            print(f"-> Calculated PnL: {pnl:.2f}")
        else:
            pnl = get_float("Total PnL (Negative for loss): ")

        reason = input("Entry Reason (Optional): ")
        exit_reason = input("Exit Reason (e.g. Target/SL): ")
        
        if not reason: reason = "Manual Entry"
        if not exit_reason: exit_reason = "Manual Exit"

        # Log to file
        # Check trade_journal signature: 
        # log_trade(symbol, strike, expiry_type, entry, exit_price, pnl, reason, exit_reason)
        # We might need to fake strike/expiry_type if we don't parse the symbol. 
        # Let's just pass placeholders or parse if easy.
        
        strike = "N/A"
        expiry = "N/A"
        
        trade_journal.log_trade(
            symbol=symbol, 
            strike=strike, 
            expiry_type=expiry, 
            entry=entry_price, 
            exit_price=exit_price, 
            pnl=pnl, 
            reason=reason, 
            exit_reason=exit_reason,
            regime="Manual",
            strategy="Manual",
            dte="Manual",
            confidence="Manual"
        )
        
        print("\n[+] Trade Successfully Logged!")
        
    except KeyboardInterrupt:
        print("\nExited.")

if __name__ == "__main__":
    main()
