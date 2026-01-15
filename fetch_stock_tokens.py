import kite_data

def fetch_tokens():
    kite = kite_data.get_kite()
    print("Fetching NSE instruments...")
    instruments = kite.instruments("NSE")
    
    targets = ["RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "TCS", "INFY"]
    found = {}
    
    for inst in instruments:
        if inst['tradingsymbol'] in targets:
            found[inst['tradingsymbol']] = inst['instrument_token']
            
    for sym, token in found.items():
        print(f"{sym}:{token}")

if __name__ == "__main__":
    fetch_tokens()
