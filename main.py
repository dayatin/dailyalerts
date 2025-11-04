import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv
import os

# ------------------ INIT ------------------
load_dotenv()
ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
DAYS = 180
COINGECKO_BASE = 'https://api.coingecko.com/api/v3'

# ------------------ ALERTS ------------------
def send_alert(subject, body):
    # Gmail alert
    try:
        gmail_user = os.getenv('GMAIL_USER')
        gmail_pass = os.getenv('GMAIL_PASS')
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = gmail_user
        msg['To'] = gmail_user

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, [gmail_user], msg.as_string())
        print("✅ Gmail alert sent.")
    except Exception as e:
        print(f"⚠️ Gmail alert failed: {e}")

    # Telegram alert
    # try:
    #     token = os.getenv('TELEGRAM_TOKEN')
    #     chat_id = os.getenv('TELEGRAM_CHAT_ID')
    #     url = f"https://api.telegram.org/bot{token}/sendMessage"
    #     payload = {"chat_id": chat_id, "text": f"{subject}\n\n{body}"}
    #     response = requests.post(url, data=payload)
    #     if response.status_code == 200:
    #         print("✅ Telegram alert sent.")
    #     else:
    #         print(f"⚠️ Telegram alert failed: {response.text}")
    # except Exception as e:
    #     print(f"⚠️ Telegram alert error: {e}")

# ------------------ DATA FETCH ------------------
def fetch_crypto_prices(coin_id, days=DAYS):
    url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days}
    response = requests.get(url, params=params)
    data = response.json()
    prices = [p[1] for p in data['prices']]
    dates = pd.date_range(end=datetime.today(), periods=len(prices))
    return pd.DataFrame({'Date': dates, 'Price': prices})

def fetch_gold_prices(api_key):
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": "XAUUSD",
        "apikey": api_key
    }
    response = requests.get(url, params=params)
    data = response.json().get("Time Series (Daily)", {})
    df = pd.DataFrame([
        {"Date": pd.to_datetime(date), "Price": float(info["4. close"])}
        for date, info in sorted(data.items())
    ])
    return df.tail(DAYS).reset_index(drop=True)

# ------------------ INDICATORS ------------------
def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, short=12, long=26, signal=9):
    ema_short = prices.ewm(span=short, adjust=False).mean()
    ema_long = prices.ewm(span=long, adjust=False).mean()
    macd = ema_short - ema_long
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def simulate_mvrv(prices):
    realized_price = prices.rolling(window=30).mean()
    mvrv = prices / realized_price
    return mvrv

# ------------------ REPORTING ------------------
def plot_indicators(df, asset):
    plt.figure(figsize=(12, 6))
    plt.plot(df['Date'], df['Price'], label='Price', color='blue')
    plt.plot(df['Date'], df['RSI'], label='RSI', color='green')
    plt.plot(df['Date'], df['MACD'], label='MACD', color='red')
    plt.plot(df['Date'], df['Signal'], label='MACD Signal', color='orange')
    plt.plot(df['Date'], df['MVRV'], label='MVRV', color='purple')
    plt.title(f'{asset} Price & Indicators')
    plt.xlabel('Date')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'{asset.lower()}_chart.png')
    plt.close()

def generate_report(asset, df):
    latest = df.iloc[-1]
    report = (
        f"📊 {asset} Valuation Report ({latest['Date'].date()}):\n"
        f"Price: ${latest['Price']:.2f}\n"
        f"RSI: {latest['RSI']:.2f} → {'Oversold' if latest['RSI'] < 30 else 'Neutral/Bullish'}\n"
        f"MACD: {latest['MACD']:.2f}, Signal: {latest['Signal']:.2f} → "
        f"{'Bullish' if latest['MACD'] > latest['Signal'] else 'Bearish'}\n"
        f"MVRV: {latest['MVRV']:.2f} → {'Undervalued' if latest['MVRV'] < 1.0 else 'Fairly Valued'}"
    )
    print(report)
    send_alert(f"{asset} Daily Valuation", report)

# ------------------ MAIN ------------------
assets = {
    'Gold': lambda: fetch_gold_prices(ALPHA_VANTAGE_KEY),
    'Bitcoin': lambda: fetch_crypto_prices('bitcoin'),
    'Ethereum': lambda: fetch_crypto_prices('ethereum')
}

for asset, fetch_func in assets.items():
    try:
        df = fetch_func()
        df['RSI'] = calculate_rsi(df['Price'])
        df['MACD'], df['Signal'] = calculate_macd(df['Price'])
        df['MVRV'] = simulate_mvrv(df['Price'])
        plot_indicators(df, asset)
        generate_report(asset, df)
    except Exception as e:
        print(f"⚠️ Error processing {asset}: {e}")
