
# Lot Sizes as of late 2023/2024 (Update as needed)
LOT_SIZES = {
    "NIFTY": 50,
    "BANKNIFTY": 15,  # Note: BankNifty lot size changed to 15 (check compatibility)
    "FINNIFTY": 40,
    "MIDCPNIFTY": 75,
    "RELIANCE": 250,
    "HDFCBANK": 550,
    "INFY": 400,
    "TCS": 175,
    "ICICIBANK": 700,
    "SBIN": 1500,
    "TATAMOTORS": 1425,
    "AXISBANK": 625,
    "KOTAKBANK": 400,
    "LT": 300,
    "BAJFINANCE": 125,
    "MARUTI": 100
}

def get_lot_size(symbol):
    # Normalize
    s = symbol.upper().replace("NSE:", "").replace("NIFTY 50", "NIFTY").replace("NIFTY BANK", "BANKNIFTY")
    return LOT_SIZES.get(s, 1) # Default to 1 if not found (Equity)
