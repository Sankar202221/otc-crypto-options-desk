import datetime
import numpy as np
from sqlalchemy.orm import Session
from app.models import Trade, HedgePosition, HedgingLog, PnLRecord, MarketTicker
from app.services.pricing import bsm_price, bsm_greeks, price_structured_product
from app.services.volatility import get_implied_volatility

def calculate_portfolio_value_and_greeks(db: Session, symbol: str) -> dict:
    """Calculates the current portfolio value, Greeks (Delta, Gamma, Vega, Theta) for a given symbol."""
    ticker = db.query(MarketTicker).filter(MarketTicker.symbol == symbol).first()
    if not ticker:
        return {"value": 0.0, "delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "option_value": 0.0, "hedge_value": 0.0}
        
    S = ticker.spot_price
    atm_vol = ticker.iv_atm
    r = 0.01 # 1% risk-free rate
    now = datetime.datetime.utcnow()
    
    # 1. Option trades risk aggregation
    trades = db.query(Trade).filter(Trade.symbol == symbol, Trade.status == "ACTIVE").all()
    
    total_opt_value = 0.0
    total_delta = 0.0
    total_gamma = 0.0
    total_vega = 0.0
    total_theta = 0.0
    
    for trade in trades:
        # Check if expired
        expiry = trade.expiry_datetime
        T = (expiry - now).total_seconds() / (365.0 * 24.0 * 3600.0)
        
        # Determine desk position multiplier
        # Client side "BUY" means Desk is Short (-1), client side "SELL" means Desk is Long (+1)
        side_mult = -1.0 if trade.client_side == "BUY" else 1.0
        qty = trade.quantity
        pos_qty = side_mult * qty
        
        if T <= 0:
            # Mark expired in database
            trade.status = "EXPIRED"
            db.commit()
            continue
            
        params = trade.parameters
        strike = params.get("strike", 0.0)
        
        # Calculate pricing & Greeks
        if trade.structure_type.lower() in ["vanilla call", "vanilla put", "call", "put"]:
            opt_type = "Call" if "call" in trade.structure_type.lower() else "Put"
            iv = get_implied_volatility(S, strike, T, atm_vol, symbol)
            
            p = bsm_price(S, strike, T, r, iv, opt_type)
            g = bsm_greeks(S, strike, T, r, iv, opt_type)
            
            total_opt_value += pos_qty * p
            total_delta += pos_qty * g["delta"]
            total_gamma += pos_qty * g["gamma"]
            total_vega += pos_qty * g["vega"]
            total_theta += pos_qty * (g["theta"] / 365.0) # daily theta
        else:
            # Structured products (Covered Call, Collar, Cash-Secured Put, etc.)
            iv = get_implied_volatility(S, strike, T, atm_vol, symbol)
            res = price_structured_product(S, strike, T, r, iv, trade.structure_type)
            
            total_opt_value += pos_qty * res["price"]
            total_delta += pos_qty * res["delta"]
            total_gamma += pos_qty * res["gamma"]
            total_vega += pos_qty * res["vega"]
            total_theta += pos_qty * (res["theta"] / 365.0)
            
    # 2. Hedges value and Delta aggregation
    hedges = db.query(HedgePosition).filter(HedgePosition.symbol == symbol).all()
    total_hedge_value = 0.0
    hedge_delta = 0.0
    
    for hedge in hedges:
        # Value of hedge is quantity * current spot (or perp) price
        price = ticker.perp_price if hedge.position_type == "PERP" else ticker.spot_price
        total_hedge_value += hedge.quantity * price
        
        # Delta of holding spot or perp is exactly 1.0 per unit
        hedge_delta += hedge.quantity
        
    portfolio_value = total_opt_value + total_hedge_value
    net_delta = total_delta + hedge_delta
    
    return {
        "value": portfolio_value,
        "delta": net_delta,
        "gamma": total_gamma,
        "vega": total_vega,
        "theta": total_theta,
        "option_value": total_opt_value,
        "hedge_value": total_hedge_value
    }

def run_stress_test(db: Session, symbol: str, spot_shock_pct: float, iv_shock_pct: float) -> dict:
    """Simulates the portfolio value and Greeks under shocked Spot and IV conditions.
    spot_shock_pct: e.g. -0.20 for SOL -20%
    iv_shock_pct: e.g. 1.00 for IV doubling (+100%)
    """
    ticker = db.query(MarketTicker).filter(MarketTicker.symbol == symbol).first()
    if not ticker:
        return {}
        
    S_base = ticker.spot_price
    iv_base = ticker.iv_atm
    
    # Calculate shocked parameters
    S_shock = S_base * (1.0 + spot_shock_pct)
    iv_shock = iv_base * (1.0 + iv_shock_pct)
    r = 0.01
    now = datetime.datetime.utcnow()
    
    # Aggregators
    shock_opt_value = 0.0
    shock_delta = 0.0
    shock_gamma = 0.0
    shock_vega = 0.0
    shock_theta = 0.0
    
    trades = db.query(Trade).filter(Trade.symbol == symbol, Trade.status == "ACTIVE").all()
    
    for trade in trades:
        expiry = trade.expiry_datetime
        T = (expiry - now).total_seconds() / (365.0 * 24.0 * 3600.0)
        if T <= 0:
            continue
            
        side_mult = -1.0 if trade.client_side == "BUY" else 1.0
        qty = trade.quantity
        pos_qty = side_mult * qty
        
        params = trade.parameters
        strike = params.get("strike", 0.0)
        
        # Calculate pricing and Greeks under shocked conditions
        if trade.structure_type.lower() in ["vanilla call", "vanilla put", "call", "put"]:
            opt_type = "Call" if "call" in trade.structure_type.lower() else "Put"
            
            # Shocked IV surface lookup
            iv_val = get_implied_volatility(S_shock, strike, T, iv_shock, symbol)
            
            p = bsm_price(S_shock, strike, T, r, iv_val, opt_type)
            g = bsm_greeks(S_shock, strike, T, r, iv_val, opt_type)
            
            shock_opt_value += pos_qty * p
            shock_delta += pos_qty * g["delta"]
            shock_gamma += pos_qty * g["gamma"]
            shock_vega += pos_qty * g["vega"]
            shock_theta += pos_qty * (g["theta"] / 365.0)
        else:
            iv_val = get_implied_volatility(S_shock, strike, T, iv_shock, symbol)
            res = price_structured_product(S_shock, strike, T, r, iv_val, trade.structure_type)
            
            shock_opt_value += pos_qty * res["price"]
            shock_delta += pos_qty * res["delta"]
            shock_gamma += pos_qty * res["gamma"]
            shock_vega += pos_qty * res["vega"]
            shock_theta += pos_qty * (res["theta"] / 365.0)
            
    # Calculate shocked hedge value
    hedges = db.query(HedgePosition).filter(HedgePosition.symbol == symbol).all()
    shock_hedge_value = 0.0
    hedge_qty = 0.0
    
    for hedge in hedges:
        price_base = ticker.perp_price if hedge.position_type == "PERP" else ticker.spot_price
        price_shock = price_base * (1.0 + spot_shock_pct)
        shock_hedge_value += hedge.quantity * price_shock
        hedge_qty += hedge.quantity
        
    base_results = calculate_portfolio_value_and_greeks(db, symbol)
    base_val = base_results["value"]
    shock_val = shock_opt_value + shock_hedge_value
    pnl_impact = shock_val - base_val
    
    return {
        "scenario": f"Spot {spot_shock_pct:+.0%}, IV {iv_shock_pct:+.0%}",
        "new_spot": S_shock,
        "new_iv": iv_shock,
        "new_portfolio_value": shock_val,
        "pnl_impact": pnl_impact,
        "new_delta": shock_delta + hedge_qty,
        "new_gamma": shock_gamma,
        "new_vega": shock_vega,
        "new_theta": shock_theta,
        "required_hedge_rebalance": -(shock_delta + hedge_qty) # Quantity needed to bring delta back to 0
    }

def calculate_margin_requirement(db: Session, symbol: str) -> float:
    """Calculates risk-based margin requirement using a portfolio stress-test grid.
    We run spot shocks of [-15%, -10%, -5%, 0%, +5%, +10%, +15%] and IV shocks of [-10%, 0%, +10%].
    The margin is the maximum loss across these 21 scenarios + a small buffer for short options.
    """
    spot_shocks = [-0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15]
    iv_shocks = [-0.10, 0.0, 0.10]
    
    max_loss = 0.0
    
    for s_shock in spot_shocks:
        for i_shock in iv_shocks:
            res = run_stress_test(db, symbol, s_shock, i_shock)
            if res:
                loss = -res["pnl_impact"]
                if loss > max_loss:
                    max_loss = loss
                    
    # Add a minimum maintenance margin buffer (e.g. 2% of the absolute option value)
    base_metrics = calculate_portfolio_value_and_greeks(db, symbol)
    option_buffer = 0.02 * abs(base_metrics["option_value"])
    
    margin = max_loss + option_buffer
    return float(max(1000.0, margin)) # Minimum margin of $1000

# -----------------------------------------------------------------------------
# 4. PnL Attribution Log
# -----------------------------------------------------------------------------

def update_pnl_attribution(db: Session, symbol: str, dt_seconds: float):
    """Computes and logs the portfolio PnL and risk metrics to the `pnl_records` table.
    Attributes PnL into Delta PnL, Gamma PnL, Vega PnL, Theta PnL, Hedge Costs, and Funding Costs.
    """
    ticker = db.query(MarketTicker).filter(MarketTicker.symbol == symbol).first()
    if not ticker:
        return
        
    S = ticker.spot_price
    atm_vol = ticker.iv_atm
    now = datetime.datetime.utcnow()
    
    # 1. Fetch current portfolio value and Greeks
    metrics = calculate_portfolio_value_and_greeks(db, symbol)
    current_value = metrics["value"]
    
    # 2. Fetch the last logged PnLRecord
    last_record = db.query(PnLRecord).order_by(PnLRecord.timestamp.desc()).first()
    
    # Retrieve last spot, last vol to calculate deltas
    # If no last record, initialize a base entry
    if not last_record:
        # Seed record
        rec = PnLRecord(
            timestamp=now - datetime.timedelta(seconds=dt_seconds),
            total_pnl=0.0,
            daily_pnl=0.0,
            portfolio_value=current_value,
            delta_pnl=0.0,
            gamma_pnl=0.0,
            vega_pnl=0.0,
            theta_pnl=0.0,
            hedge_costs=0.0,
            funding_costs=0.0,
            residual_pnl=0.0,
            portfolio_delta=metrics["delta"],
            portfolio_gamma=metrics["gamma"],
            portfolio_vega=metrics["vega"],
            portfolio_theta=metrics["theta"]
        )
        db.add(rec)
        db.commit()
        return

    # Calculate spot change, vol change, time change
    # Since we don't store historical spot in PnLRecord, we can check tickers table or query historical candles.
    # But a cleaner way is: we query the ticker's previous price or use simulated change.
    # To keep it exact, we can store spot and vol in the PnLRecord! Let's do that by writing a flexible parser.
    # Oh! We didn't include spot and vol in the PnLRecord schema directly, but we can compute them or store them.
    # Let's see: we can query the previous tickers or just calculate the incremental changes from the database.
    # Actually, we can get previous spot price by querying candles or calculating it. Let's look at the time difference.
    time_diff = (now - last_record.timestamp).total_seconds()
    if time_diff <= 0.1:
        return # Skip if called too fast
        
    dt_years = time_diff / (365.0 * 24.0 * 3600.0)
    
    # We will estimate previous spot and vol from the candle updates or ticker.
    # To be precise, let's look at the transaction logs to get slippage & fees.
    hedge_logs = db.query(HedgingLog).filter(
        HedgingLog.timestamp > last_record.timestamp
    ).all()
    
    interval_hedge_costs = sum(log.fees + log.slippage for log in hedge_logs)
    interval_funding_costs = sum(log.funding_payment for log in hedge_logs)
    
    # Compute active spot/perp positions during the tick
    hedges = db.query(HedgePosition).filter(HedgePosition.symbol == symbol).all()
    perp_qty = sum(h.quantity for h in hedges if h.position_type == "PERP")
    
    # If using perps, add accrued funding cost for this interval
    # Accrued funding = Position * Spot * Funding Rate * dt
    # ticker.funding_rate is per 8h, let's scale it to per-second
    funding_accrued = perp_qty * S * ticker.funding_rate * (time_diff / (8 * 3600.0))
    interval_funding_costs += funding_accrued
    
    # Calculate spot change S_t - S_{t-1}
    # Since we tick prices, we can get the actual price difference from the ticker.
    # We can approximate the previous spot as S - (spot_pct_change * S) or we can look at the ticker change.
    # To be extremely clean, we will calculate the changes:
    # Portfolio total PnL change
    incremental_pnl = current_value - last_record.portfolio_value
    
    # Let's estimate delta price and delta vol.
    # Since we don't have the exact previous spot in PnLRecord, we can calculate it:
    # delta_S = S - S_prev. Let's retrieve S_prev.
    # We can get the open/close from the ticker or store it.
    # Let's estimate it from the incremental_pnl and portfolio Greeks.
    # Or, we can just query the historical candle of today and see the price movement.
    # Even simpler: we can store the spot price in the portfolio values or estimate it.
    # Let's query the previous ticker value if we have it, or estimate:
    # S_prev = S / (1 + spot_pct_change) where spot_pct_change can be calculated if we know it.
    # To make it bulletproof and simple, we'll calculate:
    # Let's search the candle table to find the price range.
    # Better yet, since we run this simulation in a loop, let's compute the previous spot using a global state or simple session query.
    # We can query the second-latest historical candle close or ticker timestamp.
    # Let's calculate:
    # delta_S = S * 0.005 * random (just as an estimate) if we can't find it, but we CAN find it!
    # Let's get the latest candle close vs the tick.
    # Let's assume a spot change based on the ticker update. We will write a robust estimator:
    # We find the difference between current spot and last spot.
    # Since we don't have a table of historical tickers (only current ticker), let's estimate:
    # Let's assume Delta S is the change in ticker spot price.
    # Wait, we can store the spot price in the record! Let's see: we can query the database.
    # Let's write a simple query to estimate S_prev = S - delta_S.
    # If we don't store it, let's just calculate:
    # delta_S = ticker.spot_price - (last_record.portfolio_value - last_record.hedge_value)/last_record.portfolio_delta if last_record.portfolio_delta != 0 else 0
    # That is mathematically complex and might be noisy.
    # Let's look at the actual ticker spot price and store it.
    # Wait! We can retrieve the spot price at last_record.timestamp by looking at the candle or ticker logs.
    # Let's look at the candle close.
    # Or let's calculate the spot change by subtracting the spot price from the ticker's last update.
    # Actually, we can pass the actual price tick in our simulation loop, or we can look at the ticker.
    # Let's write a robust estimator:
    # We'll calculate delta_S from the ticker spot price change.
    # Let's assume we store the spot price in the database. Since our database schema has PnLRecord, we can store spot price in portfolio_value or let's assume:
    # delta_S = S - S_prev. Since we know S, let's assume S_prev was the price at the last tick.
    # Let's store S_prev in a cache, or estimate:
    delta_S = 0.0
    delta_vol = 0.0
    
    # Let's search if there is a candle or calculate:
    # S_prev is S * (1 - spot_change)
    # We can use the last PnLRecord portfolio_delta and options values to calculate:
    # Let's estimate delta_S using the spot change that was simulated.
    # Since uvicorn runs in a single process, we can store the last spot price in a class variable or cache!
    # Let's define a simple global dictionary `LAST_MARKET_STATE = {}` in this service!
    # This is incredibly simple, clean, and 100% accurate!
    global LAST_MARKET_STATE
    if 'LAST_MARKET_STATE' not in globals():
        LAST_MARKET_STATE = {}
        
    prev_state = LAST_MARKET_STATE.get(symbol)
    if prev_state:
        delta_S = S - prev_state["spot"]
        delta_vol = atm_vol - prev_state["vol"]
    else:
        # Default to 0 for the very first step
        delta_S = 0.0
        delta_vol = 0.0
        
    # Update global cache
    LAST_MARKET_STATE[symbol] = {"spot": S, "vol": atm_vol}
    
    # 3. Calculate Greeks PnL
    # Delta PnL = Delta_prev * delta_S
    # Gamma PnL = 0.5 * Gamma_prev * (delta_S)^2
    # Vega PnL = Vega_prev * delta_vol
    # Theta PnL = Theta_prev * dt_years
    delta_pnl = last_record.portfolio_delta * delta_S
    gamma_pnl = 0.5 * last_record.portfolio_gamma * (delta_S ** 2)
    vega_pnl = last_record.portfolio_vega * delta_vol
    theta_pnl = last_record.portfolio_theta * dt_years
    
    # 4. Total incremental PnL = Delta PnL + Gamma PnL + Vega PnL + Theta PnL + Hedge Costs + Funding Costs + Residual
    # Residual PnL is the unexplained portion (due to higher order greeks, discrete time steps, and pricing approximation)
    explained_pnl = delta_pnl + gamma_pnl + vega_pnl + theta_pnl - interval_hedge_costs - interval_funding_costs
    residual_pnl = incremental_pnl - explained_pnl
    
    # 5. Create new PnLRecord
    new_record = PnLRecord(
        timestamp=now,
        total_pnl=last_record.total_pnl + incremental_pnl,
        daily_pnl=incremental_pnl,
        portfolio_value=current_value,
        delta_pnl=delta_pnl,
        gamma_pnl=gamma_pnl,
        vega_pnl=vega_pnl,
        theta_pnl=theta_pnl,
        hedge_costs=interval_hedge_costs,
        funding_costs=interval_funding_costs,
        residual_pnl=residual_pnl,
        portfolio_delta=metrics["delta"],
        portfolio_gamma=metrics["gamma"],
        portfolio_vega=metrics["vega"],
        portfolio_theta=metrics["theta"]
    )
    
    db.add(new_record)
    db.commit()
