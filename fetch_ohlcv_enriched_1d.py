import os
import time
import numpy as np
import pandas as pd
import requests


DATA_DIR = "data"
TOP_PAIRS_FILE = os.path.join(DATA_DIR, "top20_usdt_pairs.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "ohlcv_1d_enriched.csv")

SPOT_API_BASE = "https://api.binance.com"
REQUEST_TIMEOUT = 20
REQUEST_SLEEP_SEC = 0.12

INTERVAL = "1d"
LIMIT = 365


def load_top_pairs():
    if not os.path.exists(TOP_PAIRS_FILE):
        raise FileNotFoundError(f"Top pairs file not found: {TOP_PAIRS_FILE}")
    df = pd.read_csv(TOP_PAIRS_FILE)
    if "trading_pair" not in df.columns:
        raise ValueError("Column 'trading_pair' not found in top20_usdt_pairs.csv")
    return df["trading_pair"].astype(str).tolist()


def fetch_klines(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    url = f"{SPOT_API_BASE}/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    time.sleep(REQUEST_SLEEP_SEC)

    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
    ]
    df = pd.DataFrame(data, columns=cols)

    numeric_cols = [
        "open", "high", "low", "close", "volume",
        "quote_asset_volume", "number_of_trades",
        "taker_buy_base_volume", "taker_buy_quote_volume"
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    df["trading_pair"] = symbol

    return df[[
        "open_time", "close_time", "trading_pair",
        "open", "high", "low", "close", "volume",
        "quote_asset_volume", "number_of_trades",
        "taker_buy_base_volume", "taker_buy_quote_volume"
    ]]


def add_indicators(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("open_time").copy()

    close = group["close"]
    high = group["high"]
    low = group["low"]
    open_ = group["open"]
    volume = group["volume"]

    group["ema_20"] = close.ewm(span=20, adjust=False).mean()
    group["ema_50"] = close.ewm(span=50, adjust=False).mean()
    group["ema_200"] = close.ewm(span=200, adjust=False).mean()

    group["sma_20"] = close.rolling(20).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    group["rsi_14"] = 100 - (100 / (1 + rs))

    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    group["atr_14"] = tr.ewm(alpha=1/14, adjust=False).mean()
    group["atr_pct"] = (group["atr_14"] / close.replace(0, np.nan)) * 100.0

    group["return_pct"] = close.pct_change() * 100.0
    group["range_pct"] = ((high - low) / close.replace(0, np.nan)) * 100.0
    group["body_pct"] = ((close - open_).abs() / close.replace(0, np.nan)) * 100.0
    group["upper_wick_pct"] = ((high - np.maximum(open_, close)) / close.replace(0, np.nan)) * 100.0
    group["lower_wick_pct"] = ((np.minimum(open_, close) - low) / close.replace(0, np.nan)) * 100.0

    group["volume_ma_20"] = volume.rolling(20).mean()
    group["volume_ratio_20"] = volume / group["volume_ma_20"].replace(0, np.nan)

    group["rolling_high_20"] = high.shift(1).rolling(20).max()
    group["rolling_low_20"] = low.shift(1).rolling(20).min()
    group["rolling_high_50"] = high.shift(1).rolling(50).max()
    group["rolling_low_50"] = low.shift(1).rolling(50).min()

    group["dist_to_high20_pct"] = ((close - group["rolling_high_20"]) / group["rolling_high_20"]) * 100.0
    group["dist_to_low20_pct"] = ((close - group["rolling_low_20"]) / group["rolling_low_20"]) * 100.0

    group["above_ema_20"] = close > group["ema_20"]
    group["above_ema_50"] = close > group["ema_50"]
    group["above_ema_200"] = close > group["ema_200"]
    group["ema20_above_ema50"] = group["ema_20"] > group["ema_50"]
    group["ema50_above_ema200"] = group["ema_50"] > group["ema_200"]

    return group


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    pairs = load_top_pairs()
    all_parts = []

    print(f"[INFO] Fetching {INTERVAL} OHLCV for {len(pairs)} pairs")

    for symbol in pairs:
        try:
            df = fetch_klines(symbol, INTERVAL, LIMIT)
            all_parts.append(df)
            print(f"[OK] {symbol}: {len(df)} rows")
        except Exception as e:
            print(f"[WARN] Failed {symbol}: {e}")

    if not all_parts:
        print("[WARN] No data fetched.")
        return

    full = pd.concat(all_parts, ignore_index=True)
    full = full.sort_values(["trading_pair", "open_time"]).copy()

    enriched = (
        full.groupby("trading_pair", group_keys=True)
        .apply(add_indicators, include_groups=False)
        .reset_index(drop=False)
    )

    enriched.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    print(f"[OK] Saved: {OUTPUT_FILE} | rows={len(enriched)}")


if __name__ == "__main__":
    main()