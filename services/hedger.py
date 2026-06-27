import datetime
import random
from sqlalchemy.orm import Session
from app.models import HedgePosition, HedgingLog, MarketTicker
from app.services.risk import calculate_portfolio_value_and_greeks
from app.config import settings

def execute_hedge_trade(
    db: Session, 
    symbol: str, 
    qty_to_trade: float, 
    hedge_type: str = "SPOT"
) -> dict:
    """Executes a hedge trade (BUY or SELL spot/perp) and updates the database.
    qty_to_trade: Positive to BUY, Negative to SELL.
    """
    ticker = db.query(MarketTicker).filter(MarketTicker.symbol == symbol).first()
    if not ticker or qty_to_trade == 0:
        return {}
        
    now = datetime.datetime.utcnow()
    action = "BUY" if qty_to_trade > 0 else "SELL"
    abs_qty = abs(qty_to_trade)
    
    # 1. Determine execution price based on asset type (Spot or Perp)
    base_price = ticker.perp_price if hedge_type.upper() == "PERP" else ticker.spot_price
    
    # Apply slippage (e.g. slippage = base_price * slippage_factor * random)
    # Plus a liquidity impact factor (larger trade = more slippage)
    slippage_pct = settings.DEFAULT_SLIPPAGE * (1.0 + 0.1 * abs_qty * random.random())
    slippage = base_price * slippage_pct
    
    execution_price = base_price + slippage if action == "BUY" else base_price - slippage
    
    # 2. Calculate execution fees (Taker fee)
    fees = abs_qty * execution_price * settings.DEFAULT_TAKER_FEE
    
    # 3. Update HedgePosition in database
    hedge_pos = db.query(HedgePosition).filter(
        HedgePosition.symbol == symbol,
        HedgePosition.position_type == hedge_type.upper()
    ).first()
    
    if not hedge_pos:
        # Create new position
        hedge_pos = HedgePosition(
            symbol=symbol,
            position_type=hedge_type.upper(),
            quantity=qty_to_trade,
            average_entry_price=execution_price,
            last_updated=now
        )
        db.add(hedge_pos)
    else:
        # Update existing position
        old_qty = hedge_pos.quantity
        new_qty = old_qty + qty_to_trade
        
        # Calculate new average entry price if increasing position in same direction
        if old_qty * qty_to_trade > 0:
            total_cost = (old_qty * hedge_pos.average_entry_price) + (qty_to_trade * execution_price)
            hedge_pos.average_entry_price = abs(total_cost / new_qty)
        elif new_qty == 0:
            hedge_pos.average_entry_price = 0.0
        else:
            # If reducing or flipping position, keep the entry price or update to execution price on flip
            if old_qty * new_qty < 0:
                # Flipped position
                hedge_pos.average_entry_price = execution_price
                
        hedge_pos.quantity = new_qty
        hedge_pos.last_updated = now
        
    # 4. Log the transaction
    log_entry = HedgingLog(
        timestamp=now,
        symbol=symbol,
        action=action,
        quantity=abs_qty,
        price=execution_price,
        asset_type=hedge_type.upper(),
        slippage=slippage * abs_qty,
        fees=fees,
        funding_payment=0.0
    )
    db.add(log_entry)
    db.commit()
    
    return {
        "action": action,
        "quantity": abs_qty,
        "price": execution_price,
        "fees": fees,
        "slippage": slippage * abs_qty,
        "type": hedge_type.upper()
    }

def run_auto_hedger(
    db: Session, 
    symbol: str, 
    hedge_type: str = "SPOT", 
    threshold: float = None
) -> dict:
    """Checks portfolio Delta and automatically places a hedge trade if it exceeds threshold.
    Returns details of execution if trade occurred, else None.
    """
    if threshold is None:
        threshold = settings.DEFAULT_HEDGE_THRESHOLD
        
    # Get current portfolio risk
    metrics = calculate_portfolio_value_and_greeks(db, symbol)
    net_delta = metrics["delta"]
    
    # Delta hedging goal: make net delta equal to 0
    # If net delta is +0.05, we have excess delta, so we need to SELL 0.05 units of spot/perp.
    # If net delta is -0.05, we are short delta, so we need to BUY 0.05 units.
    if abs(net_delta) > threshold:
        # We trade the negative of net_delta to offset it
        qty_to_trade = -net_delta
        print(f"Auto-Hedger: Portfolio Delta for {symbol} is {net_delta:.4f} (limit {threshold}). Placing trade to hedge {qty_to_trade:+.4f} {symbol} ({hedge_type})...")
        trade_details = execute_hedge_trade(db, symbol, qty_to_trade, hedge_type)
        return trade_details
        
    return {}
