import pytest
import numpy as np
from app.services.pricing import bsm_price, bsm_greeks, price_structured_product
from app.services.volatility import solve_implied_volatility

def test_bsm_price_call():
    """Verify BSM pricing for a Vanilla Call option."""
    S = 100.0
    K = 100.0
    T = 0.25 # 3 months
    r = 0.05
    sigma = 0.40
    
    call_price = bsm_price(S, K, T, r, sigma, "Call")
    assert call_price > 0.0
    
    # Intrinsic value check
    assert call_price >= max(0.0, S - K)

def test_bsm_price_put():
    """Verify BSM pricing for a Vanilla Put option."""
    S = 100.0
    K = 105.0
    T = 0.5
    r = 0.02
    sigma = 0.30
    
    put_price = bsm_price(S, K, T, r, sigma, "Put")
    assert put_price > 0.0
    assert put_price >= max(0.0, K - S)

def test_bsm_greeks_bounds():
    """Ensure analytical Greeks conform to standard financial bounds."""
    S = 150.0
    K = 150.0
    T = 0.1
    r = 0.01
    sigma = 0.60
    
    call_greeks = bsm_greeks(S, K, T, r, sigma, "Call")
    assert 0.0 <= call_greeks["delta"] <= 1.0
    assert call_greeks["gamma"] > 0.0
    assert call_greeks["vega"] > 0.0
    assert call_greeks["theta"] < 0.0
    
    put_greeks = bsm_greeks(S, K, T, r, sigma, "Put")
    assert -1.0 <= put_greeks["delta"] <= 0.0
    assert put_greeks["gamma"] > 0.0
    assert put_greeks["vega"] > 0.0
    assert put_greeks["theta"] < 0.0 # Theta can be positive in rare deep ITM put cases, but standard ATM is negative

def test_iv_solver():
    """Ensure the Implied Volatility solver can invert the BSM formula."""
    S = 150.0
    K = 160.0
    T = 0.2
    r = 0.03
    original_iv = 0.65
    
    price = bsm_price(S, K, T, r, original_iv, "Call")
    solved_iv = solve_implied_volatility(S, K, T, r, price, "Call")
    
    # Solved IV should be within a 0.1% tolerance of original IV
    assert pytest.approx(solved_iv, abs=1e-3) == original_iv

def test_structured_pricing():
    """Verify structured product pricing returns sensible values and numerical Greeks."""
    S = 100.0
    K = 100.0
    T = 0.1
    r = 0.01
    sigma = 0.50
    
    # Price a Covered Call (Long Spot + Short Call)
    res = price_structured_product(S, K, T, r, sigma, "Covered Call", num_sims=5000)
    
    # A covered call caps upside, so its price should be lower than spot
    assert res["price"] < S
    
    # Analytical verification: Covered Call price = Spot - Call_price
    c_price = bsm_price(S, K, T, r, sigma, "Call")
    analytical_cc_price = S - c_price
    
    # Monte Carlo price should approximate analytical price
    assert pytest.approx(res["price"], rel=0.03) == analytical_cc_price
    
    # Delta of Covered Call = Delta_spot (1.0) - Delta_call
    # Call delta is roughly 0.5, so covered call delta is roughly 0.5
    assert 0.2 < res["delta"] < 0.8
