# 🚀 Cloud Execution Setup Guide (GitHub Actions & Telegram)

This guide explains how to run your trading daemon **100% free in the cloud** using GitHub Actions, while keeping your personal credentials completely private in your personal fork.

---

## 🛠️ Step 1: Create a Personal Telegram Bot (For Mobile Alerts)

1. Open **Telegram** on your mobile or desktop and search for **`@BotFather`**.
2. Send `/newbot` and follow the prompts to choose a name and username (e.g. `MyShoonyaTradingBot`).
3. BotFather will provide an **HTTP API Token** (e.g. `7182938491:AAHqj_...`). Copy this token.
4. Search for **`@userinfobot`** on Telegram, send `/start`, and copy your numeric **Id** (e.g. `123456789`).
5. Open your newly created bot in Telegram and tap **"Start"** (or send any message like `/start` so the bot has permission to message you).

---

## 🍴 Step 2: Fork the Repository

1. Navigate to the main repository: `https://github.com/vaibhavreddys/algotradingdaily`
2. Click the **"Fork"** button in the top-right corner.
3. Choose your personal GitHub account as the destination.
4. Uncheck *"Copy the main branch only"* (so you have access to all branches).
5. Click **"Create fork"**.

---

## 🔒 Step 3: Add Private Secrets to Your Personal Fork

In your **personal forked repository** on GitHub:

1. Go to **Settings** $\to$ **Secrets and variables** $\to$ **Actions**.
2. Under the **Secrets** tab, click **"New repository secret"**:
   - **Name**: `TELEGRAM_BOT_TOKEN`
   - **Secret**: *(Paste your token from BotFather)*
   - Click **Add secret**.
3. Click **"New repository secret"** again:
   - **Name**: `TELEGRAM_CHAT_ID`
   - **Secret**: *(Paste your numeric ID from userinfobot)*
   - Click **Add secret**.
4. *(Optional - Only needed when switching to live money)*:
   - `SHOONYA_USER`, `SHOONYA_PWD`, `SHOONYA_API_KEY`, `SHOONYA_VENDOR_CODE`, `SHOONYA_TOTP_KEY`, `SHOONYA_IMEI`.

---

## 🏃 Step 4: Run & Test the Cloud Bot

In your **personal forked repository**:

1. Click the **"Actions"** tab at the top.
2. If Actions are disabled on your fork, click **"I understand my workflows, go ahead and enable them"**.
3. In the left sidebar, click **"Daily Paper Trading Execution Daemon"**.
4. Click the **"Run workflow"** button on the right $\to$ select branch `main` (or `development`) $\to$ click **"Run workflow"**.
5. Click on the running job to watch live terminal logs.
6. Verify you receive a test startup / entry notification on your Telegram app!

---

## ⏰ Step 5: Automated Daily Schedule

Once enabled in your fork:
- The cloud daemon runs **automatically Monday to Friday at 09:10 AM IST (03:40 UTC)**.
- It scans the Nifty 50 universe, trails Stop-Losses, enforces 3:00 PM auto-squareoffs, and sends you instant Telegram alerts.
- At 15:35 IST, it saves your `paper_trades.db` SQLite database as a GitHub Artifact and shuts down gracefully.

---

## 🔄 Keeping Your Fork Updated With New Features

Whenever new strategies, bug fixes, or improvements are committed to `vaibhavreddys/algotradingdaily`:
1. Open your personal fork on GitHub.
2. Click the **"Sync fork"** button at the top $\to$ click **"Update branch"**.
3. Your fork is updated to the latest code in 1 second!
