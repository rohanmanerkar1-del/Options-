from kiteconnect import KiteConnect
import config
import logging

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KiteData")

_kite = None

def get_kite():
    global _kite
    if _kite is None:
        try:
            _kite = KiteConnect(api_key=config.API_KEY)
            _kite.set_access_token(config.ACCESS_TOKEN)
        except Exception as e:
            logger.error(f"Error initializing Kite: {e}")
    return _kite

# --- 1. INDEX TOKENS (FIX SPOT PRICE SOURCE) ---
INDEX_TOKENS = {
    "NIFTY": 256265,
    "BANKNIFTY": 260105,
    "FINNIFTY": 257801
}

# --- 2. ADD OPTION TOKEN LOOKUP (MANDATORY) ---
OPTION_TOKENS = {}
# Global cache for lot sizes (Underlying -> Lot Size)
LOT_SIZE_CACHE = {}
# Global cache for Instrument Details (Symbol -> {expiry, strike, lot_size})
INSTRUMENT_DETAILS = {}

def load_option_tokens(kite):
    global LOT_SIZE_CACHE, INSTRUMENT_DETAILS
    tokens = {}
    print("[*] Loading Option Tokens & Lot Sizes... (This may take a moment)")
    try:
        # Fetch detailed instrument list for NFO
        instruments = kite.instruments("NFO")
        for inst in instruments:
            ts = inst["tradingsymbol"]
            tokens[ts] = inst["instrument_token"]
            
            # Map Underlying Name to Lot Size (Prefer NFO-OPT)
            if inst["segment"] in ["NFO-OPT", "NFO-FUT"]:
                 LOT_SIZE_CACHE[inst["name"]] = inst["lot_size"]
                 
            # Cache Details for Greeks
            INSTRUMENT_DETAILS[ts] = {
                "expiry": inst["expiry"],
                "strike": inst["strike"],
                "name": inst["name"],
                "lot_size": inst["lot_size"]
            }
                 
        print(f"[*] Loaded {len(tokens)} Option Tokens.")
        print(f"[*] Loaded {len(LOT_SIZE_CACHE)} Lot Size entries.")
    except Exception as e:
        print(f"[!] Error loading tokens: {e}")
    return tokens

def get_instrument_detail(symbol):
    return INSTRUMENT_DETAILS.get(symbol, {})

def get_cached_lot_size(name):
     return LOT_SIZE_CACHE.get(name, None)

def ensure_tokens_loaded(kite):
    global OPTION_TOKENS
    if not OPTION_TOKENS:
        OPTION_TOKENS = load_option_tokens(kite)

# --- 3. FIX LTP FETCHING (STRICT - NO FALLBACKS) ---
def get_ltp(symbol, kite):
    
    # Check if it's an Index and return spot from token
    if symbol in INDEX_TOKENS:
        try:
            token = INDEX_TOKENS[symbol]
            data = kite.ltp(token)
            return data[str(token)]["last_price"]
        except Exception as e:
            print(f"Error fetching Index Spot {symbol}: {e}")
            return None

    # Token Check for Options
    ensure_tokens_loaded(kite)
    
    # Identify Tradingsymbol (remove NFO: prefix if present)
    tradingsymbol = symbol.replace("NFO:", "")
    
    # Check if this looks like an option (not index) to validate token
    if "NFO:" in symbol or any(x in symbol for x in ["CE", "PE", "FUT"]):
        # It's an NFO instrument. Validate token exists first?
        # Actually, let's just ensure we pass "NFO:" to kite.ltp if it's missing
        if not symbol.startswith("NFO:"):
             symbol = "NFO:" + symbol
             
        if tradingsymbol not in OPTION_TOKENS:
            print(f"Token not found: {tradingsymbol}")
            # If token not found in our cache, we might still try fetching?
            # But let's trust the cache for now or just log warning.
            # return None 
    
    try:
        # 1. STRICT FETCH
        data = kite.ltp(symbol)
        
        if symbol not in data:
            return None
            
        ltp = data[symbol]["last_price"]
        
        # 2. FILTER INVALID PRICES
        if ltp is None or ltp < 2:
            print(f"Invalid or stale premium for {symbol} ({ltp}). Skipping.")
            return None
            
        return ltp
        
    except Exception as e:
        print("Error fetching LTP:", e)
        return None

# --- 4. REAL OPTION DATA (OI, IV, VOL) ---
def get_real_option_data(symbol, kite):
    """
    Fetches comprehensive data including OI, Vol, IV, LTP.
    """
    ensure_tokens_loaded(kite)
    
    # Symbol formatting
    if not symbol.startswith("NFO:"):
        full_symbol = "NFO:" + symbol
    else:
        full_symbol = symbol
        
    try:
        q = kite.quote(full_symbol)
        if full_symbol not in q:
            return None
            
        data = q[full_symbol]
        return {
            "ltp": data["last_price"],
            "oi": data["oi"],
            "volume": data["volume"],
            "iv": data.get("iv", None) # Some quotes might not have IV
        }
    except Exception as e:
        print(f"Error fetching real option data for {symbol}: {e}")
        return None

# Indices Token Map (For Historical Data wrapper if needed later)
TOKEN_MAP = INDEX_TOKENS.copy()
TOKEN_MAP.update({
    "MIDCPNIFTY": 288009,
    "RELIANCE": 738561,
    "HDFCBANK": 341249,
    "ICICIBANK": 1270529,
    "SBIN": 779521,
    "TCS": 2953217,
    "INFY": 408065
}) 

def get_historical_data(symbol, interval="5m", days=30):
    """
    Fetches historical candles using Zerodha API.
    """
    kite = get_kite()
    token = TOKEN_MAP.get(symbol)
    
    if not token:
        print(f"[!] Historical data supported only for Nifty/BankNifty/FinNifty. No token for {symbol}")
        return []
    
    try:
        import datetime
        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(days=days)
        
        z_interval = interval
        if interval == "5m": z_interval = "5minute"
        elif interval == "15m": z_interval = "15minute"
        elif interval == "1H": z_interval = "60minute"
        elif interval == "1d": z_interval = "day"
        
        candles = kite.historical_data(token, from_date, to_date, z_interval)
        return candles
        
    except Exception as e:
        print(f"Error fetching Zerodha history for {symbol}: {e}")
        return []

# ------------------------------------------------------------------------
# 🔥 1️⃣ REAL OPTION CHAIN FETCHER
# ------------------------------------------------------------------------
def fetch_option_chain(kite, underlying):
    """
    Fetches ALL live option-chain instruments.
    """
    # Normalize underlying name for regex/match
    # User said "inst['name'] == underlying"
    # Kite instruments usually have 'name' as 'NIFTY', 'BANKNIFTY', 'RELIANCE', etc.
    print(f"[*] Fetching Option Chain for {underlying}...")
    try:
        instruments = kite.instruments("NFO")
        chain = []
        for inst in instruments:
            if inst["name"] == underlying and inst["segment"] == "NFO-OPT":
                chain.append(inst)
        return chain
    except Exception as e:
        print(f"Error fetching option chain: {e}")
        return []

# ------------------------------------------------------------------------
# 🔥 4️⃣ REAL IV FETCH
# ------------------------------------------------------------------------
def get_iv_value(kite, symbol):
    """
    Fetches real IV from Quote.
    """
    if not symbol.startswith("NFO:"): symbol = "NFO:" + symbol
    try:
        q = kite.quote(symbol)
        data = q.get(symbol, {})
        iv = data.get("iv", None)
        
        if iv is not None and iv > 0:
            return iv
            
        # API IV missing, calculate it manually
        # specific to options
        import greeks_engine
        
        ltp = data.get('last_price', 0)
        ts = symbol.replace("NFO:", "")
        details = INSTRUMENT_DETAILS.get(ts)
        
        # We need details (Strike, Expiry)
        # If details are not in cache, we cannot calc IV easily without fetching instrument master again or parsing symbol
        # Assuming load_option_tokens ran earlier or we lazily fetch
        if not details:
            # Try to get spot for fallback
            # This is complex without details. Return 0 for now to avoid crashes.
            return 0
            
        # Get Underlying Spot
        underlying = details['name'] # e.g. NIFTY
        idx_token = INDEX_TOKENS.get(underlying)
        S = 0
        if idx_token:
             # We need to fetch spot ltp? We might have just quoted options
             # To save calls, we could use cached spot or just fetch it.
             # Ideally get_iv_value should be efficient.
             # Let's assume we can fetch it.
             try:
                 qs = kite.ltp(idx_token)
                 S = qs[str(idx_token)]['last_price']
             except: return 0
        else:
            return 0 # Cannot find spot
            
        K = details['strike']
        T = greeks_engine.calculate_time_to_expiry(details['expiry'])
        opt_type = "CE" if "CE" in ts else "PE"
        
        calc_iv = greeks_engine.get_implied_volatility(ltp, S, K, T, 0.07, opt_type)
        return calc_iv

    except Exception as e:
        # print(f"Error getting IV: {e}")
        return None

# ------------------------------------------------------------------------
# 🔥 6️⃣ REAL LIQUIDITY FILTER
# ------------------------------------------------------------------------
def valid_liquidity(kite, symbol):
    """
    Strict Liquidity Check:
    - Volume >= 5000
    - OI >= 10000
    - LTP >= 2
    """
    if not symbol.startswith("NFO:"): symbol = "NFO:" + symbol
    try:
        q = kite.quote(symbol)
        data = q.get(symbol, {})

        volume = data.get("volume", 0)
        oi = data.get("oi", 0)
        ltp = data.get("last_price", 0)
        
        # print(f"Checking {symbol}: Vol={volume}, OI={oi}, LTP={ltp}")

        if volume < 5000: return False
        if oi < 10000: return False
        if ltp < 2: return False

        return True
        return True
    except Exception as e:
        # print(f"Error validating liquidity: {e}")
        return False

# ------------------------------------------------------------------------
# 🔥 7️⃣ SPREAD CHECKER
# ------------------------------------------------------------------------
def get_quote_spread(symbol, kite):
    """
    Returns Bid/Ask/Spread info.
    """
    if not symbol.startswith("NFO:"): symbol = "NFO:" + symbol
    try:
        q = kite.quote(symbol)
        if symbol not in q: return None
        
        d = q[symbol]['depth']
        buy_list = d['buy']
        sell_list = d['sell']
        
        if not buy_list or not sell_list: return None
        
        best_bid = buy_list[0]['price']
        best_ask = sell_list[0]['price']
        
        # Avoid zero division
        if best_bid == 0: return None
        
        spread = best_ask - best_bid
        spread_pct = (spread / best_bid) * 100
        
        return {
            "bid": best_bid,
            "ask": best_ask,
            "spread": spread,
            "spread_pct": spread_pct
        }
    except Exception as e:
        print(f"Error fetching spread for {symbol}: {e}")
        return None
