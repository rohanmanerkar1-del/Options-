import numpy as np
from scipy.stats import norm
import datetime

# Market Constants
RISK_FREE_RATE = 0.07 # 7% India risk-free approximation

def d1_d2(S, K, T, r, sigma):
    """
    Calculates d1 and d2 parameters for Black-Scholes.
    """
    if T <= 0 or sigma <= 0:
        return 0, 0
    
    # Avoid div by zero
    T = max(T, 0.0001)
    sigma = max(sigma, 0.001)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return d1, d2

def get_greeks(S, K, T, r, sigma, option_type="CE"):
    """
    Returns a dictionary of Greeks.
    S: Spot Price
    K: Strike Price
    T: Time to Expiry (in years)
    r: Risk-Free Rate (decimal, e.g., 0.07)
    sigma: IV (decimal, e.g., 0.15 for 15%)
    option_type: "CE" or "PE"
    """
    # Defaults
    greeks = {
        "delta": 0,
        "gamma": 0,
        "theta": 0,
        "vega": 0
    }

    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return greeks

    d1, d2 = d1_d2(S, K, T, r, sigma)
    
    # Normalized PDF/CDF
    pdf_d1 = norm.pdf(d1)
    cdf_d1 = norm.cdf(d1)
    cdf_d2 = norm.cdf(d2)
    
    if option_type == "CE":
        delta = cdf_d1
        # Theta (annual) -> divide by 365 for daily decay estimate usually
        theta_annual = -(S * pdf_d1 * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * cdf_d2
    else: # PE
        delta = cdf_d1 - 1
        theta_annual = -(S * pdf_d1 * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * (1 - cdf_d2)

    # Gamma (same for Call/Put)
    gamma = pdf_d1 / (S * sigma * np.sqrt(T))
    
    # Vega (same for Call/Put) -> Change in price per 1% change in IV
    # Usually Vega is shown as * 0.01 (impact of 1% change)
    vega = S * np.sqrt(T) * pdf_d1 * 0.01

    # Daily Theta (approx)
    theta_daily = theta_annual / 365.0

    return {
        "delta": round(delta, 3),
        "gamma": round(gamma, 5),
        "theta": round(theta_daily, 2), # Daily Theta
        "vega": round(vega, 2)
    }

def get_implied_volatility(market_price, S, K, T, r, option_type="CE", tol=0.001, max_iter=100):
    """
    Calculates Implied Volatility using Newton-Raphson method.
    """
    if market_price <= 0 or S <= 0 or K <= 0 or T <= 0:
        return 0

    sigma = 0.3 # Initial guess (30%)
    
    for i in range(max_iter):
        # Calculate Price and Vega
        greeks = get_greeks(S, K, T, r, sigma, option_type)
        
        # We need the theoretical price, not just delta/theta.
        # Let's re-implement price func or extract it.
        # For efficiency, let's keep it inline or add bs_price func.
        
        d1, d2 = d1_d2(S, K, T, r, sigma)
        if option_type == "CE":
            theo_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            theo_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
        diff = theo_price - market_price
        
        if abs(diff) < tol:
            return round(sigma * 100, 2) # Return as percentage (e.g. 15.5)
            
        vega = S * np.sqrt(T) * norm.pdf(d1)
        if vega == 0:
            break
            
        sigma = sigma - diff / vega
        
    return round(sigma * 100, 2)

def calculate_time_to_expiry(expiry_date):
    """
    Returns T (years) from a dict or datetime.
    """
    if isinstance(expiry_date, str):
         # Try parsing YYYY-MM-DD
         try:
             expiry_date = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").date()
         except:
             return 0

    now = datetime.datetime.now()
    if isinstance(expiry_date, datetime.date) and not isinstance(expiry_date, datetime.datetime):
         # Convert to datetime at market close (15:30) for precision?
         # Or just use midnight
         expiry_dt = datetime.datetime.combine(expiry_date, datetime.time(15, 30))
    else:
         expiry_dt = expiry_date
         
    diff = expiry_dt - now
    days = diff.days
    seconds = diff.seconds
    total_years = (days + seconds / 86400.0) / 365.0
    return max(0, total_years)

if __name__ == "__main__":
    # Test
    S = 21500
    K = 21600
    T = 5/365 # 5 days
    r = 0.07
    sigma = 0.15 # 15%
    
    print(f"Call Greeks: {get_greeks(S, K, T, r, sigma, 'CE')}")
    print(f"Put Greeks: {get_greeks(S, K, T, r, sigma, 'PE')}")
