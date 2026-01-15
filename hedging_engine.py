import margin_engine

def get_hedged_strategy(view, capital, margin, symbol, expiry_data, atm_strike):
    """
    Suggests a hedged strategy based on view and capital.
    Ideal for margin 20k-40k where naked selling is risky/impossible but Buying is too volatile.
    """
    
    strategy = {}
    
    # Vertical Spreads (Debit or Credit)
    # Low Capital/Margin -> Debit Spread (Buy ATM, Sell OTM) -> Reduces cost
    # Mid Capital -> Credit Spread (Sell OTM, Buy Further OTM) -> Income
    
    if view == "BULLISH":
        if margin > 25000:
            # Bull Put Spread (Credit) - Moderately Bullish
            # Sell PE (ATM/OTM), Buy PE (Lower Strike)
            strategy = {
                "name": "Bull Put Spread (Credit)",
                "legs": [
                    {"action": "SELL", "type": "PE", "strike": atm_strike, "quantity": 1}, # Sell ATM/OTM
                    {"action": "BUY", "type": "PE", "strike": atm_strike - 200, "quantity": 1} # Buy Hedge
                ],
                "reason": "Credit spread to benefit from sideways-to-up move."
            }
        else:
            # Bull Call Spread (Debit) - Directional
            # Buy CE (ATM), Sell CE (OTM)
            strategy = {
                "name": "Bull Call Spread (Debit)",
                "legs": [
                    {"action": "BUY", "type": "CE", "strike": atm_strike, "quantity": 1},
                    {"action": "SELL", "type": "CE", "strike": atm_strike + 200, "quantity": 1} # Reduce cost
                ],
                "reason": "Debit spread to reduce premium cost and theta decay."
            }
            
    elif view == "BEARISH":
        if margin > 25000:
            # Bear Call Spread (Credit)
            strategy = {
                "name": "Bear Call Spread (Credit)",
                "legs": [
                    {"action": "SELL", "type": "CE", "strike": atm_strike, "quantity": 1},
                    {"action": "BUY", "type": "CE", "strike": atm_strike + 200, "quantity": 1}
                ],
                "reason": "Credit spread to benefit from sideways-to-down move."
            }
        else:
            # Bear Put Spread (Debit)
            strategy = {
                "name": "Bear Put Spread (Debit)",
                "legs": [
                    {"action": "BUY", "type": "PE", "strike": atm_strike, "quantity": 1},
                    {"action": "SELL", "type": "PE", "strike": atm_strike - 200, "quantity": 1}
                ],
                "reason": "Debit spread to reduce premium cost."
            }
            
    else:
        # Sideways
        if margin > 40000:
             strategy = {
                "name": "Iron Condor",
                "legs": [
                    {"action": "SELL", "type": "CE", "strike": atm_strike + 100, "quantity": 1},
                    {"action": "BUY", "type": "CE", "strike": atm_strike + 300, "quantity": 1},
                    {"action": "SELL", "type": "PE", "strike": atm_strike - 100, "quantity": 1},
                    {"action": "BUY", "type": "PE", "strike": atm_strike - 300, "quantity": 1},
                ],
                "reason": "Non-directional strategy to eat theta."
            }
        else:
             strategy = {"name": "WAIT", "legs": [], "reason": "Sideways market, insufficient capital for Iron Condor."}
             
    return strategy
