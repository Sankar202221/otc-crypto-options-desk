from dash import dcc, html

def get_layout():
    return html.Div([
        # 1. Header Row
        html.Div([
            html.Div([
                html.Img(src="/dashboard/assets/grt_logo.png", style={
                    "width": "36px",
                    "height": "36px",
                    "marginRight": "12px",
                    "borderRadius": "6px",
                    "border": "1px solid var(--border-color)",
                    "boxShadow": "0 0 10px rgba(0, 210, 255, 0.2)"
                }),
                html.H1("QUANT OTC OPTIONS DESK", className="header-title"),
                html.Span("LIVE DESK SIMULATOR (GRT MODEL)", style={
                    "fontSize": "0.75rem", 
                    "color": "var(--accent-color)", 
                    "marginLeft": "15px",
                    "fontWeight": "600",
                    "letterSpacing": "1px",
                    "border": "1px solid var(--accent-color)",
                    "padding": "2px 8px",
                    "borderRadius": "4px"
                })
            ], className="header-title-container"),
            
            # Live Tickers
            html.Div([
                html.Div([
                    html.Span("BTC", className="ticker-symbol"),
                    html.Span("Loading...", id="ticker-btc", className="ticker-price")
                ], className="ticker-box"),
                html.Div([
                    html.Span("ETH", className="ticker-symbol"),
                    html.Span("Loading...", id="ticker-eth", className="ticker-price")
                ], className="ticker-box"),
                html.Div([
                    html.Span("SOL", className="ticker-symbol"),
                    html.Span("Loading...", id="ticker-sol", className="ticker-price")
                ], className="ticker-box"),
                html.Div([
                    html.Span("ARB", className="ticker-symbol"),
                    html.Span("Loading...", id="ticker-arb", className="ticker-price")
                ], className="ticker-box"),
                
                # Portfolio PnL Ticker
                html.Div([
                    html.Span("DESK TOTAL PNL", className="ticker-symbol", style={"color": "white"}),
                    html.Span("$0.00", id="header-pnl", className="ticker-price", style={"color": "var(--green-glow)"})
                ], className="ticker-box", style={"background": "rgba(63, 185, 80, 0.1)", "borderColor": "var(--green-glow)"})
            ], className="ticker-panel")
        ], className="dashboard-header"),
        
        # 2. Main Dashboard Grid
        html.Div([
            
            # LEFT COLUMN: RFQ FORM
            html.Div([
                html.H3("Client RFQ Portal", style={"marginTop": 0, "borderBottom": "1px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.Div([
                    html.Label("Underlying Asset", className="form-label"),
                    dcc.Dropdown(
                        id="rfq-asset",
                        options=[
                            {"label": "BTC (Bitcoin)", "value": "BTC"},
                            {"label": "ETH (Ethereum)", "value": "ETH"},
                            {"label": "SOL (Solana)", "value": "SOL"},
                            {"label": "ARB (Arbitrum)", "value": "ARB"}
                        ],
                        value="SOL",
                        clearable=False,
                        className="dash-dropdown"
                    )
                ], style={"marginBottom": "15px"}),
                
                html.Div([
                    html.Label("Option side (Client)", className="form-label"),
                    dcc.RadioItems(
                        id="rfq-side",
                        options=[
                            {"label": "Client BUYS (Desk Short)", "value": "BUY"},
                            {"label": "Client SELLS (Desk Long)", "value": "SELL"}
                        ],
                        value="BUY",
                        labelStyle={"display": "inline-block", "marginRight": "20px", "fontSize": "0.85rem"},
                        style={"marginTop": "5px"}
                    )
                ], style={"marginBottom": "15px"}),
                
                html.Div([
                    html.Label("Product Structure", className="form-label"),
                    dcc.Dropdown(
                        id="rfq-structure",
                        options=[
                            {"label": "Vanilla Call", "value": "Vanilla Call"},
                            {"label": "Vanilla Put", "value": "Vanilla Put"},
                            {"label": "Covered Call (Spot + Short Call)", "value": "Covered Call"},
                            {"label": "Cash-Secured Put (Short Put + Cash)", "value": "Cash-Secured Put"},
                            {"label": "Collar (Spot + Put - Call)", "value": "Collar"},
                            {"label": "Custom Payoff (Knock-out Straddle)", "value": "Custom Payoff"}
                        ],
                        value="Vanilla Call",
                        clearable=False,
                        className="dash-dropdown"
                    )
                ], style={"marginBottom": "15px"}),
                
                html.Div([
                    html.Label("Strike Price ($)", className="form-label"),
                    dcc.Input(id="rfq-strike", type="number", value=150.0, step=0.1, className="form-input")
                ], style={"marginBottom": "15px"}),
                
                html.Div([
                    html.Label("Expiry (Tenor in Days)", className="form-label"),
                    dcc.Input(id="rfq-expiry", type="number", value=30, min=1, max=365, className="form-input")
                ], style={"marginBottom": "15px"}),
                
                html.Div([
                    html.Label("Option Quantity", className="form-label"),
                    dcc.Input(id="rfq-quantity", type="number", value=1000.0, step=1, className="form-input")
                ], style={"marginBottom": "15px"}),
                
                html.Div([
                    html.Label("Volatility Input", className="form-label"),
                    html.Div([
                        dcc.Checklist(
                            id="rfq-vol-override-check",
                            options=[{"label": "Override", "value": "override"}],
                            value=[],
                            style={"display": "inline-block", "marginRight": "10px", "fontSize": "0.85rem"}
                        ),
                        dcc.Input(
                            id="rfq-vol-override-val",
                            type="number",
                            value=75.0,
                            min=5.0,
                            max=300.0,
                            step=1,
                            disabled=True,
                            style={"width": "100px", "display": "inline-block"},
                            className="form-input"
                        ),
                        html.Span(" %", style={"fontSize": "0.85rem", "color": "var(--text-muted)"})
                    ], style={"display": "flex", "alignItems": "center"})
                ], style={"marginBottom": "20px"}),
                
                html.Button("Calculate OTC Quote", id="btn-quote", className="desk-btn", style={"width": "100%"}),
                
                # RFQ Notification message
                html.Div(id="rfq-message", style={"marginTop": "15px", "fontSize": "0.85rem"})
            ], className="desk-card"),
            
            # CENTER COLUMN: LIVE QUOTE DETAILS & GREEKS
            html.Div([
                html.H3("OTC Desk Quote", style={"marginTop": 0, "borderBottom": "1px solid var(--border-color)", "paddingBottom": "10px"}),
                
                # Bid / Ask Premium Displays
                html.Div([
                    html.Div([
                        html.Span("DESK BID (Client Sells)", style={"fontSize": "0.75rem", "color": "var(--text-muted)", "fontWeight": "600"}),
                        html.Span("$-.--", id="quote-bid", style={"fontFamily": "JetBrains Mono", "fontSize": "1.75rem", "fontWeight": "700", "color": "var(--green-glow)"})
                    ], className="metric-card", style={"borderColor": "rgba(63, 185, 80, 0.3)"}),
                    
                    html.Div([
                        html.Span("DESK ASK (Client Buys)", style={"fontSize": "0.75rem", "color": "var(--text-muted)", "fontWeight": "600"}),
                        html.Span("$-.--", id="quote-ask", style={"fontFamily": "JetBrains Mono", "fontSize": "1.75rem", "fontWeight": "700", "color": "var(--red-glow)"})
                    ], className="metric-card", style={"borderColor": "rgba(248, 81, 73, 0.3)"})
                ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "15px", "marginBottom": "20px"}),
                
                # Mid, Spread, Vol details
                html.Div([
                    html.Div([
                        html.Span("Theoretical Price: ", style={"color": "var(--text-muted)"}),
                        html.Span("$-.--", id="quote-mid", style={"fontWeight": "600", "fontFamily": "JetBrains Mono"})
                    ]),
                    html.Div([
                        html.Span("Charged Spread: ", style={"color": "var(--text-muted)"}),
                        html.Span("$-.--", id="quote-spread", style={"fontWeight": "600", "fontFamily": "JetBrains Mono"})
                    ]),
                    html.Div([
                        html.Span("IV Applied: ", style={"color": "var(--text-muted)"}),
                        html.Span("--.-%", id="quote-iv", style={"fontWeight": "600", "fontFamily": "JetBrains Mono"})
                    ])
                ], style={"fontSize": "0.85rem", "marginBottom": "20px", "display": "flex", "justifyContent": "space-between", "background": "rgba(255,255,255,0.02)", "padding": "10px", "borderRadius": "6px", "border": "1px solid var(--border-color)"}),
                
                # Option Greeks cards
                html.Label("Option Greeks (Per Unit)", className="form-label"),
                html.Div([
                    html.Div([
                        html.Div("Delta (Δ)", className="metric-title"),
                        html.Div("0.0000", id="quote-delta", className="metric-value")
                    ], className="metric-card"),
                    html.Div([
                        html.Div("Gamma (Γ)", className="metric-title"),
                        html.Div("0.0000", id="quote-gamma", className="metric-value")
                    ], className="metric-card"),
                    html.Div([
                        html.Div("Vega (V)", className="metric-title"),
                        html.Div("0.0000", id="quote-vega", className="metric-value")
                    ], className="metric-card"),
                    html.Div([
                        html.Div("Theta (Θ)", className="metric-title"),
                        html.Div("0.0000", id="quote-theta", className="metric-value")
                    ], className="metric-card")
                ], className="metrics-row"),
                
                # Payoff Chart
                html.Div([
                    dcc.Graph(
                        id="quote-payoff-chart", 
                        config={"displayModeBar": False},
                        style={"height": "200px"}
                    )
                ], style={"marginBottom": "20px", "border": "1px solid var(--border-color)", "borderRadius": "8px", "overflow": "hidden"}),
                
                # Book Button
                html.Button("Book OTC Option Trade", id="btn-book", disabled=True, className="desk-btn desk-btn-success", style={"width": "100%"}),
                html.Div(id="book-message", style={"marginTop": "10px", "fontSize": "0.85rem", "textAlign": "center"})
            ], className="desk-card"),
            
            # RIGHT COLUMN: DESK RISK & HEDGING CONTROL
            html.Div([
                html.H3("Active Desk Risk & Hedging", style={"marginTop": 0, "borderBottom": "1px solid var(--border-color)", "paddingBottom": "10px"}),
                
                # Live Portfolio Greeks
                html.Label("Live Portfolio Greeks (Option + Hedges)", className="form-label"),
                html.Div([
                    html.Div([
                        html.Div("Net Delta (Δ)", className="metric-title"),
                        html.Div("0.0000", id="port-delta", className="metric-value")
                    ], className="metric-card"),
                    html.Div([
                        html.Div("Net Gamma (Γ)", className="metric-title"),
                        html.Div("0.0000", id="port-gamma", className="metric-value")
                    ], className="metric-card"),
                    html.Div([
                        html.Div("Net Vega (V)", className="metric-title"),
                        html.Div("0.0000", id="port-vega", className="metric-value")
                    ], className="metric-card"),
                    html.Div([
                        html.Div("Net Theta (Θ)", className="metric-title"),
                        html.Div("0.0000", id="port-theta", className="metric-value")
                    ], className="metric-card")
                ], className="metrics-row"),
                
                # Portfolio Margins
                html.Div([
                    html.Div([
                        html.Span("Portfolio Value: ", style={"color": "var(--text-muted)", "fontSize": "0.85rem"}),
                        html.Span("$0.00", id="port-value", style={"fontWeight": "700", "fontFamily": "JetBrains Mono"})
                    ]),
                    html.Div([
                        html.Span("SPAN Margin Req: ", style={"color": "var(--text-muted)", "fontSize": "0.85rem"}),
                        html.Span("$0.00", id="port-margin", style={"fontWeight": "700", "fontFamily": "JetBrains Mono"})
                    ])
                ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "20px", "background": "rgba(255,255,255,0.02)", "padding": "10px", "borderRadius": "6px", "border": "1px solid var(--border-color)"}),
                
                # Automated Delta Hedger
                html.H4("Automated Delta Hedging Engine", style={"borderBottom": "1px solid var(--border-color)", "paddingBottom": "5px"}),
                
                html.Div([
                    html.Div([
                        html.Span("Auto-Hedger Enabled", style={"fontSize": "0.85rem", "fontWeight": "600"}),
                        dcc.RadioItems(
                            id="hedger-enabled",
                            options=[
                                {"label": "ON", "value": "on"},
                                {"label": "OFF", "value": "off"}
                            ],
                            value="on",
                            labelStyle={"display": "inline-block", "marginLeft": "15px", "fontSize": "0.85rem"}
                        )
                    ], className="switch-container"),
                    
                    html.Div([
                        html.Label("Hedge Instrument", className="form-label"),
                        dcc.Dropdown(
                            id="hedger-instrument",
                            options=[
                                {"label": "Spot Markets (Physical)", "value": "SPOT"},
                                {"label": "Perpetual Contracts (Derivatives)", "value": "PERP"}
                            ],
                            value="SPOT",
                            clearable=False,
                            className="dash-dropdown"
                        )
                    ], style={"marginBottom": "15px"}),
                    
                    html.Div([
                        html.Label("Rebalance Threshold (Delta Drift)", className="form-label"),
                        dcc.Slider(
                            id="hedger-threshold",
                            min=0.01,
                            max=0.20,
                            step=0.01,
                            value=0.05,
                            marks={0.01: "0.01", 0.05: "0.05", 0.10: "0.10", 0.15: "0.15", 0.20: "0.20"},
                            tooltip={"placement": "bottom", "always_visible": True}
                        )
                    ], style={"marginBottom": "25px"}),
                    
                    html.Button("Force Manual Rebalance", id="btn-manual-hedge", className="desk-btn desk-btn-secondary", style={"width": "100%"}),
                    html.Div(id="manual-hedge-message", style={"marginTop": "10px", "fontSize": "0.85rem", "textAlign": "center"})
                ], style={"background": "rgba(88, 166, 255, 0.03)", "border": "1px solid rgba(88, 166, 255, 0.1)", "padding": "15px", "borderRadius": "8px"})
            ], className="desk-card")
            
        ], className="dashboard-grid"),
        
        # 3. Bottom Grid: Volatility, PnL Attribution, Stress Test
        html.Div([
            
            # BOTTOM LEFT: ACTIVE POSITIONS, VOLATILITY & PNL ATTRIBUTION TABS
            html.Div([
                dcc.Tabs(id="desk-tabs", value="tab-positions", children=[
                    
                    # Tab 1: Current Positions
                    dcc.Tab(label="ACTIVE POSITIONS", value="tab-positions", style={"backgroundColor": "#0d1117", "color": "var(--text-muted)"}, selected_style={"backgroundColor": "#161b22", "color": "white", "borderTop": "2px solid var(--accent-color)"}, children=[
                        html.Div([
                            html.H4("Active Client Option Options", style={"marginTop": "15px"}),
                            html.Div(id="table-active-options"),
                            
                            html.H4("Hedge Positions (Spot & Perp)", style={"marginTop": "20px"}),
                            html.Div(id="table-active-hedges")
                        ], style={"padding": "10px"})
                    ]),
                    
                    # Tab 2: Volatility Surface (3D) & Smile (2D)
                    dcc.Tab(label="VOLATILITY ENGINE", value="tab-volatility", style={"backgroundColor": "#0d1117", "color": "var(--text-muted)"}, selected_style={"backgroundColor": "#161b22", "color": "white", "borderTop": "2px solid var(--accent-color)"}, children=[
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.H4("Implied Volatility Smile / Skew", style={"marginTop": "15px"}),
                                    dcc.Graph(id="vol-smile-chart", config={"displayModeBar": False})
                                ], style={"flex": "1", "minWidth": "300px"}),
                                
                                html.Div([
                                    html.H4("3D Volatility Surface", style={"marginTop": "15px"}),
                                    dcc.Graph(id="vol-surface-chart", config={"displayModeBar": False})
                                ], style={"flex": "1.2", "minWidth": "350px"})
                            ], style={"display": "flex", "flexWrap": "wrap", "gap": "20px"})
                        ], style={"padding": "10px"})
                    ]),
                    
                    # Tab 3: PnL Attribution Waterfall
                    dcc.Tab(label="PNL ATTRIBUTION", value="tab-pnl", style={"backgroundColor": "#0d1117", "color": "var(--text-muted)"}, selected_style={"backgroundColor": "#161b22", "color": "white", "borderTop": "2px solid var(--accent-color)"}, children=[
                        html.Div([
                            html.H4("PnL Attribution Waterfall Chart", style={"marginTop": "15px"}),
                            html.Div([
                                dcc.Graph(id="pnl-attribution-chart", config={"displayModeBar": False})
                            ], style={"border": "1px solid var(--border-color)", "borderRadius": "8px", "overflow": "hidden"}),
                            
                            html.H4("Hedge Logs & Funding Payments", style={"marginTop": "20px"}),
                            html.Div(id="table-hedger-logs")
                        ], style={"padding": "10px"})
                    ]),
                    
                    # Tab 4: GRT Careers & About Us
                    dcc.Tab(label="JOIN GRT (CAREERS)", value="tab-careers", style={"backgroundColor": "#0d1117", "color": "var(--text-muted)"}, selected_style={"backgroundColor": "#161b22", "color": "white", "borderTop": "2px solid var(--accent-color)"}, children=[
                        html.Div([
                            # Sleek Grid for logo & corporate summary
                            html.Div([
                                html.Img(src="/dashboard/assets/grt_logo.png", style={
                                    "width": "80px",
                                    "height": "80px",
                                    "borderRadius": "8px",
                                    "border": "1px solid var(--border-color)",
                                    "boxShadow": "0 0 10px rgba(0, 210, 255, 0.2)"
                                }),
                                html.Div([
                                    html.H4("GRT", style={"margin": "0 0 5px 0", "fontSize": "1.3rem", "background": "linear-gradient(90deg, #00d2ff, #008cff)", "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent", "fontWeight": "bold"}),
                                    html.Span("Digital-Asset Quantitative Trading Firm specializing in OTC derivatives, structured products, and algorithmic liquidity.", style={"fontSize": "0.85rem", "color": "var(--text-muted)"})
                                ], style={"flex": "1"})
                            ], style={"display": "flex", "alignItems": "center", "gap": "20px", "padding": "15px 0", "borderBottom": "1px solid var(--border-color)", "marginBottom": "15px"}),
                            
                            # About Us Section
                            html.H5("About Us", style={"margin": "0 0 8px 0", "fontSize": "0.9rem", "color": "white", "fontWeight": "bold"}),
                            html.P("GRT is a digital-asset trading firm specialising in OTC derivatives, structured products, and liquidity solutions. Our core business is pricing and trading vanilla and exotic options on tokens that have no listed options market — serving token projects, funds, miners, and institutional counterparties who need bespoke risk management. All quoting and hedging is algorithmic and automated, and we compete directly with other well known crypto trading firms.", style={"fontSize": "0.85rem", "lineHeight": "1.4", "marginBottom": "20px", "color": "var(--text-color)"}),
                            
                            # Job Posting Header
                            html.Div([
                                html.H4("Quantitative Options Trader (Junior / Mid-Level) - APAC", style={"margin": "0 0 5px 0", "color": "var(--accent-color)", "fontSize": "1.1rem", "fontWeight": "bold"}),
                                html.Span("Remote / APAC Timezones | Live Capital | Fast-Paced", style={"fontSize": "0.8rem", "color": "var(--text-muted)", "textTransform": "uppercase", "letterSpacing": "1px"})
                            ], style={"background": "rgba(88,166,255,0.05)", "border": "1px solid rgba(88,166,255,0.1)", "padding": "12px", "borderRadius": "8px", "marginBottom": "20px"}),
                            
                            # The Role
                            html.H5("The Role", style={"margin": "0 0 8px 0", "fontSize": "0.9rem", "color": "white", "fontWeight": "bold"}),
                            html.P("We are looking for a Quantitative Options Trader (Junior / Mid-Level) to support the pricing, risk management, and ongoing improvement of our OTC options book. You will work closely with senior traders to help price and manage structures such as covered calls, cash-secured puts, and other bespoke payoffs for clients — while contributing to the automated systems that warehouse and hedge risk. This is not a passive seat. You will actively contribute to models, tooling, and trading logic, gaining direct exposure to live trading and real capital while developing deep expertise in crypto options markets.", style={"fontSize": "0.85rem", "lineHeight": "1.4", "marginBottom": "20px"}),
                            
                            # Two Columns for What You Will Do & What You Bring
                            html.Div([
                                # Left Col: What You Will Do
                                html.Div([
                                    html.H5("What You Will Do", style={"margin": "0 0 10px 0", "fontSize": "0.9rem", "color": "white", "borderBottom": "1px solid var(--border-color)", "paddingBottom": "5px", "fontWeight": "bold"}),
                                    
                                    html.Div([
                                        html.Strong("Pricing & Quoting", style={"color": "var(--neon-blue)", "fontSize": "0.85rem"}),
                                        html.Ul([
                                            html.Li("Support development and calibration of quantitative models used to price options on tokens with no listed options market", style={"marginBottom": "4px"}),
                                            html.Li("Assist in building and maintaining implied volatility surfaces and pricing frameworks", style={"marginBottom": "4px"}),
                                            html.Li("Contribute to generating competitive two-way pricing for vanilla and structured OTC products", style={"marginBottom": "4px"}),
                                            html.Li("Help refine assumptions around spreads, skew, and term structure through backtesting, paper trading, scenario, and walk forward analysis", style={"marginBottom": "4px"}),
                                        ], style={"paddingLeft": "18px", "margin": "5px 0 10px 0", "fontSize": "0.8rem", "color": "var(--text-muted)"})
                                    ]),
                                    
                                    html.Div([
                                        html.Strong("Risk Management & Hedging", style={"color": "var(--neon-blue)", "fontSize": "0.85rem"}),
                                        html.Ul([
                                            html.Li("Monitor the options book and key risk metrics (delta, gamma, vega, theta)", style={"marginBottom": "4px"}),
                                            html.Li("Assist in maintaining and improving automated hedging strategies", style={"marginBottom": "4px"}),
                                            html.Li("Support stress testing and scenario analysis across different market conditions", style={"marginBottom": "4px"}),
                                            html.Li("Help manage inventory and exposures across spot and derivatives venues", style={"marginBottom": "4px"}),
                                        ], style={"paddingLeft": "18px", "margin": "5px 0 10px 0", "fontSize": "0.8rem", "color": "var(--text-muted)"})
                                    ]),
                                    
                                    html.Div([
                                        html.Strong("Technology & Automation", style={"color": "var(--neon-blue)", "fontSize": "0.85rem"}),
                                        html.Ul([
                                            html.Li("Write and maintain code (primarily Python) supporting pricing, risk, and execution systems", style={"marginBottom": "4px"}),
                                            html.Li("Collaborate with engineering to improve execution infrastructure and data pipelines", style={"marginBottom": "4px"}),
                                            html.Li("Build tools and dashboards for monitoring performance, risk, and PNL attribution", style={"marginBottom": "4px"}),
                                        ], style={"paddingLeft": "18px", "margin": "5px 0 10px 0", "fontSize": "0.8rem", "color": "var(--text-muted)"})
                                    ]),
                                    
                                    html.Div([
                                        html.Strong("Strategy & Growth", style={"color": "var(--neon-blue)", "fontSize": "0.85rem"}),
                                        html.Ul([
                                            html.Li("Contribute ideas for new products, structures, and trading strategies", style={"marginBottom": "4px"}),
                                            html.Li("Support research into market opportunities, pricing inefficiencies, and client demand", style={"marginBottom": "4px"}),
                                            html.Li("Help translate quantitative outputs into actionable trading insights", style={"marginBottom": "4px"}),
                                        ], style={"paddingLeft": "18px", "margin": "5px 0 10px 0", "fontSize": "0.8rem", "color": "var(--text-muted)"})
                                    ]),
                                ], style={"flex": "1", "minWidth": "250px"}),
                                
                                # Right Col: What You Bring & Offer
                                html.Div([
                                    html.H5("What You Bring", style={"margin": "0 0 10px 0", "fontSize": "0.9rem", "color": "white", "borderBottom": "1px solid var(--border-color)", "paddingBottom": "5px", "fontWeight": "bold"}),
                                    
                                    html.Strong("Required", style={"color": "var(--green-glow)", "fontSize": "0.85rem"}),
                                    html.Ul([
                                        html.Li("1-4 years of experience in trading, quantitative research, or a related field", style={"marginBottom": "4px"}),
                                        html.Li("Strong understanding of options fundamentals (Greeks, Black-Scholes intuition, volatility concepts)", style={"marginBottom": "4px"}),
                                        html.Li("Exposure to crypto markets and/or derivatives trading", style={"marginBottom": "4px"}),
                                        html.Li("Programming experience in Python (required); familiarity with other languages is a plus", style={"marginBottom": "4px"}),
                                        html.Li("Strong analytical and quantitative problem-solving skills", style={"marginBottom": "4px"}),
                                        html.Li("Ability to work in a fast-paced, high-ownership environment", style={"marginBottom": "4px"}),
                                    ], style={"paddingLeft": "18px", "margin": "5px 0 15px 0", "fontSize": "0.8rem", "color": "var(--text-muted)"}),
                                    
                                    html.Strong("Preferred", style={"color": "var(--accent-color)", "fontSize": "0.85rem"}),
                                    html.Ul([
                                        html.Li("Experience with options pricing or volatility modeling", style={"marginBottom": "4px"}),
                                        html.Li("Exposure to OTC markets, market-making, or structured products", style={"marginBottom": "4px"}),
                                        html.Li("Familiarity with crypto market structure (CEXs, perps, liquidity dynamics)", style={"marginBottom": "4px"}),
                                        html.Li("Background in mathematics, physics, computer science, or engineering", style={"marginBottom": "4px"}),
                                        html.Li("Interest in building automated trading systems", style={"marginBottom": "4px"}),
                                    ], style={"paddingLeft": "18px", "margin": "5px 0 15px 0", "fontSize": "0.8rem", "color": "var(--text-muted)"}),
                                    
                                    html.H5("What We Offer", style={"margin": "20px 0 10px 0", "fontSize": "0.9rem", "color": "white", "borderBottom": "1px solid var(--border-color)", "paddingBottom": "5px", "fontWeight": "bold"}),
                                    html.Ul([
                                        html.Li("Competitive compensation with performance-based upside", style={"marginBottom": "4px"}),
                                        html.Li("Direct exposure to live trading and real capital from day one", style={"marginBottom": "4px"}),
                                        html.Li("Opportunity to learn from experienced traders in a high-performance environment", style={"marginBottom": "4px"}),
                                        html.Li("Flexible remote setup across APAC time zones", style={"marginBottom": "4px"}),
                                        html.Li("Clear growth path toward senior trading and strategy ownership", style={"marginBottom": "4px"}),
                                        html.Li("Opportunity to work at the intersection of quantitative finance and digital assets", style={"marginBottom": "4px"}),
                                    ], style={"paddingLeft": "18px", "margin": "5px 0 0 0", "fontSize": "0.8rem", "color": "var(--text-muted)"})
                                ], style={"flex": "1", "minWidth": "250px"})
                            ], style={"display": "flex", "flexWrap": "wrap", "gap": "20px", "marginBottom": "20px"}),
                            
                            # Apply Button section
                            html.Div([
                                html.Button("Apply for this Role", id="btn-apply-role", className="desk-btn desk-btn-success", style={"padding": "10px 24px"}),
                                html.Div(id="apply-role-message", style={"marginTop": "12px", "fontSize": "0.85rem", "textAlign": "center"})
                            ], style={"textAlign": "center", "borderTop": "1px solid var(--border-color)", "paddingTop": "15px"})
                        ], style={"padding": "10px", "maxHeight": "400px", "overflowY": "auto"})
                    ])
                ])
            ], className="desk-card"),
            
            # BOTTOM RIGHT: STRESS TESTING
            html.Div([
                html.H3("Desk Stress Testing Simulator", style={"marginTop": 0, "borderBottom": "1px solid var(--border-color)", "paddingBottom": "10px"}),
                
                html.Label("Pre-Packaged Scenarios", className="form-label"),
                html.Div([
                    html.Button("SOL -20% Crash", id="btn-stress-crash", className="stress-btn"),
                    html.Button("SOL +30% Pump", id="btn-stress-pump", className="stress-btn"),
                    html.Button("IV Doubles", id="btn-stress-iv", className="stress-btn"),
                    html.Button("Liquidity Freeze", id="btn-stress-liq", className="stress-btn"),
                    html.Button("Gap Down Move", id="btn-stress-gap", className="stress-btn")
                ], className="stress-grid"),
                
                # Custom shock inputs
                html.Label("Custom Shocks", className="form-label"),
                html.Div([
                    html.Div([
                        html.Span("Spot Price Shock:", style={"fontSize": "0.85rem", "color": "var(--text-muted)"}),
                        html.Span(" 0%", id="label-shock-spot", style={"fontWeight": "600", "fontFamily": "JetBrains Mono"})
                    ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "5px"}),
                    dcc.Slider(
                        id="slider-shock-spot",
                        min=-0.50,
                        max=0.50,
                        step=0.05,
                        value=0.0,
                        marks={-0.5: "-50%", -0.25: "-25%", 0: "0%", 0.25: "+25%", 0.5: "+50%"}
                    )
                ], style={"marginBottom": "20px"}),
                
                html.Div([
                    html.Div([
                        html.Span("Volatility Shock:", style={"fontSize": "0.85rem", "color": "var(--text-muted)"}),
                        html.Span(" 0%", id="label-shock-iv", style={"fontWeight": "600", "fontFamily": "JetBrains Mono"})
                    ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "5px"}),
                    dcc.Slider(
                        id="slider-shock-iv",
                        min=-0.50,
                        max=1.50,
                        step=0.10,
                        value=0.0,
                        marks={-0.5: "-50%", 0: "0%", 0.5: "+50%", 1.0: "+100%", 1.5: "+150%"}
                    )
                ], style={"marginBottom": "25px"}),
                
                # Stress results details
                html.Label("Stress Test Results", className="form-label"),
                html.Div(id="stress-results-panel")
            ], className="desk-card")
            
        ], className="bottom-grid"),
        
        # Hidden and utility elements
        dcc.Interval(id="live-interval", interval=2000, n_intervals=0),
        dcc.Store(id="quote-store", data=None),
        dcc.Store(id="stress-scenario-store", data=None)
    ])
