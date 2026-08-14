# Shoonya Algorithmic Trading Bot

An automated intraday trading execution engine built in Python for Shoonya (Finvasia).

## Strategy Overview
* **Timeframe:** 15-Minute Candles
* **Indicators:** Stochastic RSI (14, 14, 3, 3) + 200 EMA Trend Filter + ADX Filter
* **Risk Management:** 
  * Max 2 concurrent positions (₹10,000 capital simulation)
  * Dynamic Stop Loss: 3-bar swing high/low
  * Target: Fixed 2:1 Risk-to-Reward (2R)
  * Auto-Squareoff: Hard exit at 15:00 IST

## Files
* `shoonya_engine.py`: Live execution daemon connecting to Shoonya API.
* `portfolio_sim.py`: Chronological 60-day portfolio simulator factoring in broker friction & STT.
* `backtest.py`: Standalone single-stock technical indicator scan.
* `trade_db.py`: SQLite state tracking database for position persistence.

## Setup
1. Clone the repository
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
