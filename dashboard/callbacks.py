import datetime
import pandas as pd
import numpy as np
from dash import Input, Output, State, html, dcc, callback, no_update
import plotly.graph_objects as go
from app.database import SessionLocal
from app.models import MarketTicker, Trade, HedgePosition, HedgingLog, PnLRecord, Quote
from app.services.pricing import bsm_price, bsm_greeks, price_structured_product
from app.services.volatility import get_implied_volatility, generate_volatility_surface_grid, calculate_realized_volatility
from app.services.risk import calculate_portfolio_value_and_greeks, run_stress_test, calculate_margin_requirement
from app.services.hedger import execute_hedge_trade

# -----------------------------------------------------------------------------
# Helper: format values
# -----------------------------------------------------------------------------
def fmt_currency(val):
    if val is None:
        return "$-.--"
    return f"${val:,.2f}"

def fmt_greek(val):
    if val is None:
        return "0.0000"
    return f"{val:+.4f}"

# -----------------------------------------------------------------------------
# Callbacks
# -----------------------------------------------------------------------------

# Callback 1: Ticker Updates, Portfolio summary, and active holdings tables
@callback(
    Output("ticker-btc", "children"),
    Output("ticker-eth", "children"),
    Output("ticker-sol", "children"),
    Output("ticker-arb", "children"),
    Output("header-pnl", "children"),
    Output("header-pnl", "style"),
    Output("port-delta", "children"),
    Output("port-gamma", "children"),
    Output("port-vega", "children"),
    Output("port-theta", "children"),
    Output("port-value", "children"),
    Output("port-margin", "children"),
    Output("table-active-options", "children"),
    Output("table-active-hedges", "children"),
    Output("table-hedger-logs", "children"),
    Input("live-interval", "n_intervals"),
    State("rfq-asset", "value")
)
def update_live_metrics(n, selected_symbol):
    with SessionLocal() as db:
        # 1. Fetch Tickers
        tickers = db.query(MarketTicker).all()
        ticker_map = {t.symbol: t for t in tickers}
        
        btc_text = f"${ticker_map['BTC'].spot_price:,.2f}" if "BTC" in ticker_map else "Loading..."
        eth_text = f"${ticker_map['ETH'].spot_price:,.2f}" if "ETH" in ticker_map else "Loading..."
        sol_text = f"${ticker_map['SOL'].spot_price:,.2f}" if "SOL" in ticker_map else "Loading..."
        arb_text = f"${ticker_map['ARB'].spot_price:,.4f}" if "ARB" in ticker_map else "Loading..."
        
        # 2. Fetch Portfolio Risk
        metrics = calculate_portfolio_value_and_greeks(db, selected_symbol)
        
        # Total PnL (from historical records)
        last_pnl_rec = db.query(PnLRecord).order_by(PnLRecord.timestamp.desc()).first()
        total_pnl = last_pnl_rec.total_pnl if last_pnl_rec else 0.0
        
        pnl_text = f"${total_pnl:+,.2f}"
        pnl_style = {"color": "var(--green-glow)" if total_pnl >= 0 else "var(--red-glow)"}
        
        p_delta = fmt_greek(metrics["delta"])
        p_gamma = fmt_greek(metrics["gamma"])
        p_vega = fmt_greek(metrics["vega"])
        p_theta = fmt_greek(metrics["theta"])
        p_val = fmt_currency(metrics["value"])
        
        margin_req = calculate_margin_requirement(db, selected_symbol)
        p_margin = fmt_currency(margin_req)
        
        # 3. Build Active Options Table
        active_trades = db.query(Trade).filter(
            Trade.symbol == selected_symbol, 
            Trade.status == "ACTIVE"
        ).order_by(Trade.timestamp.desc()).all()
        
        if not active_trades:
            options_table = html.Div("No active option positions.", style={"color": "var(--text-muted)", "fontSize": "0.85rem", "padding": "10px"})
        else:
            rows = []
            now = datetime.datetime.utcnow()
            ticker_obj = ticker_map.get(selected_symbol)
            spot = ticker_obj.spot_price if ticker_obj else 1.0
            
            for t in active_trades:
                time_to_exp = (t.expiry_datetime - now).total_seconds() / (24 * 3600)
                side_mult = -1.0 if t.client_side == "BUY" else 1.0
                
                # Approximate PnL: (Current Option Value - Entry Premium)
                # For simplified PnL tracking:
                strike = t.parameters.get("strike", 0.0)
                # Re-price option
                if t.structure_type.lower() in ["vanilla call", "vanilla put", "call", "put"]:
                    opt_type = "Call" if "call" in t.structure_type.lower() else "Put"
                    iv = get_implied_volatility(spot, strike, time_to_exp/365.0, ticker_obj.iv_atm, selected_symbol)
                    current_pr = bsm_price(spot, strike, time_to_exp/365.0, 0.01, iv, opt_type)
                else:
                    iv = get_implied_volatility(spot, strike, time_to_exp/365.0, ticker_obj.iv_atm, selected_symbol)
                    res = price_structured_product(spot, strike, time_to_exp/365.0, 0.01, iv, t.structure_type)
                    current_pr = res["price"]
                
                entry_pr = t.execution_price
                pnl = side_mult * t.quantity * (current_pr - entry_pr)
                pnl_class = "value-up" if pnl >= 0 else "value-down"
                
                rows.append(html.Tr([
                    html.Td(t.structure_type),
                    html.Td("SHORT" if t.client_side == "BUY" else "LONG", style={"fontWeight": "600", "color": "var(--red-glow)" if t.client_side == "BUY" else "var(--green-glow)"}),
                    html.Td(f"{t.quantity:,.0f}"),
                    html.Td(f"${strike:,.2f}"),
                    html.Td(f"{time_to_exp:.1f}d"),
                    html.Td(f"${entry_pr:,.2f}"),
                    html.Td(f"${current_pr:,.2f}"),
                    html.Td(f"${pnl:+,.2f}", className=pnl_class)
                ]))
                
            options_table = html.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Structure"), html.Th("Side"), html.Th("Qty"), 
                        html.Th("Strike"), html.Th("Expiry"), html.Th("Entry Px"), 
                        html.Th("Mark Px"), html.Th("PnL")
                    ])
                ]),
                html.Tbody(rows)
            ], className="desk-table")
            
        # 4. Build Active Hedges Table
        hedges = db.query(HedgePosition).filter(HedgePosition.symbol == selected_symbol).all()
        ticker_obj = ticker_map.get(selected_symbol)
        
        if not hedges or all(h.quantity == 0 for h in hedges):
            hedges_table = html.Div("No active hedge positions.", style={"color": "var(--text-muted)", "fontSize": "0.85rem", "padding": "10px"})
        else:
            rows = []
            for h in hedges:
                if h.quantity == 0:
                    continue
                mark_price = ticker_obj.perp_price if h.position_type == "PERP" else ticker_obj.spot_price
                cost_basis = h.average_entry_price
                pnl = h.quantity * (mark_price - cost_basis)
                pnl_class = "value-up" if pnl >= 0 else "value-down"
                
                rows.append(html.Tr([
                    html.Td(h.position_type),
                    html.Td(f"{h.quantity:+.4f}", style={"fontFamily": "JetBrains Mono"}),
                    html.Td(f"${cost_basis:,.4f}"),
                    html.Td(f"${mark_price:,.4f}"),
                    html.Td(f"${pnl:+,.2f}", className=pnl_class)
                ]))
                
            hedges_table = html.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Asset Type"), html.Th("Hedge Qty"), 
                        html.Th("Avg Entry"), html.Th("Mark Price"), html.Th("PnL")
                    ])
                ]),
                html.Tbody(rows)
            ], className="desk-table")
            
        # 5. Build Recent Hedger Logs Table
        hedge_logs = db.query(HedgingLog).filter(
            HedgingLog.symbol == selected_symbol
        ).order_by(HedgingLog.timestamp.desc()).limit(5).all()
        
        if not hedge_logs:
            logs_table = html.Div("No recent hedging activity.", style={"color": "var(--text-muted)", "fontSize": "0.85rem", "padding": "10px"})
        else:
            rows = []
            for log in hedge_logs:
                rows.append(html.Tr([
                    html.Td(log.timestamp.strftime("%H:%M:%S")),
                    html.Td(log.action, style={"color": "var(--green-glow)" if log.action == "BUY" else "var(--red-glow)", "fontWeight": "600"}),
                    html.Td(log.asset_type),
                    html.Td(f"{log.quantity:,.4f}"),
                    html.Td(f"${log.price:,.4f}"),
                    html.Td(f"${log.fees:,.4f}"),
                    html.Td(f"${log.slippage:,.4f}")
                ]))
                
            logs_table = html.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Time"), html.Th("Action"), html.Th("Type"), 
                        html.Th("Qty"), html.Th("Price"), html.Th("Fee"), html.Th("Slippage")
                    ])
                ]),
                html.Tbody(rows)
            ], className="desk-table")

        return (
            btc_text, eth_text, sol_text, arb_text,
            pnl_text, pnl_style,
            p_delta, p_gamma, p_vega, p_theta, p_val, p_margin,
            options_table, hedges_table, logs_table
        )

# Callback 2: Vol Override Input State
@callback(
    Output("rfq-vol-override-val", "disabled"),
    Input("rfq-vol-override-check", "value")
)
def toggle_vol_override_input(value):
    return "override" not in value

# Callback 3: Generate Option Quote & Payoff Graph
@callback(
    Output("quote-store", "data"),
    Output("quote-bid", "children"),
    Output("quote-ask", "children"),
    Output("quote-mid", "children"),
    Output("quote-spread", "children"),
    Output("quote-iv", "children"),
    Output("quote-delta", "children"),
    Output("quote-gamma", "children"),
    Output("quote-vega", "children"),
    Output("quote-theta", "children"),
    Output("quote-payoff-chart", "figure"),
    Output("btn-book", "disabled"),
    Output("rfq-message", "children"),
    Output("rfq-message", "style"),
    Input("btn-quote", "n_clicks"),
    State("rfq-asset", "value"),
    State("rfq-side", "value"),
    State("rfq-structure", "value"),
    State("rfq-strike", "value"),
    State("rfq-expiry", "value"),
    State("rfq-quantity", "value"),
    State("rfq-vol-override-check", "value"),
    State("rfq-vol-override-val", "value")
)
def generate_desk_quote(n_clicks, symbol, side, structure, strike, expiry_days, quantity, vol_override_check, vol_override_val):
    if n_clicks is None or n_clicks == 0:
        return no_update
        
    if strike is None or strike <= 0 or expiry_days is None or expiry_days <= 0 or quantity is None or quantity <= 0:
        return (
            None, "$-.--", "$-.--", "$-.--", "$-.--", "--.-%", "0.0000", "0.0000", "0.0000", "0.0000",
            go.Figure(), True, "Please enter valid numeric inputs.", {"color": "var(--red-glow)"}
        )
        
    with SessionLocal() as db:
        ticker = db.query(MarketTicker).filter(MarketTicker.symbol == symbol).first()
        if not ticker:
            return no_update
            
        S = ticker.spot_price
        T = expiry_days / 365.0
        r = 0.01 # 1% rate
        
        # 1. Determine volatility to apply
        if "override" in vol_override_check and vol_override_val is not None:
            iv = vol_override_val / 100.0
        else:
            # Query implied volatility surface
            iv = get_implied_volatility(S, strike, T, ticker.iv_atm, symbol)
            
        # 2. Calculate Theoretical Price and Greeks
        is_vanilla = structure.lower() in ["vanilla call", "vanilla put", "call", "put"]
        
        if is_vanilla:
            opt_type = "Call" if "call" in structure.lower() else "Put"
            price = bsm_price(S, strike, T, r, iv, opt_type)
            g = bsm_greeks(S, strike, T, r, iv, opt_type)
            
            # Apply bid-ask spread: e.g. spread = max(1% of spot, 5% of premium)
            # Desk bid = price - spread/2, Desk ask = price + spread/2
            spread = max(0.01 * S * 0.02, 0.04 * price)
            
            # Bid/ask depends on client's action
            # Client wants to BUY option: Client pays Ask (Desk sells). Client wants to SELL option: Client receives Bid (Desk buys).
            # Bid / Ask are relative to desk
            desk_bid = max(0.01, price - 0.5 * spread)
            desk_ask = price + 0.5 * spread
            
            delta = g["delta"]
            gamma = g["gamma"]
            vega = g["vega"]
            theta = g["theta"]
        else:
            # Structured Product (Covered Call, Collar, etc.) via Monte Carlo
            res = price_structured_product(S, strike, T, r, iv, structure)
            price = res["price"]
            desk_bid = res["bid"]
            desk_ask = res["ask"]
            spread = res["spread"]
            
            delta = res["delta"]
            gamma = res["gamma"]
            vega = res["vega"]
            theta = res["theta"]
            
        # Format returns
        bid_str = f"${desk_bid:,.2f}"
        ask_str = f"${desk_ask:,.2f}"
        mid_str = f"${price:,.2f}"
        spread_str = f"${spread:,.2f}"
        iv_str = f"{iv*100:.1f}%"
        
        d_str = fmt_greek(delta)
        g_str = fmt_greek(gamma)
        v_str = fmt_greek(vega)
        t_str = fmt_greek(theta / 365.0)
        
        # 3. Generate Payoff Diagram
        spot_range = np.linspace(0.5 * S, 1.5 * S, 50)
        payoffs = []
        
        for st in spot_range:
            if is_vanilla:
                opt_type = "Call" if "call" in structure.lower() else "Put"
                payoffs.append(max(0.0, st - strike) if opt_type == "Call" else max(0.0, strike - st))
            else:
                # Custom payoffs
                from app.services.pricing import calculate_structure_payoff
                payoffs.append(calculate_structure_payoff(S, st, strike, structure))
                
        # If client bought, desk is short (flip payoff for desk position)
        client_mult = 1.0 if side == "BUY" else -1.0 # Client perspective payoff
        fig_payoffs = [p * client_mult * quantity for p in payoffs]
        
        # Interactive chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=spot_range, y=fig_payoffs, 
            mode='lines', name='Payoff at Expiry',
            line=dict(color='#58a6ff', width=3)
        ))
        
        # Add current spot line
        fig.add_vline(x=S, line_dash="dash", line_color="#8b949e", annotation_text="Current Spot", annotation_position="top left")
        # Add strike line
        fig.add_vline(x=strike, line_dash="dot", line_color="#f85149", annotation_text="Strike", annotation_position="top right")
        
        fig.update_layout(
            margin=dict(l=10, r=10, t=25, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#c9d1d9', size=9),
            xaxis=dict(showgrid=True, gridcolor='rgba(48,54,61,0.3)', title="Spot Price"),
            yaxis=dict(showgrid=True, gridcolor='rgba(48,54,61,0.3)', title="Payoff ($)"),
            showlegend=False,
            height=200
        )
        
        # Store quote parameters for booking
        quote_data = {
            "symbol": symbol,
            "side": side,
            "structure": structure,
            "strike": strike,
            "expiry_days": expiry_days,
            "quantity": quantity,
            "volatility": iv,
            "execution_price": desk_ask if side == "BUY" else desk_bid, # client buys desk's ask, client sells to desk's bid
            "delta": delta,
            "gamma": gamma,
            "vega": vega,
            "theta": theta
        }
        
        msg = f"Quote calculated! Client {side} price: " + (f"${desk_ask:,.2f}" if side == "BUY" else f"${desk_bid:,.2f}")
        
        return (
            quote_data, bid_str, ask_str, mid_str, spread_str, iv_str,
            d_str, g_str, v_str, t_str, fig, False, msg, {"color": "var(--green-glow)"}
        )

# Callback 4: Book Trade
@callback(
    Output("book-message", "children"),
    Output("book-message", "style"),
    Input("btn-book", "n_clicks"),
    State("quote-store", "data"),
    prevent_initial_call=True
)
def book_otc_trade(n_clicks, quote_data):
    if n_clicks is None or not quote_data:
        return no_update
        
    with SessionLocal() as db:
        # Create quote record
        q_record = Quote(
            symbol=quote_data["symbol"],
            structure_type=quote_data["structure"],
            parameters={
                "strike": quote_data["strike"],
                "expiry_days": quote_data["expiry_days"],
                "side": quote_data["side"],
                "quantity": quote_data["quantity"]
            },
            price_model=quote_data["execution_price"],
            bid=quote_data["execution_price"] * 0.99, # placeholder
            ask=quote_data["execution_price"] * 1.01,
            spread=quote_data["execution_price"] * 0.02,
            volatility=quote_data["volatility"],
            delta=quote_data["delta"],
            gamma=quote_data["gamma"],
            vega=quote_data["vega"],
            theta=quote_data["theta"],
            status="BOOKED"
        )
        db.add(q_record)
        db.flush() # gets ID
        
        expiry_datetime = datetime.datetime.utcnow() + datetime.timedelta(days=quote_data["expiry_days"])
        
        # Create Trade record
        t_record = Trade(
            quote_id=q_record.id,
            symbol=quote_data["symbol"],
            structure_type=quote_data["structure"],
            parameters={
                "strike": quote_data["strike"],
                "expiry_days": quote_data["expiry_days"]
            },
            quantity=quote_data["quantity"],
            execution_price=quote_data["execution_price"],
            premium=quote_data["quantity"] * quote_data["execution_price"],
            client_side=quote_data["side"],
            expiry_datetime=expiry_datetime,
            status="ACTIVE"
        )
        db.add(t_record)
        db.commit()
        
        side_label = "Short" if quote_data["side"] == "BUY" else "Long"
        msg = f"Trade Booked! Desk is {side_label} {quote_data['quantity']:,.0f} {quote_data['structure']} contracts."
        return msg, {"color": "var(--green-glow)", "fontWeight": "bold", "marginTop": "10px"}

# Callback 5: Force Manual Rebalance
@callback(
    Output("manual-hedge-message", "children"),
    Input("btn-manual-hedge", "n_clicks"),
    State("rfq-asset", "value"),
    State("hedger-instrument", "value"),
    prevent_initial_call=True
)
def manual_rebalance(n_clicks, symbol, instrument):
    if n_clicks is None:
        return no_update
        
    with SessionLocal() as db:
        # Calculate Delta
        metrics = calculate_portfolio_value_and_greeks(db, symbol)
        net_delta = metrics["delta"]
        
        if abs(net_delta) < 0.005:
            return "Portfolio is already delta neutral (net delta < 0.005)."
            
        qty_to_trade = -net_delta
        res = execute_hedge_trade(db, symbol, qty_to_trade, instrument)
        
        if res:
            action = res["action"]
            qty = res["quantity"]
            price = res["price"]
            return f"Rebalance Complete! {action} {qty:.4f} {symbol} {instrument} at ${price:,.2f}."
        else:
            return "Rebalance failed."

# Callback 6: Volatility Surface (3D) and Smile (2D) Charts + PnL Waterfall
@callback(
    Output("vol-smile-chart", "figure"),
    Output("vol-surface-chart", "figure"),
    Output("pnl-attribution-chart", "figure"),
    Input("desk-tabs", "value"),
    Input("rfq-asset", "value"),
    Input("live-interval", "n_intervals")
)
def render_tab_charts(active_tab, symbol, n):
    with SessionLocal() as db:
        ticker = db.query(MarketTicker).filter(MarketTicker.symbol == symbol).first()
        if not ticker:
            return no_update, no_update, no_update
            
        spot = ticker.spot_price
        atm_vol = ticker.iv_atm
        
        # 1. Smile Chart (IV vs Strike for different Expiries)
        strikes = np.linspace(0.80 * spot, 1.20 * spot, 30)
        tenors = [7/365.0, 30/365.0, 90/365.0] # 1w, 1m, 3m
        tenor_labels = ["7 Days", "30 Days", "90 Days"]
        colors = ["#58a6ff", "#3fb950", "#bc8cff"]
        
        fig_smile = go.Figure()
        for t, label, color in zip(tenors, tenor_labels, colors):
            ivs = [get_implied_volatility(spot, k, t, atm_vol, symbol) * 100 for k in strikes]
            fig_smile.add_trace(go.Scatter(
                x=strikes, y=ivs, mode="lines", name=label,
                line=dict(color=color, width=2.5)
            ))
        fig_smile.add_vline(x=spot, line_dash="dash", line_color="#8b949e", annotation_text="Spot")
        fig_smile.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#c9d1d9', size=9),
            xaxis=dict(showgrid=True, gridcolor='rgba(48,54,61,0.2)', title="Strike Price"),
            yaxis=dict(showgrid=True, gridcolor='rgba(48,54,61,0.2)', title="Implied Volatility (%)"),
            legend=dict(x=0.01, y=0.99, bgcolor='rgba(13,17,23,0.8)', bordercolor='var(--border-color)', borderwidth=1),
            height=250
        )
        
        # 2. 3D Surface Chart
        grid = generate_volatility_surface_grid(symbol, spot, atm_vol, num_strikes=15, num_tenors=10)
        
        fig_surface = go.Figure(data=[go.Surface(
            x=grid["strikes"],
            y=grid["tenors"],
            z=np.array(grid["ivs"]) * 100,
            colorscale="Viridis",
            colorbar=dict(title="IV %", thickness=15, len=0.6, tickfont=dict(color='#c9d1d9'))
        )])
        fig_surface.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#c9d1d9', size=9),
            scene=dict(
                xaxis=dict(title="Strike", backgroundcolor="rgba(0,0,0,0)", gridcolor='rgba(48,54,61,0.3)', showbackground=True),
                yaxis=dict(title="Days to Expiry", backgroundcolor="rgba(0,0,0,0)", gridcolor='rgba(48,54,61,0.3)', showbackground=True),
                zaxis=dict(title="IV %", backgroundcolor="rgba(0,0,0,0)", gridcolor='rgba(48,54,61,0.3)', showbackground=True),
            ),
            height=250
        )
        
        # 3. PnL Attribution Waterfall Chart
        # Query latest PnLRecord
        latest_rec = db.query(PnLRecord).order_by(PnLRecord.timestamp.desc()).first()
        
        fig_pnl = go.Figure()
        if latest_rec:
            # Waterfall showing PnL split
            components = ["Delta PnL", "Gamma PnL", "Vega PnL", "Theta PnL", "Hedge Costs", "Funding Costs", "Residual PnL"]
            values = [
                latest_rec.delta_pnl,
                latest_rec.gamma_pnl,
                latest_rec.vega_pnl,
                latest_rec.theta_pnl,
                -latest_rec.hedge_costs, # cost is negative for PnL
                -latest_rec.funding_costs,
                latest_rec.residual_pnl
            ]
            
            fig_pnl.add_trace(go.Waterfall(
                name="PnL Attribution",
                orientation="v",
                measure=["relative"] * len(components) + ["total"],
                x=components + ["Net PnL"],
                textposition="outside",
                text=[f"${v:+,.1f}" for v in values] + [f"${latest_rec.daily_pnl:+,.1f}"],
                y=values + [latest_rec.daily_pnl],
                connector={"line": {"color": "rgb(63, 63, 63)"}},
                decreasing={"marker": {"color": "#f85149"}},
                increasing={"marker": {"color": "#3fb950"}},
                totals={"marker": {"color": "#58a6ff"}}
            ))
            
        fig_pnl.update_layout(
            margin=dict(l=10, r=10, t=25, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#c9d1d9', size=9),
            xaxis=dict(showgrid=True, gridcolor='rgba(48,54,61,0.2)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(48,54,61,0.2)', title="PnL ($)"),
            height=220
        )

        return fig_smile, fig_surface, fig_pnl

# Callback 7: Stress Testing Panel Callbacks (Quick scenarios & sliders)
@callback(
    Output("slider-shock-spot", "value"),
    Output("slider-shock-iv", "value"),
    Output("label-shock-spot", "children"),
    Output("label-shock-iv", "children"),
    Output("stress-results-panel", "children"),
    Input("btn-stress-crash", "n_clicks"),
    Input("btn-stress-pump", "n_clicks"),
    Input("btn-stress-iv", "n_clicks"),
    Input("btn-stress-liq", "n_clicks"),
    Input("btn-stress-gap", "n_clicks"),
    Input("slider-shock-spot", "value"),
    Input("slider-shock-iv", "value"),
    State("rfq-asset", "value"),
    Input("live-interval", "n_intervals")
)
def handle_stress_testing(n_crash, n_pump, n_iv, n_liq, n_gap, spot_val, iv_val, symbol, n_ticks):
    # Determine triggering input
    from dash import callback_context
    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else ""
    
    # 1. Adjust sliders based on quick scenarios
    if triggered_id == "btn-stress-crash":
        spot_val = -0.20
        iv_val = 0.0
    elif triggered_id == "btn-stress-pump":
        spot_val = 0.30
        iv_val = 0.0
    elif triggered_id == "btn-stress-iv":
        spot_val = 0.0
        iv_val = 1.00 # IV doubles (+100%)
    elif triggered_id == "btn-stress-liq":
        spot_val = 0.0
        iv_val = 0.0
        # In a liquidity freeze, bid-ask spreads widen and slippage increases.
        # We can handle this by adding a message or simulating it.
    elif triggered_id == "btn-stress-gap":
        spot_val = -0.30
        iv_val = 0.50 # gap down spot, vol spikes
        
    spot_text = f"{spot_val:+.0%}"
    iv_text = f"{iv_val:+.0%}"
    
    # 2. Run stress test service
    with SessionLocal() as db:
        res = run_stress_test(db, symbol, spot_val, iv_val)
        
    if not res:
        results_panel = html.Div("No active positions to stress test.", style={"color": "var(--text-muted)", "fontSize": "0.85rem"})
    else:
        pnl_imp = res["pnl_impact"]
        pnl_class = "value-up" if pnl_imp >= 0 else "value-down"
        
        # Build results UI
        results_panel = html.Div([
            html.Div([
                html.Div([
                    html.Span("Shocked Portfolio Value: "),
                    html.Span(f"${res['new_portfolio_value']:,.2f}", style={"fontWeight": "600"})
                ], style={"marginBottom": "8px"}),
                html.Div([
                    html.Span("Projected PnL Impact: "),
                    html.Span(f"${pnl_imp:+,.2f}", className=pnl_class, style={"fontSize": "1.1rem", "fontWeight": "bold"})
                ], style={"marginBottom": "15px", "borderBottom": "1px dashed var(--border-color)", "paddingBottom": "8px"}),
                
                # New Greeks under stress
                html.Label("Shocked Greeks Exposures", className="form-label"),
                html.Div([
                    html.Div([
                        html.Div("Shock Delta", className="metric-title"),
                        html.Div(f"{res['new_delta']:.4f}", className="metric-value", style={"fontSize": "1rem"})
                    ], className="metric-card"),
                    html.Div([
                        html.Div("Shock Gamma", className="metric-title"),
                        html.Div(f"{res['new_gamma']:.4f}", className="metric-value", style={"fontSize": "1rem"})
                    ], className="metric-card"),
                    html.Div([
                        html.Div("Shock Vega", className="metric-title"),
                        html.Div(f"{res['new_vega']:.4f}", className="metric-value", style={"fontSize": "1rem"})
                    ], className="metric-card"),
                    html.Div([
                        html.Div("Shock Theta", className="metric-title"),
                        html.Div(f"{res['new_theta']:.4f}", className="metric-value", style={"fontSize": "1rem"})
                    ], className="metric-card")
                ], className="metrics-row", style={"marginBottom": "15px"}),
                
                html.Div([
                    html.Span("Hedge Rebalance Required: ", style={"color": "var(--text-muted)"}),
                    html.Span(f"{res['required_hedge_rebalance']:+.4f} {symbol}", style={"fontWeight": "bold", "color": "var(--accent-color)"})
                ], style={"fontSize": "0.85rem", "background": "rgba(255,255,255,0.02)", "padding": "8px", "borderRadius": "6px", "border": "1px solid var(--border-color)"})
            ])
        ])
        
    return spot_val, iv_val, spot_text, iv_text, results_panel

# Callback 8: Sync Hedger Settings from UI to in-memory desk_state
@callback(
    Output("btn-manual-hedge", "style"), # dummy output to satisfy Dash callback requirements
    Input("hedger-enabled", "value"),
    Input("hedger-instrument", "value"),
    Input("hedger-threshold", "value")
)
def sync_hedger_settings(enabled, instrument, threshold):
    from app.config import desk_state
    desk_state.auto_hedge_enabled = (enabled == "on")
    desk_state.hedge_instrument = instrument
    desk_state.hedge_threshold = threshold
    return no_update

# Callback 9: Handle Applying for Job Role
@callback(
    Output("apply-role-message", "children"),
    Output("apply-role-message", "style"),
    Input("btn-apply-role", "n_clicks"),
    prevent_initial_call=True
)
def handle_apply_role(n_clicks):
    if n_clicks is None or n_clicks == 0:
        return no_update
    return (
        "Application submitted! Our recruitment team will review your profile shortly.",
        {"color": "var(--green-glow)", "fontWeight": "bold"}
    )


