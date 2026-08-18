# Backtest Results & Multi-Broker Friction Matrix

This document provides quantitative backtest results, timeframe comparison studies, and the statutory multi-broker friction matrix.

---

## 📊 58-Day Baseline Performance (15-Minute Timeframe)

Simulation run on 50 Nifty constituents across **58 Trading Days (2026-05-27 to 2026-08-18)** with ₹10,000 capital and max 2 concurrent positions:

| Metric | Quantitative Value |
| :--- | :--- |
| **Initial Capital** | ₹10,000.00 |
| **Per-Trade Exposure** | ₹25,000.00 (₹5,000 margin $\times$ 5 MIS) |
| **Total Trades Taken** | 124 (56 Wins / 68 Losses) |
| **Win Rate** | **45.16%** |
| **Gross Realized Profit** | **+₹5,608.98 (+56.09%)** |
| **Total Statutory Taxes & Charges** | **₹2,555.43** |
| **Net Realized Profit (Post-Charges)** | **+₹3,053.55 (+30.54% ROI)** |
| **Ending Capital Balance** | **₹13,053.55** |
| **Profit Factor** | **1.76** (Gross Gains / Gross Losses) |
| **Max Drawdown (MDD)** | **-₹1,241.65 (-9.52%)** |
| **Trade Expectancy** | **+₹24.63 / trade** |
| **Avg Win / Avg Loss** | **+₹232.43 / -₹108.93** |

---

## ⏱️ Multi-Timeframe Comparative Backtest Study

| Timeframe | Trades | Win Rate | Gross Profit | Taxes/Fees | Net Realized PnL | Net ROI % | Verdict |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`5m`** | 236 | 36.86% | +₹2,674.10 | ₹4,866.50 | -₹2,192.40 | **-21.92%** | ❌ Excessive fee drag & whipsaws |
| **`15m`** | **124** | **45.16%** | **+₹5,608.98** | **₹2,555.43** | **+₹3,053.55** | **+30.54%** | ✅ **Optimal Quantitative Sweet Spot** |
| **`30m`** | 94 | 43.62% | +₹2,091.20 | ₹1,945.30 | +₹145.90 | **+1.46%** | ⚠️ Fewer entries, delayed momentum |
| **`60m`** | 72 | 34.72% | +₹580.40 | ₹1,493.10 | -₹912.70 | **-9.13%** | ❌ 87.5% forced 3PM exits |

---

## 🏦 Multi-Broker Friction Comparison Matrix

Calculated across the 124 executed trades modeling all Indian regulatory statutory taxes (STT 0.025% sell-side, NSE Txn 0.00297%, GST 18%, Stamp Duty 0.003%, SEBI 0.0001%):

| Broker Schedule | Total Brokerage + Taxes | Net Realized PnL | Net ROI % | Fee Impact |
| :--- | :---: | :---: | :---: | :---: |
| **Zero-Brokerage Baseline** | ₹1,092.23 | +₹4,516.75 | **+45.17%** | Pure statutory taxes |
| **Shoonya (Finvasia)** | **₹2,555.43** | **+₹3,053.55** | **+30.54%** | **Optimal Real-World (Zero Brokerage)** |
| **Zerodha** (₹20 / order) | ₹3,285.04 | +₹2,323.94 | **+23.24%** | -7.30% ROI lost to brokerage |
| **Dhan** (₹20 / order) | ₹3,285.04 | +₹2,323.94 | **+23.24%** | -7.30% ROI lost to brokerage |
| **Fyers** (₹20 / order) | ₹3,285.04 | +₹2,323.94 | **+23.24%** | -7.30% ROI lost to brokerage |
| **Groww** (0.05% max ₹20) | ₹4,746.92 | +₹862.06 | **+8.62%** | -21.92% ROI lost to brokerage |
| **Upstox** (0.05% max ₹20) | ₹4,746.92 | +₹862.06 | **+8.62%** | -21.92% ROI lost to brokerage |
| **Angel One** (₹20 / leg) | ₹6,945.03 | -₹1,336.05 | **-13.36%** | Destroys net edge |
