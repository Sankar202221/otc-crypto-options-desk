import numpy as np
import scipy.stats as si
import datetime

# -----------------------------------------------------------------------------
# 1. Vanilla Analytical Pricing (Black-Scholes-Merton)
# -----------------------------------------------------------------------------

def bsm_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "Call") -> float:
    """Calculates the analytical BSM option price.
    T is in years. r and sigma are decimals (e.g. 0.05 and 0.60).
    """
    if T <= 0:
        if option_type.lower() == "call":
            return max(0.0, S - K)
        else:
            return max(0.0, K - S)
            
    if sigma <= 0:
        # Zero vol limit
        discount = np.exp(-r * T)
        if option_type.lower() == "call":
            return max(0.0, S - K * discount)
        else:
            return max(0.0, K * discount - S)

    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type.lower() == "call":
        price = S * si.norm.cdf(d1, 0.0, 1.0) - K * np.exp(-r * T) * si.norm.cdf(d2, 0.0, 1.0)
    else:
        price = K * np.exp(-r * T) * si.norm.cdf(-d2, 0.0, 1.0) - S * si.norm.cdf(-d1, 0.0, 1.0)
        
    return max(0.0, price)

def bsm_greeks(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "Call") -> dict:
    """Calculates BSM analytical Greeks: Delta, Gamma, Vega, Theta."""
    if T <= 0:
        # Expiry greeks limit
        if option_type.lower() == "call":
            delta = 1.0 if S > K else 0.0
        else:
            delta = -1.0 if S < K else 0.0
        return {"delta": delta, "gamma": 0.0, "vega": 0.0, "theta": 0.0}
        
    if sigma <= 0:
        sigma = 1e-6 # Avoid division by zero

    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    # 1. Delta
    if option_type.lower() == "call":
        delta = si.norm.cdf(d1, 0.0, 1.0)
    else:
        delta = si.norm.cdf(d1, 0.0, 1.0) - 1.0
        
    # 2. Gamma
    gamma = si.norm.pdf(d1, 0.0, 1.0) / (S * sigma * np.sqrt(T))
    
    # 3. Vega (scaled for 1% vol change, but standard units: dPrice/dSigma)
    vega = S * si.norm.pdf(d1, 0.0, 1.0) * np.sqrt(T)
    
    # 4. Theta (annualized, divide by 365 to get daily theta)
    term1 = -(S * si.norm.pdf(d1, 0.0, 1.0) * sigma) / (2 * np.sqrt(T))
    if option_type.lower() == "call":
        term2 = r * K * np.exp(-r * T) * si.norm.cdf(d2, 0.0, 1.0)
        theta = term1 - term2
    else:
        term2 = r * K * np.exp(-r * T) * si.norm.cdf(-d2, 0.0, 1.0)
        theta = term1 + term2
        
    return {
        "delta": float(delta),
        "gamma": float(gamma),
        "vega": float(vega),
        "theta": float(theta)
    }

# -----------------------------------------------------------------------------
# 2. Structured Products Pricing (Monte Carlo Simulator)
# -----------------------------------------------------------------------------

def price_structured_product(
    S: float, 
    K: float, 
    T: float, 
    r: float, 
    sigma: float, 
    structure_type: str, 
    quantity: float = 1.0, 
    num_sims: int = 10000
) -> dict:
    """Prices structured products using Monte Carlo simulation.
    Returns: BSM price, Bid, Ask, Spread, and Greeks (Delta, Gamma, Vega, Theta).
    """
    # Expiry in years
    if T <= 0:
        payoff = calculate_structure_payoff(S, S, K, structure_type)
        return {
            "price": payoff,
            "bid": payoff * 0.99,
            "ask": payoff * 1.01,
            "spread": payoff * 0.02,
            "delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0
        }
        
    # Generate terminal spot prices
    # S_T = S * exp((r - 0.5*sigma^2)*T + sigma*sqrt(T)*Z)
    np.random.seed(42) # set seed for path consistency
    z = np.random.standard_normal(num_sims)
    S_T = S * np.exp((r - 0.5 * sigma ** 2) * T + sigma * np.sqrt(T) * z)
    
    # Calculate payoffs
    payoffs = np.array([calculate_structure_payoff(S, st, K, structure_type) for st in S_T])
    
    # Discount back
    discount = np.exp(-r * T)
    price = float(np.mean(payoffs) * discount)
    
    # Apply bid/ask spread (wider for structured products than vanillas)
    # E.g. spread = max(1.5% of price, 0.5% of spot)
    spread = max(0.015 * price, 0.005 * S * 0.01) if price > 0 else 0.01 * S * 0.01
    bid = max(0.0, price - 0.5 * spread)
    ask = price + 0.5 * spread
    
    # Calculate Greeks via Finite Differences
    dS = S * 0.01 # 1% shift for spot
    dVol = 0.01   # 1% vol shift (0.01 absolute)
    dT = 1 / 365.0 # 1 day decay
    
    # Delta & Gamma via Spot shifts (S+dS, S-dS)
    S_T_up = (S + dS) * np.exp((r - 0.5 * sigma ** 2) * T + sigma * np.sqrt(T) * z)
    S_T_down = (S - dS) * np.exp((r - 0.5 * sigma ** 2) * T + sigma * np.sqrt(T) * z)
    
    payoffs_up = np.array([calculate_structure_payoff(S + dS, st, K, structure_type) for st in S_T_up])
    payoffs_down = np.array([calculate_structure_payoff(S - dS, st, K, structure_type) for st in S_T_down])
    
    price_up = float(np.mean(payoffs_up) * discount)
    price_down = float(np.mean(payoffs_down) * discount)
    
    delta = (price_up - price_down) / (2 * dS)
    gamma = (price_up - 2 * price + price_down) / (dS ** 2)
    
    # Vega via Vol shift (sigma + dVol)
    S_T_vol = S * np.exp((r - 0.5 * (sigma + dVol) ** 2) * T + (sigma + dVol) * np.sqrt(T) * z)
    payoffs_vol = np.array([calculate_structure_payoff(S, st, K, structure_type) for st in S_T_vol])
    price_vol = float(np.mean(payoffs_vol) * discount)
    
    vega = (price_vol - price) / dVol
    
    # Theta via Time decay (T - dT)
    if T - dT > 0:
        S_T_t = S * np.exp((r - 0.5 * sigma ** 2) * (T - dT) + sigma * np.sqrt(T - dT) * z)
        payoffs_t = np.array([calculate_structure_payoff(S, st, K, structure_type) for st in S_T_t])
        price_t = float(np.mean(payoffs_t) * np.exp(-r * (T - dT)))
        theta = (price_t - price) / dT
    else:
        payoffs_t = np.array([calculate_structure_payoff(S, st, K, structure_type) for st in S_T])
        price_t = float(np.mean(payoffs_t)) # Undiscounted final payoff
        theta = (price_t - price) / dT
        
    return {
        "price": price,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "theta": theta
    }

def calculate_structure_payoff(S0: float, ST: float, K: float, structure_type: str) -> float:
    """Calculates the payoff of a structured product at expiry.
    1. Covered Call: Long Spot + Short Call. Payoff = ST - max(0, ST - K)
    2. Cash-Secured Put: Short Put + Collateral in Cash. Payoff = -max(0, K - ST) (Premium cash is separately tracked, payoff represents option value)
    3. Collar: Long Spot + Long Put (strike K_put) + Short Call (strike K_call)
       Here, K represents the Call strike, and we set Put strike at 90% of spot (K_put = 0.90 * S0).
    4. Custom Payoff: User can define structured payouts. We simulate a binary double barrier/straddle payoff as an example.
    """
    struct = structure_type.lower()
    
    if struct == "covered call" or struct == "coveredcall":
        # Client holds spot, sells call. 
        # Desk is SHORT Covered Call = Client is LONG.
        # Wait, from client perspective: Long Spot, Short Call.
        # From desk perspective (OTC Counterparty): Desk is Short Spot, Long Call.
        # Let's price the structure as a bundle: Spot - Call.
        option_payoff = max(0.0, ST - K)
        return ST - option_payoff
        
    elif struct == "cash-secured put" or struct == "cashsecuredput":
        # Client sells put, holds cash collateral.
        # Desk is counterparty (Long Put).
        # Structured product payoff: cash - put payoff.
        # Put option payoff:
        option_payoff = max(0.0, K - ST)
        return -option_payoff # option value payoff
        
    elif struct == "collar":
        # Client: Long Spot + Long Put (K_put) - Short Call (K_call)
        # We set K_call = K, K_put = 0.90 * S0
        K_call = K
        K_put = 0.90 * S0
        call_payoff = max(0.0, ST - K_call)
        put_payoff = max(0.0, K_put - ST)
        return ST + put_payoff - call_payoff
        
    elif struct == "custom payoff" or struct == "custompayoff":
        # Example of a custom structure: "Straddle with Knock-Out"
        # Payoff is a Straddle |ST - K| but if ST moves > 50% away from S0, it knocks out to 0
        dist = abs(ST - K)
        if ST > S0 * 1.50 or ST < S0 * 0.50:
            return 0.0
        return dist
        
    else:
        # Default fallback to vanilla call
        return max(0.0, ST - K)
