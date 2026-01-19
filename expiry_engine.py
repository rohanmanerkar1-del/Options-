import datetime
import calendar

# Holidays (Simplified List)
HOLIDAYS_2024 = [
    "2024-01-26", "2024-03-08", "2024-03-25", "2024-04-11",
    "2024-04-17", "2024-05-01", "2024-06-17", "2024-07-17",
    "2024-08-15", "2024-10-02", "2024-11-01", "2024-11-15", "2024-12-25"
]

def is_holiday(date_obj):
    fmt = date_obj.strftime("%Y-%m-%d")
    return fmt in HOLIDAYS_2024

def get_monthly_expiry(from_date=None):
    if from_date is None: from_date = datetime.datetime.now().date()
    
    # Get this month's last Thursday
    year = from_date.year
    month = from_date.month
    
    cal = calendar.monthcalendar(year, month)
    last_week = cal[-1]
    day = last_week[calendar.THURSDAY]
    if day == 0:
        day = cal[-2][calendar.THURSDAY]
        
    expiry = datetime.date(year, month, day)
    
    # If today is past expiry, get next month
    if from_date > expiry:
        month += 1
        if month > 12:
            month = 1
            year += 1
            
        cal = calendar.monthcalendar(year, month)
        last_week = cal[-1]
        day = last_week[calendar.THURSDAY]
        if day == 0:
            day = cal[-2][calendar.THURSDAY]
        expiry = datetime.date(year, month, day)
            
    # Handle Holiday
    while is_holiday(expiry):
        expiry -= datetime.timedelta(days=1)
        
    return expiry

def get_option_symbol(underlying, expiry_date, strike, otype):
    """
    --- 3. FIX EXPIRY FORMAT FOR ZERODHA ---
    Format: <UNDERLYING><YY><MON><STRIKE><CE/PE>
    """
    # Force Underlying Name Standard (NIFTY 50 -> NIFTY)
    # Force Underlying Name Standard (NIFTY 50 -> NIFTY)
    if underlying == "NIFTY 50" or underlying == "NIFTY":
         underlying = "NIFTY"
    elif underlying == "NIFTY BANK" or underlying == "BANKNIFTY":
         underlying = "BANKNIFTY"
    elif underlying == "NIFTY FIN SERVICE" or underlying == "FINNIFTY":
         underlying = "FINNIFTY"
    
    year = expiry_date.strftime("%y")             # -> "24"
    month = expiry_date.strftime("%b").upper()    # -> "JAN"
    
    tradingsymbol = f"{underlying}{year}{month}{strike}{otype}"
    return tradingsymbol

def get_expiry(symbol, from_date=None, use_weekly=False):
    # Always return Monthly for now as it ensures the strict format works safely
    # The strict format user requested is typically implied for monthly or specific weekly codes
    # User said "Correct Zerodha option format is <UNDERLYING><YY><MON><STRIKE><CE/PE>"
    
    expiry_date = get_monthly_expiry(from_date)
    return {
        "date": expiry_date,
        "code_monthly": "UNUSED", # Legacy key
        "code": "UNUSED" 
    }
