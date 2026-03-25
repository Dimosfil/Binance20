import os

SPOT_API_BASE = "https://api.binance.com"
FUTURES_API_BASE = "https://fapi.binance.com"

DATA_DIR = "data"
TOP_N = 1
QUOTE_ASSET = "USDT"

REQUEST_TIMEOUT = 20
REQUEST_SLEEP_SEC = 0.12

# Сколько свечей скачивать
OHLCV_LIMITS = {
    "1h": 500,   # ~21 день
    "4h": 400,   # ~66 дней
    "1d": 365    # ~1 год
}

# Для liquidity snapshot
ORDERBOOK_LIMIT = 500

os.makedirs(DATA_DIR, exist_ok=True)