# Shoonya Algorithmic Trading Bot & Simulation Engine

An automated intraday trading execution engine and portfolio simulator built in Python for Shoonya (Finvasia).

---

## 📈 Strategy Overview: VWAP-Stoch Breakdown

* **Universe:** NIFTY 50 Constituents (NSE)
* **Timeframe:** 15-Minute Candles
* **Entry Window:** 10:00 AM – 1:30 PM IST
* **Direction:** Short Breakdown
* **Core Technical Indicators:**
  * **Stochastic RSI (14, 14, 3, 3):** Identifies breakdown momentum (crossing below 80 from overbought).
  * **ADX (14):** Trend strength filter (`ADX > 25`).
  * **VWAP:** Intraday bias confirmation (`Close < VWAP`).
  * **NIFTY 50 Relative Weakness:** Stock intraday % return must underperform NIFTY 50 intraday % return (`Stock % < Nifty %`).

---

## 🛡️ Risk Management & Execution Rules

* **Capital Allocation:** ₹10,000 baseline (Max 2 concurrent positions, ₹5,000 margin / 5x MIS leverage).
* **Dynamic Stop Loss:** 3-bar swing high (min 0.2% buffer).
* **Profit Target:** Dynamic 1:2 Risk-to-Reward (2R).
* **Trailing SL:** Once trade reaches **+1R profit**, Stop-Loss automatically trails to **Breakeven (₹0 risk)**.
* **Auto-Squareoff:** Mandatory hard exit at **15:00 IST (3:00 PM)**.
* **Fee Modeling:** Full Shoonya regulatory friction modeled (STT, GST, Exchange Txn, Stamp Duty, SEBI turnover fees).

---

## 📊 Backtest Performance (Simulation)

| Metric | Simulated Result |
| :--- | :--- |
| **Simulation Period** | **2026-05-25 to 2026-08-14 (56 Trading Days)** |
| **Initial Capital** | ₹10,000.00 |
| **Per-Trade Exposure** | ₹25,000.00 (₹5,000 margin x 5 MIS) |
| **Total Trades Taken** | 131 (59 Wins / 72 Losses) |
| **Win Rate** | **45.04%** |
| **Gross Profit (Pre-Tax)** | **₹5,736.69 (+57.37%)** |
| **Total Statutory Taxes & Brokerage** | **₹2,699.70** |
| **Total Net Profit** | **+₹3,036.99 (Post-All Charges)** |
| **Net Return** | **+30.37%** |
| **Ending Capital Balance** | **₹13,036.99** |
| **Profit Factor** | 1.70 (Gross Profits / Gross Losses) |
| **Max Drawdown (MDD)** | ₹1,114.18 (−8.74%) |
| **Trade Expectancy** | +₹23.18 / trade |

---

## 📁 Repository Structure

```text
shoonya_algo/
├── config.py              # Centralized TradingConfig dataclass & parameters
│
├── core/                  # Pure math, indicators & regulatory fee calculators
│   ├── trade_db.py        # Isolated SQLite trade journals (WAL mode & concurrency hardened)
│   ├── indicators.py      # Stoch RSI, ADX, VWAP, Relative Weakness formulas
│   └── charges.py         # Universal Indian taxes & multi-broker fee engine
│
├── strategies/            # Trading strategies layer (one module per strategy)
│   └── vwap_stoch_breakdown.py # Rules, entry/exit criteria & single-trade lifecycle
│
├── data_pipeline/         # Market data gateway & historical caching
│   ├── data_feed.py       # Smart local caching & fallback data loader
│   └── shoonya_loader.py  # Shoonya 1-year historical downloader
│
├── backtesting/           # Historical simulation & scanning engines
│   ├── portfolio_sim.py   # Chronological multi-stock portfolio simulator
│   └── scanner.py         # Unconstrained single-stock indicator scanner
│
├── live_trading/          # Execution engines
│   ├── base_engine.py     # Common scheduler, candle aggregator & trailing SL
│   ├── paper_trader.py    # Risk-free virtual paper trading
│   └── live_trader.py     # Real-money Shoonya OMS order placement
│
├── alerts/                # Multi-channel notification framework (Telegram, Webhooks)
│   ├── __init__.py        # Clean public export facade
│   ├── base.py            # BaseAlertChannel interface & dynamic channel dispatcher
│   └── telegram.py        # Telegram bot push notifications
│
├── tests/                 # Automated test suites
│   ├── test_trade_db.py   # SQLite CRUD, isolation & zero-pollution verification
│   ├── test_charges.py    # Multi-broker fee engine & statutory tax verification
│   ├── test_strategy_parity.py # Exact numerical parity between backtesting and live execution
│   ├── test_alerts.py     # Multi-channel notification dispatch & failure isolation
│   └── test_live_monitor.py # High-frequency guardian & precise 3PM squareoff
│
├── market_data/           # Local candle cache CSVs (git-ignored)
├── database/              # SQLite trade journals (git-ignored)
├── docs/                  # In-depth architectural & operational setup guides
│   └── cloud_execution_setup_guide.md # Telegram bot & GitHub Actions fork setup guide
├── .env.example           # Public secrets template with placeholder values
├── .env                   # Private broker credentials (git-ignored)
└── README.md
```

---

## 🚀 Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/vaibhavreddys/algotradingdaily.git
cd algotradingdaily
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux/macOS
```

### 3. Install dependencies
All project dependencies are listed in [`requirements.txt`](requirements.txt). Install them with:
```bash
pip install -r requirements.txt
```

### 4. Configure Broker Credentials (.env)
Copy the public template file [`.env.example`](.env.example) to `.env` and fill in your confidential broker API keys:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

Edit `.env` with your private broker credentials (templates for Shoonya, Zerodha, Dhan, Groww, Angel One, Upstox, and Fyers are included in [`.env.example`](.env.example)):
```env
# Finvasia Shoonya API Credentials (Private Secrets)
SHOONYA_USER=your_user_id
SHOONYA_PWD=your_password
SHOONYA_API_KEY=your_api_key
SHOONYA_VENDOR_CODE=your_vendor_code
SHOONYA_TOTP_KEY=your_totp_secret_key
SHOONYA_IMEI=shoonya_algo_desktop
```
> [!NOTE]
> All strategy parameters, risk rules, and portfolio math are centrally defined as typed Python constants in [`config.py`](config.py). Your `.env` file is exclusively reserved for confidential secrets.

---

## 💻 Usage

### Run Portfolio Simulation (₹10,000 Capital, 2 Slots):
```bash
python -m backtesting.portfolio_sim            # loads from market_data/ archives (fast)
python -m backtesting.portfolio_sim --refresh  # force re-download of fresh 15m candles
```
* All 50 NIFTY 50 constituents are scanned **in parallel (8 workers)** with vectorized signal extraction; a full `--refresh` re-download completes in ~6s.

### Run Unconstrained Strategy Scanner:
```bash
python -m backtesting.scanner
```

### Run Live Market Paper Trading Engine (Safe Simulation):
```bash
python -m live_trading.paper_trader
```
* **Real-time 15m candle loop**: Evaluates breakdown signals on every bar close (:00, :15, :30, :45) during the active window (10:00 AM – 1:30 PM).
* **+1R Trailing SL**: Automatically moves stop loss to Breakeven in real-time.
* **3:00 PM Auto-Squareoff**: Automatically exits open positions at 15:00 IST and saves all records to `database/paper_trades.db`.
* **Daily EOD Performance Report**: Prints an itemized performance summary table on market close or daemon exit.

### Run Automated 24/7 Cloud Paper Trading (Free GitHub Actions Daemon):
* Runs automatically in the cloud Monday to Friday (09:10 AM – 15:35 IST) and sends real-time trade signals to your phone via Telegram.
* See the full step-by-step setup guide in [`docs/cloud_execution_setup_guide.md`](docs/cloud_execution_setup_guide.md).

### Run Live Real-Money Execution Engine:
```bash
python -m live_trading.live_trader
```

### Run Automated Test Suite:
```bash
# Run all unit tests
python -m unittest discover tests

# Run individual test modules:
python -m unittest tests/test_charges.py
python -m unittest tests/test_trade_db.py
python -m unittest tests/test_strategy_parity.py
python -m unittest tests/test_alerts.py
python -m unittest tests/test_live_monitor.py
```
