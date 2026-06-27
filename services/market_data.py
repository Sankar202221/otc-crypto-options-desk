import random
import datetime
from sqlalchemy.orm import Session
from app.models import MarketTicker, HistoricalCandle

# Seed parameters for supported assets
ASSET_PARAMS = {
    "BTC": {"spot": 65000.0, "vol": 0.50, "drift": 0.05, "iv_atm": 0.55},
    "ETH": {"spot": 3500.0, "vol": 0.55, "drift": 0.08, "iv_atm": 0.60},
    "SOL": {"spot": 150.0, "vol": 0.70, "drift": 0.15, "iv_atm": 0.75},
    "ARB": {"spot": 1.00, "vol": 0.85, "drift": 0.20, "iv_atm": 0.85}
}

def seed_initial_market_data(db: Session):
    """Seeds historical candles (30 days) and initial tickers on startup if empty."""
    # Check if we already have tickers
    if db.query(MarketTicker).count() > 0:
        return
        
    print("Seeding initial market data...")
    now = datetime.datetime.utcnow()
    
    for symbol, params in ASSET_PARAMS.items():
        # Create initial ticker
        ticker = MarketTicker(
            symbol=symbol,
            spot_price=params["spot"],
            perp_price=params["spot"] * 1.0005, # slight premium
            funding_rate=0.0001, # 10 bps
            iv_atm=params["iv_atm"]
        )
        db.add(ticker)
        
        # Generate 30 days of historical daily candles
        current_price = params["spot"]
        vol = params["vol"]
        dt = 1 / 365.0
        
        for i in range(30, 0, -1):
            timestamp = now - datetime.timedelta(days=i)
            # Simple Geometric Brownian Motion step back or forward
            # S_new = S_old * exp((drift - vol^2/2)*dt + vol*sqrt(dt)*Z)
            drift = params["drift"]
            z = random.gauss(0, 1)
            # Step back: we invert the step
            price_change = current_price * (1 + drift * dt + vol * (dt ** 0.5) * z)
            
            # Bound price
            if price_change <= 0:
                price_change = current_price * 0.95
                
            open_p = price_change
            close_p = current_price
            high_p = max(open_p, close_p) * (1 + abs(random.gauss(0, 0.01)))
            low_p = min(open_p, close_p) * (1 - abs(random.gauss(0, 0.01)))
            volume = random.uniform(1e6, 5e7) / current_price # Volume in base asset
            
            candle = HistoricalCandle(
                symbol=symbol,
                timestamp=timestamp.replace(hour=0, minute=0, second=0, microsecond=0),
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=volume
            )
            db.add(candle)
            
            # Slide current price to the open price for the previous candle
            current_price = open_p

    db.commit()
    print("Market data seeded successfully.")

def simulate_market_tick(db: Session, dt_seconds: float = 2.0):
    """Simulates spot price, perp price, and funding rate changes using GBM and basis reversion."""
    tickers = db.query(MarketTicker).all()
    now = datetime.datetime.utcnow()
    
    # Year fraction for step
    dt = dt_seconds / (365.0 * 24.0 * 3600.0)
    
    for ticker in tickers:
        params = ASSET_PARAMS[ticker.symbol]
        vol = params["vol"]
        drift = params["drift"]
        
        # 1. Spot price update (GBM)
        z = random.gauss(0, 1)
        spot_pct_change = drift * dt + vol * (dt ** 0.5) * z
        new_spot = ticker.spot_price * (1 + spot_pct_change)
        
        # Safeguard positive price
        if new_spot <= 0.01:
            new_spot = 0.01
            
        # 2. Perp price update (basis reversion + noise)
        # Perp tends to track spot with a basis that reverts to a mean, but fluctuates
        basis = ticker.perp_price - ticker.spot_price
        target_basis = 0.0005 * new_spot # Long-term perp premium of 5 bps
        basis_reversion_speed = 0.1 # Reverts 10% of the way each tick
        
        basis_change = -basis_reversion_speed * (basis - target_basis) + (new_spot * 0.0002 * random.gauss(0, 1))
        new_basis = basis + basis_change
        
        # Bound basis to +/- 1% of spot
        max_basis = 0.01 * new_spot
        new_basis = max(-max_basis, min(max_basis, new_basis))
        
        new_perp = new_spot + new_basis
        
        # 3. Funding rate update
        # Funding rate = (Perp Price - Spot Price) / Spot Price * scaling_constant
        # scaled to standard 8-hour rate (often ~basis / spot, scaled or clamped)
        # E.g. clamp between -0.1% and 0.1% per 8 hours
        raw_funding = (new_perp - new_spot) / new_spot
        new_funding = max(-0.001, min(0.001, raw_funding))
        
        # 4. IV ATM update (varies slightly randomly)
        iv_z = random.gauss(0, 1)
        new_iv = ticker.iv_atm + 0.005 * iv_z
        new_iv = max(0.15, min(1.80, new_iv)) # Clamp between 15% and 180%
        
        # Update database values
        ticker.spot_price = round(new_spot, 4) if new_spot > 5.0 else round(new_spot, 6)
        ticker.perp_price = round(new_perp, 4) if new_perp > 5.0 else round(new_perp, 6)
        ticker.funding_rate = round(new_funding, 6)
        ticker.iv_atm = round(new_iv, 4)
        ticker.timestamp = now
        
        # 5. Update or insert historical daily candle
        # We find today's daily candle
        today_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        candle = db.query(HistoricalCandle).filter(
            HistoricalCandle.symbol == ticker.symbol,
            HistoricalCandle.timestamp == today_date
        ).first()
        
        if candle:
            # Update existing candle
            candle.close = ticker.spot_price
            candle.high = max(candle.high, ticker.spot_price)
            candle.low = min(candle.low, ticker.spot_price)
            candle.volume += random.uniform(10, 500) / ticker.spot_price
        else:
            # Create a new candle for the new day
            yesterday_close = ticker.spot_price
            candle = HistoricalCandle(
                symbol=ticker.symbol,
                timestamp=today_date,
                open=yesterday_close,
                high=ticker.spot_price,
                low=ticker.spot_price,
                close=ticker.spot_price,
                volume=random.uniform(10, 500) / ticker.spot_price
            )
            db.add(candle)
            
    db.commit()

def get_latest_tickers(db: Session) -> dict:
    """Returns a dictionary of all latest tickers."""
    tickers = db.query(MarketTicker).all()
    return {t.symbol: t for t in tickers}

def get_historical_candles(db: Session, symbol: str, limit: int = 30) -> list:
    """Gets historical candles for a specific symbol, sorted by timestamp ascending."""
    return db.query(HistoricalCandle).filter(
        HistoricalCandle.symbol == symbol
    ).order_by(HistoricalCandle.timestamp.desc()).limit(limit).all()[::-1]
