import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import MarketTicker, Trade, HedgePosition, HedgingLog
from app.services.hedger import execute_hedge_trade, run_auto_hedger
from app.services.risk import calculate_portfolio_value_and_greeks

@pytest.fixture(name="db_session")
def fixture_db_session():
    """Create a temporary in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Seed initial test market data
    sol_ticker = MarketTicker(
        symbol="SOL",
        spot_price=150.0,
        perp_price=150.1,
        funding_rate=0.0001,
        iv_atm=0.75
    )
    db.add(sol_ticker)
    db.commit()
    
    yield db
    
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_execute_hedge_trade(db_session):
    """Verify that hedge trades update HedgePosition quantities and log transactions."""
    # 1. Place a BUY hedge trade of 10 SOL Spot
    res = execute_hedge_trade(db_session, "SOL", 10.0, "SPOT")
    assert res["action"] == "BUY"
    assert res["quantity"] == 10.0
    assert res["type"] == "SPOT"
    assert res["price"] > 150.0 # Price + slippage
    
    # 2. Check position was created in database
    pos = db_session.query(HedgePosition).filter(HedgePosition.symbol == "SOL", HedgePosition.position_type == "SPOT").first()
    assert pos is not None
    assert pos.quantity == 10.0
    assert pos.average_entry_price == res["price"]
    
    # 3. Add to the hedge: BUY another 5 SOL Spot
    res2 = execute_hedge_trade(db_session, "SOL", 5.0, "SPOT")
    assert pos.quantity == 15.0
    
    # 4. Reduce position: SELL 8 SOL Spot
    res3 = execute_hedge_trade(db_session, "SOL", -8.0, "SPOT")
    assert pos.quantity == 7.0
    
    # 5. Check log entries
    logs = db_session.query(HedgingLog).filter(HedgingLog.symbol == "SOL").all()
    assert len(logs) == 3

def test_run_auto_hedger(db_session):
    """Verify that auto-hedging triggers when Delta exceeds threshold."""
    # 1. Portfolio has no options, so net delta = 0.
    # Auto-hedger should do nothing
    res = run_auto_hedger(db_session, "SOL", "SPOT", threshold=0.05)
    assert res == {}
    
    # 2. Let's add a short call option to create a negative delta exposure
    # Desk is Short Call = Client buys Call. Client side BUY.
    # Expiry 30 days, Strike 150.0. Quantity 100 options.
    import datetime
    expiry = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    
    trade = Trade(
        symbol="SOL",
        structure_type="Vanilla Call",
        parameters={"strike": 150.0, "expiry_days": 30},
        quantity=100.0,
        execution_price=10.0,
        premium=1000.0,
        client_side="BUY", # Desk is SHORT Call
        expiry_datetime=expiry,
        status="ACTIVE"
    )
    db_session.add(trade)
    db_session.commit()
    
    # 3. Calculate portfolio Greeks. Since desk is short 100 calls, delta should be negative
    # (Call delta is ~0.50, so portfolio delta should be roughly -50)
    metrics = calculate_portfolio_value_and_greeks(db_session, "SOL")
    assert metrics["delta"] < -10.0
    initial_delta = metrics["delta"]
    
    # 4. Run auto-hedger. Since |Delta| > 0.05 threshold, it should buy spot to delta hedge
    hedge_res = run_auto_hedger(db_session, "SOL", "SPOT", threshold=0.05)
    assert hedge_res != {}
    assert hedge_res["action"] == "BUY"
    assert pytest.approx(hedge_res["quantity"], abs=1e-3) == -initial_delta
    
    # 5. Re-evaluate portfolio Greeks. Net delta should now be zero (or near zero due to float/slippage)
    post_metrics = calculate_portfolio_value_and_greeks(db_session, "SOL")
    assert abs(post_metrics["delta"]) < 0.01
