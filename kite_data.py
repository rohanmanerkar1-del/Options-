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

def load_option_tokens(kite):
    tokens = {}
    print("[*] Loading Option Tokens... (This may take a moment)")
    try:
        # Fetch detailed instrument list for NFO
        instruments = kite.instruments("NFO")
        for inst in instruments:
            tokens[inst["tradingsymbol"]] = inst["instrument_token"]
        print(f"[*] Loaded {len(tokens)} Option Tokens.")
    except Exception as e:
        print(f"[!] Error loading tokens: {e}")
    return tokens

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
    
    if "NFO:" in symbol: # Only check tokens for NFO symbols
        if tradingsymbol not in OPTION_TOKENS:
            print(f"Token not found: {tradingsymbol}")
            return None

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
        return data.get("iv", None)
    except:
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
    except Exception as e:
        # print(f"Error validating liquidity: {e}")
        return False
