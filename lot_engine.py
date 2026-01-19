# Lot Sizes logic updated to fetch properly from Zerodha
import kite_data

# Fallback Lot Sizes (only used if API fetch fails)
FALLBACK_LOT_SIZES = {
    "NIFTY": 50,
    "BANKNIFTY": 15,
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
    # Normalize inputs like "Nifty Bank", "NIFTY 50" to "BANKNIFTY", "NIFTY"
    s = symbol.upper().replace("NSE:", "").replace("NIFTY 50", "NIFTY").replace("NIFTY BANK", "BANKNIFTY")
    
    # 1. Try to get dynamic lot size from kite_data (populated at startup)
    dynamic_lot = kite_data.get_cached_lot_size(s)
    if dynamic_lot:
        return dynamic_lot
        
    # 2. If not found (maybe kite not loaded yet?), force load/check
    # Note: ensure_tokens_loaded calls load_option_tokens which populates the cache
    if kite_data.get_kite(): 
        kite_data.ensure_tokens_loaded(kite_data.get_kite())
        dynamic_lot = kite_data.get_cached_lot_size(s)
        if dynamic_lot:
            return dynamic_lot

    # 3. Fallback
    print(f"[!] Warning: Using fallback lot size for {s}")
    return FALLBACK_LOT_SIZES.get(s, 1) # Default to 1 if not found (Equity)
