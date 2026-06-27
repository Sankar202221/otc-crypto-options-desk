import numpy as np
from sqlalchemy.orm import Session
from app.models import HistoricalCandle, MarketTicker
from app.services.pricing import bsm_price, bsm_greeks

# Parametric Surface Parameters per Asset
# alpha: skew (slope), beta: smile (curvature)
SURFACE_PARAMS = {
    "BTC": {"alpha": -0.15, "beta": 0.35, "ts_coeff": 0.10},
    "ETH": {"alpha": -0.18, "beta": 0.40, "ts_coeff": 0.12},
    "SOL": {"alpha": -0.22, "beta": 0.45, "ts_coeff": 0.15},
    "ARB": {"alpha": -0.25, "beta": 0.50, "ts_coeff": 0.18}
}

# -----------------------------------------------------------------------------
# 1. Realized Volatility Calculation
# -----------------------------------------------------------------------------

def calculate_realized_volatility(db: Session, symbol: str, lookback_days: int = 30) -> float:
    """Calculates annualized realized volatility from historical close prices."""
    candles = db.query(HistoricalCandle).filter(
        HistoricalCandle.symbol == symbol
    ).order_by(HistoricalCandle.timestamp.desc()).limit(lookback_days + 1).all()
    
    if len(candles) < 2:
        return 0.50 # Fallback default
        
    closes = [c.close for c in candles][::-1] # Ascending order
    
    # Calculate log returns: ln(P_t / P_{t-1})
    log_returns = []
    for i in range(1, len(closes)):
        if closes[i-1] > 0 and closes[i] > 0:
            log_returns.append(np.log(closes[i] / closes[i-1]))
            
    if len(log_returns) < 1:
        return 0.50
        
    # Standard deviation * sqrt(365) (crypto is 24/7/365)
    std_dev = np.std(log_returns, ddof=1)
    realized_vol = std_dev * np.sqrt(365.0)
    
    return float(realized_vol)

# -----------------------------------------------------------------------------
# 2. Implied Volatility Solver
# -----------------------------------------------------------------------------

def bisection_iv_solver(S: float, K: float, T: float, r: float, target_price: float, option_type: str = "Call", tol: float = 1e-5) -> float:
    """Fallback bisection solver when Newton-Raphson fails or Vega is too small."""
    low, high = 0.001, 3.0
    for _ in range(100):
        mid = 0.5 * (low + high)
        price = bsm_price(S, K, T, r, mid, option_type)
        if abs(price - target_price) < tol:
            return mid
        if price < target_price:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)

def solve_implied_volatility(S: float, K: float, T: float, r: float, target_price: float, option_type: str = "Call", max_iter: int = 100, tol: float = 1e-6) -> float:
    """Solves for implied volatility using Newton-Raphson method."""
    if T <= 0 or target_price <= 0:
        return 0.0
        
    # Check intrinsic value lower bound
    intrinsic = max(0.0, S - K) if option_type.lower() == "call" else max(0.0, K - S)
    if target_price <= intrinsic + 1e-5:
        return 0.01 # Volatility cannot be zero
        
    sigma = 0.50 # Initial guess
    
    for _ in range(max_iter):
        price = bsm_price(S, K, T, r, sigma, option_type)
        greeks = bsm_greeks(S, K, T, r, sigma, option_type)
        vega = greeks["vega"]
        
        # If Vega is too small, Newton-Raphson will jump wild. Switch to bisection
        if abs(vega) < 1e-4:
            return bisection_iv_solver(S, K, T, r, target_price, option_type, tol)
            
        diff = price - target_price
        if abs(diff) < tol:
            return float(sigma)
            
        sigma = sigma - diff / vega
        
        # Keep within reasonable bounds during iteration
        if sigma <= 0.01 or sigma >= 3.0:
            return bisection_iv_solver(S, K, T, r, target_price, option_type, tol)
            
    return float(sigma)

# -----------------------------------------------------------------------------
# 3. Volatility Surface Engine
# -----------------------------------------------------------------------------

def get_implied_volatility(S: float, K: float, T: float, atm_vol: float, symbol: str) -> float:
    """Calculates IV for a given strike and maturity from the desk's parametric surface.
    T is tenor in years.
    """
    if T <= 0:
        return atm_vol
        
    params = SURFACE_PARAMS.get(symbol, SURFACE_PARAMS["SOL"])
    alpha = params["alpha"]
    beta = params["beta"]
    ts_coeff = params["ts_coeff"]
    
    # 1. Term structure of ATM: ATM decreases or increases with tenor
    # Standard: decays slightly towards a long term vol or curves
    # E.g. ATM(T) = atm_vol * (1.0 - ts_coeff * tanh(3.0 * (T - 0.25)))
    atm_t = atm_vol * (1.0 - ts_coeff * np.tanh(3.0 * (T - 0.25)))
    
    # Log-moneyness: ln(K / S)
    log_moneyness = np.log(K / S)
    
    # 2. Skew and smile coefficients decay with maturity (smile flattens out for long tenors)
    # skew(T) = alpha * exp(-0.6 * T)
    # smile(T) = beta * exp(-0.4 * T)
    skew_t = alpha * np.exp(-0.6 * T)
    smile_t = beta * np.exp(-0.4 * T)
    
    # 3. Volatility Smile: IV = ATM + Skew * x + Smile * x^2
    iv = atm_t + skew_t * log_moneyness + smile_t * (log_moneyness ** 2)
    
    # Clamp IV to realistic levels: 15% to 200%
    return float(max(0.15, min(2.0, iv)))

def generate_volatility_surface_grid(symbol: str, spot: float, atm_vol: float, num_strikes: int = 21, num_tenors: int = 10) -> dict:
    """Generates a grid of strikes, tenors, and IVs to draw a 3D surface plot.
    Tenor ranges from 1 week (7/365) to 6 months (180/365).
    Strike ranges from 70% of spot to 130% of spot.
    """
    tenors = np.linspace(7/365.0, 180/365.0, num_tenors)
    strikes = np.linspace(0.70 * spot, 1.30 * spot, num_strikes)
    
    X_grid, Y_grid = np.meshgrid(strikes, tenors)
    Z_grid = np.zeros_like(X_grid)
    
    for i in range(num_tenors):
        for j in range(num_strikes):
            K = strikes[j]
            T = tenors[i]
            Z_grid[i, j] = get_implied_volatility(spot, K, T, atm_vol, symbol)
            
    # Return lists for Plotly plotting
    return {
        "strikes": strikes.tolist(),
        "tenors": (tenors * 365.0).tolist(), # Convert to days for display
        "ivs": Z_grid.tolist()
    }
