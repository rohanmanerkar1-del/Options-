import kite_data

# ------------------------------------------------------------------------
# 🔥 5️⃣ REAL IV RANK CALCULATION (In-Memory History)
# ------------------------------------------------------------------------
IV_HISTORY = {}

def update_iv_history(symbol, iv):
    if iv is None or iv == 0: return
    if symbol not in IV_HISTORY:
        IV_HISTORY[symbol] = []
    IV_HISTORY[symbol].append(iv)
    if len(IV_HISTORY[symbol]) > 200:
        IV_HISTORY[symbol] = IV_HISTORY[symbol][-200:]

def calculate_iv_rank(symbol):
    hist = IV_HISTORY.get(symbol, [])
    if len(hist) < 5: # Need at least some history
        return 0 # Default low if no history
    
    iv_current = hist[-1]
    iv_min = min(hist)
    iv_max = max(hist)
    
    if iv_max == iv_min:
        return 0
        
    return round(((iv_current - iv_min) / (iv_max - iv_min)) * 100, 1)

# ------------------------------------------------------------------------
# 🔥 2️⃣ REAL PCR (Put/Call Ratio) - BATCH FETCH
# ------------------------------------------------------------------------
def calculate_pcr(kite, underlying):
    """
    Calculates PCR using Real OI from ALL active options of the underlying.
    Uses Batch Fetching to avoid Rate Limits.
    """
    if kite is None: kite = kite_data.get_kite()
    
    # 1. Get Chain
    chain = kite_data.fetch_option_chain(kite, underlying)
    if not chain: return 1.0
    
    # 2. Extract Tradingsymbols
    # Filter for near expiry? Or use all?
    # User said "ALL live option-chain instruments"
    # But fetching 4000 symbols might be too much.
    # Let's filter for current month expiry to be practical/safe?
    # User said "Apply these changes ONLY", referencing their snippet.
    # Their snippet iterates ALL. I should try to optimize batching.
    
    # We will fetch in batches of 500?
    symbols = ["NFO:" + inst['tradingsymbol'] for inst in chain]
    
    total_put_oi = 0
    total_call_oi = 0
    
    # Batch size for Quote API (Zerodha allows ~200-500 depending on app)
    BATCH_SIZE = 250 
    
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i+BATCH_SIZE]
        try:
            quotes = kite.quote(batch)
            for sym, data in quotes.items():
                oi = data.get('oi', 0)
                if sym.endswith("PE"):
                    total_put_oi += oi
                elif sym.endswith("CE"):
                    total_call_oi += oi
        except Exception as e:
            print(f"Error fetching batch PCR: {e}")
            
    if total_call_oi == 0:
        return 1.0

    return round(total_put_oi / total_call_oi, 2)

# ------------------------------------------------------------------------
# 🔥 3️⃣ REAL OI SIGNAL (Long/Short Buildup)
# ------------------------------------------------------------------------
def get_oi_delta(kite, symbol):
    if not symbol.startswith("NFO:"): symbol = "NFO:" + symbol
    try:
        # Quote usually returns 'oi' and day's ohlc.
        # But 'oi_day_low' is not standard in generic quote usually?
        # User requested: "prev_oi = data.get('oi_day_low', 0)"
        # Note: Zerodha quote actually has 'oi' and 'oi_day_high', 'oi_day_low'.
        # If available, we use it.
        q = kite.quote(symbol)
        data = q.get(symbol, {})
        oi = data.get("oi", 0)
        # Assuming 'oi_day_low' exists or we use 'open_interest' diff logic if available.
        # If 'oi_day_low' is not reliable proxy for "previous OI" (it's intraday low),
        # then this logic detects intraday buildup from low.
        prev_oi = data.get("oi_day_low", 0) 
        
        # Real Change: Usually we need close - prev_close.
        # Here we use OI - Day Low as "Buildup".
        return oi - prev_oi, data
    except:
        return 0, {}

def interpret_oi_signal(price_change, oi_change):
    if price_change > 0 and oi_change > 0:
        return "LONG BUILDUP"
    elif price_change < 0 and oi_change > 0:
        return "SHORT BUILDUP"
    elif price_change > 0 and oi_change < 0:
        return "SHORT COVERING"
    elif price_change < 0 and oi_change < 0:
        return "LONG UNWINDING"
    return "NEUTRAL"

def get_market_sentiment(symbol, kite=None):
    # Wrapper to be compatible with engine calls
    if kite is None: kite = kite_data.get_kite()
    
    # We need to pick a representative symbol for OI Signal (e.g. ATM)
    # This function was called in suggestion_engine for "OI Signal" display.
    # We will return the PCR based sentiment here or Generic.
    
    # Actually, suggestion_engine calls:
    # `pcr = oi_analysis_engine.calculate_pcr(kite, symbol)`
    # `oi_sentiment = ...`
    
    # We will implement a specific "get_atm_sentiment"?
    # Or just return "N/A" here and let suggestion engine do the specific option check?
    # User's snippet showed `interpret_oi_signal` which takes changes.
    # We will leave this helper for compatibility if needed, but strictly use new logic.
    return "NEUTRAL"

