# Broker API Configuration Guide

This guide details how to configure broker API credentials, generate TOTP authentication keys, and connect your trading account to the execution engine.

---

## 🔐 Credentials Overview & `.env` Setup

All sensitive broker credentials (passwords, API keys, TOTP secrets) are stored in the local `.env` file (which is git-ignored for safety).

### 1. Initialize your local `.env` file:
```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

---

## 🏦 Broker-Specific Setup Guides

### 1. Finvasia Shoonya (Default Zero-Brokerage Live Execution)
Shoonya provides a completely free API with zero monthly fees and zero intraday brokerage.

#### Configuration Keys:
```env
SHOONYA_USER=your_client_id
SHOONYA_PWD=your_login_password
SHOONYA_API_KEY=your_api_key
SHOONYA_VENDOR_CODE=your_vendor_code
SHOONYA_TOTP_KEY=your_totp_secret_key
SHOONYA_IMEI=shoonya_algo_desktop
```

#### How to obtain your Shoonya credentials:
1. **API Key & Vendor Code**: Log into the [Shoonya Prism Portal](https://prism.shoonya.com/) $\to$ Go to **API Center** $\to$ Generate your API Key and Vendor Code.
2. **TOTP Secret Key**: When enabling 2FA in Shoonya Mobile/Web app, choose *"Can't scan QR code?"* to reveal the alphanumeric base32 secret string (e.g. `JBSWY3DPEHPK3PXP`). Paste this key as `SHOONYA_TOTP_KEY`.

---

### 2. Zerodha Kite Connect
```env
ZERODHA_USER=your_user_id
ZERODHA_PWD=your_password
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_TOTP_KEY=your_totp_secret_key
```

---

### 3. Dhan HQ
```env
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_permanent_access_token
```

---

### 4. Angel One (SmartAPI)
```env
ANGEL_CLIENT_CODE=your_client_code
ANGEL_PWD=your_pin
ANGEL_API_KEY=your_smartapi_key
ANGEL_TOTP_KEY=your_totp_secret_key
```

---

### 5. Upstox
```env
UPSTOX_API_KEY=your_api_key
UPSTOX_API_SECRET=your_api_secret
UPSTOX_REDIRECT_URI=http://localhost:8000/callback
```

---

### 6. Fyers (API v3)
```env
FYERS_APP_ID=your_app_id
FYERS_SECRET_KEY=your_secret_key
FYERS_REDIRECT_URI=http://localhost:8000/callback
```

---

## 🛡️ Best Practices & Security
* **Never commit `.env`**: `.gitignore` is already pre-configured to ignore `.env` and `*.db` files.
* **Separation of Secrets and Logic**: All mathematical strategy parameters, risk rules, and portfolio math are centrally defined as typed Python constants in [`config.py`](../config.py). Your `.env` file is exclusively reserved for confidential secrets.
