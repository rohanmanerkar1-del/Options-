def get_user_profile():
    """
    Returns the user's trading profile and risk settings.
    You can modify these return values to change the bot's behavior.
    """
    return {
        # Risk Level: "low", "medium", "high"
        # Affects Stoploss and Target width.
        "risk_level": "medium",

        # Trading Style: "scalper", "intraday", "swing", "positional"
        # Affects timeframes and strictness of exits (logic to be implemented).
        "trading_style": "intraday",

        # Capital Allocation: Percentage of total capital to use per trade.
        # e.g., 0.50 means use 50% of available capital.
        "capital_allocation": 0.50 
    }
