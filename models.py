import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from app.database import Base

class MarketTicker(Base):
    __tablename__ = "market_tickers"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True, nullable=False) # BTC, ETH, SOL, ARB
    spot_price = Column(Float, nullable=False)
    perp_price = Column(Float, nullable=False)
    funding_rate = Column(Float, nullable=False) # e.g. 0.0001 (10 bps per 8hr)
    iv_atm = Column(Float, nullable=False) # ATM volatility e.g. 0.60 (60%)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class HistoricalCandle(Base):
    __tablename__ = "historical_candles"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

class Quote(Base):
    __tablename__ = "quotes"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, default="default_client")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    symbol = Column(String, nullable=False)
    structure_type = Column(String, nullable=False) # Vanilla Call, Vanilla Put, Covered Call, Cash-Secured Put, Collar, Custom Payoff
    
    # Store parameters as JSON to handle arbitrary structures
    # E.g. {"strike": 100.0, "expiry_days": 30, "side": "BUY", "quantity": 1000.0}
    parameters = Column(JSON, nullable=False)
    
    price_model = Column(Float, nullable=False) # Theoretical price
    bid = Column(Float, nullable=False)
    ask = Column(Float, nullable=False)
    spread = Column(Float, nullable=False)
    volatility = Column(Float, nullable=False) # Volatility used for pricing
    
    # Greeks (at quote time)
    delta = Column(Float, nullable=False)
    gamma = Column(Float, nullable=False)
    vega = Column(Float, nullable=False)
    theta = Column(Float, nullable=False)
    
    status = Column(String, default="PENDING") # PENDING, BOOKED, EXPIRED

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    symbol = Column(String, nullable=False)
    structure_type = Column(String, nullable=False)
    
    # Store trade parameters (quantity, strike, expiry, client_side)
    # Note: client_side = "BUY" means Desk is Short (-), client_side = "SELL" means Desk is Long (+)
    parameters = Column(JSON, nullable=False)
    
    quantity = Column(Float, nullable=False) # Absolute units of options/structures
    execution_price = Column(Float, nullable=False) # Price option was booked at
    premium = Column(Float, nullable=False) # Premium exchanged (quantity * execution_price)
    client_side = Column(String, nullable=False) # BUY or SELL
    expiry_datetime = Column(DateTime, nullable=False)
    
    status = Column(String, default="ACTIVE") # ACTIVE, CLOSED, EXPIRED

class HedgePosition(Base):
    __tablename__ = "hedge_positions"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    position_type = Column(String, nullable=False) # SPOT or PERP
    quantity = Column(Float, default=0.0) # Positive for Long, Negative for Short
    average_entry_price = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class HedgingLog(Base):
    __tablename__ = "hedging_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    symbol = Column(String, nullable=False)
    action = Column(String, nullable=False) # BUY or SELL
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    asset_type = Column(String, nullable=False) # SPOT or PERP
    slippage = Column(Float, default=0.0)
    fees = Column(Float, default=0.0)
    funding_payment = Column(Float, default=0.0) # Captures perp funding costs if applicable

class PnLRecord(Base):
    __tablename__ = "pnl_records"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Portfolio summary
    total_pnl = Column(Float, default=0.0) # Cumulative PnL
    daily_pnl = Column(Float, default=0.0) # Incremental PnL from last step
    portfolio_value = Column(Float, default=0.0)
    
    # PnL Attribution
    delta_pnl = Column(Float, default=0.0)
    gamma_pnl = Column(Float, default=0.0)
    vega_pnl = Column(Float, default=0.0)
    theta_pnl = Column(Float, default=0.0)
    hedge_costs = Column(Float, default=0.0)
    funding_costs = Column(Float, default=0.0)
    residual_pnl = Column(Float, default=0.0)
    
    # Portfolio Greeks
    portfolio_delta = Column(Float, default=0.0)
    portfolio_gamma = Column(Float, default=0.0)
    portfolio_vega = Column(Float, default=0.0)
    portfolio_theta = Column(Float, default=0.0)
