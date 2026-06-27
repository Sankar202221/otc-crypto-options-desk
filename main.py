import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.wsgi import WSGIMiddleware

from app.config import settings, desk_state
from app.database import init_db, SessionLocal
from app.services.market_data import seed_initial_market_data, simulate_market_tick
from app.services.risk import update_pnl_attribution
from app.services.hedger import run_auto_hedger
from app.dashboard.app import dash_app

# -----------------------------------------------------------------------------
# Background Loops
# -----------------------------------------------------------------------------

async def market_simulation_loop():
    """Background task to simulate live market price updates and record PnL attribution."""
    print("Market simulation loop started.")
    interval = settings.MARKET_DATA_UPDATE_INTERVAL
    while True:
        try:
            with SessionLocal() as db:
                # 1. Update spot, perp prices, funding rates, IVs
                simulate_market_tick(db, interval)
                
                # 2. Update and attribute PnL for each asset
                for symbol in ["BTC", "ETH", "SOL", "ARB"]:
                    update_pnl_attribution(db, symbol, interval)
        except Exception as e:
            print(f"Error in market simulation loop: {e}")
        await asyncio.sleep(interval)

async def auto_hedger_loop():
    """Background task to check portfolio Delta and hedge if necessary."""
    print("Auto-hedger engine loop started.")
    interval = settings.AUTO_HEDGE_INTERVAL
    while True:
        try:
            # Only run if automated hedging is toggled ON in the dashboard settings
            if desk_state.auto_hedge_enabled:
                with SessionLocal() as db:
                    for symbol in ["BTC", "ETH", "SOL", "ARB"]:
                        run_auto_hedger(
                            db, 
                            symbol, 
                            hedge_type=desk_state.hedge_instrument,
                            threshold=desk_state.hedge_threshold
                        )
        except Exception as e:
            print(f"Error in auto-hedger loop: {e}")
        await asyncio.sleep(interval)

# -----------------------------------------------------------------------------
# FastAPI Lifecycle Manager
# -----------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize Database Tables
    init_db()
    
    # 2. Seed Initial Tickers and 30 Days of Historical Candles
    with SessionLocal() as db:
        seed_initial_market_data(db)
        
    # 3. Startup Background Simulation Tasks
    sim_task = asyncio.create_task(market_simulation_loop())
    hedge_task = asyncio.create_task(auto_hedger_loop())
    
    yield
    
    # 4. Cleanup Background Tasks on Shutdown
    sim_task.cancel()
    hedge_task.cancel()
    try:
        await asyncio.gather(sim_task, hedge_task, return_exceptions=True)
    except Exception:
        pass
    print("Shutdown complete.")

# -----------------------------------------------------------------------------
# FastAPI App Definition
# -----------------------------------------------------------------------------

app = FastAPI(
    title="Crypto OTC Options Trading Desk Simulator",
    description="A production-style system to simulate an OTC option trading desk with pricing, volatility surface, automated hedging, risk metrics, and stress testing.",
    version="1.0.0",
    lifespan=lifespan
)

# Root endpoint redirects to the dashboard
@app.get("/")
def read_root():
    return RedirectResponse(url="/dashboard/")

# Mount the WSGI Dash application onto FastAPI under the /dashboard path
app.mount("/dashboard", WSGIMiddleware(dash_app.server))
