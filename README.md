# OTC Crypto Options Desk

An institutional-grade OTC crypto options trading simulator that replicates the workflow of a digital asset derivatives trading desk. The platform provides end-to-end infrastructure for pricing bespoke token options, constructing implied volatility surfaces, managing portfolio Greeks, automating delta hedging, attributing PnL, and performing stress testing across digital asset derivatives portfolios.

## Overview

Most digital assets do not have liquid listed options markets, making pricing and risk management significantly more complex than traditional exchange-traded options. This project addresses that challenge by simulating the quantitative infrastructure used by professional OTC derivatives desks.

The system continuously ingests market data, calibrates volatility models, generates two-way option quotes, monitors portfolio exposures, executes automated hedging strategies, and provides real-time risk analytics and performance attribution.

## Core Capabilities

### Market Simulation & Data Engine

* Multi-asset market simulation for BTC, ETH, SOL, and ARB
* Geometric Brownian Motion (GBM) with drift and stochastic volatility shocks
* Historical market data generation and real-time price streams
* Spot and perpetual market simulations

### Volatility Modeling

* Real-time implied volatility surface construction
* Volatility smile and skew modeling
* Term structure calibration and interpolation
* Support for pricing bespoke strikes and maturities without listed market data

### Pricing Engine

* Analytical Black-Scholes-Merton pricing for vanilla options
* Monte Carlo path simulation for structured products
* Support for:

  * Calls and Puts
  * Covered Calls
  * Cash-Secured Puts
  * Collars
  * Custom OTC payoff structures

### Portfolio Risk Management

* Real-time portfolio aggregation
* Portfolio Greeks computation:

  * Delta
  * Gamma
  * Vega
  * Theta
* Risk-based margin estimation
* Inventory and exposure monitoring

### Automated Delta Hedging

* Continuous monitoring of net portfolio Delta
* Configurable hedging thresholds
* Automated hedge execution using spot and perpetual markets
* Dynamic rebalancing toward delta neutrality

### PnL Attribution

* Delta PnL
* Gamma PnL
* Vega PnL
* Theta decay
* Hedging costs and execution slippage
* Perpetual funding costs

### Stress Testing & Scenario Analysis

* Spot price shocks
* Volatility regime changes
* Liquidity stress events
* Portfolio revaluation under extreme scenarios
* Shocked Greeks and hedge requirement projections

## Problems Addressed

The platform is designed to solve the core challenges faced by crypto OTC options market makers:

* Pricing options on assets without listed options markets
* Managing multi-asset portfolio Greeks and inventory risk
* Maintaining delta neutrality during volatile market conditions
* Identifying sources of profitability and PnL leakage
* Quantifying tail-risk exposure under extreme market events

## Technology Stack

**Backend**

* Python
* FastAPI
* SQLAlchemy
* PostgreSQL / SQLite

**Quantitative Libraries**

* NumPy
* Pandas
* SciPy
* Plotly

**Frontend**

* Plotly Dash

**Deployment**

* Docker
* Docker Compose

## Project Goal

The objective of this project is to build a production-style quantitative trading platform that mirrors the day-to-day operations of an institutional crypto OTC options desk, combining derivatives pricing, volatility modeling, automated hedging, and portfolio risk management into a single integrated system.
