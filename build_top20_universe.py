import os
import pandas as pd
from config import SPOT_API_BASE, DATA_DIR, TOP_N, QUOTE_ASSET
from utils import http_get_json, to_float_safe, save_csv


def main():
    exchange_info = http_get_json(f"{SPOT_API_BASE}/api/v3/exchangeInfo")
    symbols_info = pd.DataFrame(exchange_info["symbols"])

    # Только spot trading + status TRADING + quoteAsset=USDT
    symbols_info = symbols_info[
        (symbols_info["status"] == "TRADING") &
        (symbols_info["isSpotTradingAllowed"] == True) &
        (symbols_info["quoteAsset"] == QUOTE_ASSET)
    ].copy()

    allowed_symbols = set(symbols_info["symbol"].tolist())

    ticker_24h = http_get_json(f"{SPOT_API_BASE}/api/v3/ticker/24hr")
    tickers = pd.DataFrame(ticker_24h)

    tickers = tickers[tickers["symbol"].isin(allowed_symbols)].copy()

    # quoteVolume — основной критерий ликвидности
    tickers["quoteVolume"] = tickers["quoteVolume"].apply(to_float_safe)
    tickers["volume"] = tickers["volume"].apply(to_float_safe)
    tickers["lastPrice"] = tickers["lastPrice"].apply(to_float_safe)
    tickers["priceChangePercent"] = tickers["priceChangePercent"].apply(to_float_safe)
    tickers["count"] = tickers["count"].apply(lambda x: int(float(x)) if pd.notna(x) else 0)

    tickers = tickers.sort_values("quoteVolume", ascending=False).head(TOP_N).copy()

    result = tickers[[
        "symbol",
        "lastPrice",
        "volume",
        "quoteVolume",
        "priceChangePercent",
        "count"
    ]].rename(columns={
        "symbol": "trading_pair",
        "lastPrice": "last_price",
        "volume": "base_volume_24h",
        "quoteVolume": "quote_volume_24h",
        "priceChangePercent": "price_change_pct_24h",
        "count": "trade_count_24h"
    })

    out_path = os.path.join(DATA_DIR, "top20_usdt_pairs.csv")
    save_csv(result, out_path)

    print("\nTop 20 USDT pairs:")
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()