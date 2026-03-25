import os
import pandas as pd
from config import FUTURES_API_BASE, DATA_DIR
from utils import http_get_json, save_csv, to_float_safe


def load_top_pairs():
    path = os.path.join(DATA_DIR, "top20_usdt_pairs.csv")
    df = pd.read_csv(path)
    return df["trading_pair"].astype(str).tolist()


def get_futures_symbols():
    info = http_get_json(f"{FUTURES_API_BASE}/fapi/v1/exchangeInfo")
    symbols = pd.DataFrame(info["symbols"])
    symbols = symbols[
        (symbols["status"] == "TRADING") &
        (symbols["contractType"].isin(["PERPETUAL", "CURRENT_QUARTER", "NEXT_QUARTER"]))
    ].copy()
    return set(symbols["symbol"].astype(str).tolist())


def get_last_funding(symbol: str):
    data = http_get_json(
        f"{FUTURES_API_BASE}/fapi/v1/fundingRate",
        params={"symbol": symbol, "limit": 1}
    )
    if not data:
        return {}
    return data[-1]


def get_open_interest(symbol: str):
    return http_get_json(
        f"{FUTURES_API_BASE}/fapi/v1/openInterest",
        params={"symbol": symbol}
    )


def get_premium_index(symbol: str):
    return http_get_json(
        f"{FUTURES_API_BASE}/fapi/v1/premiumIndex",
        params={"symbol": symbol}
    )


def get_ticker_24h(symbol: str):
    return http_get_json(
        f"{FUTURES_API_BASE}/fapi/v1/ticker/24hr",
        params={"symbol": symbol}
    )


def get_top_long_short_position_ratio(symbol: str, period="1h"):
    data = http_get_json(
        f"{FUTURES_API_BASE}/futures/data/topLongShortPositionRatio",
        params={"symbol": symbol, "period": period, "limit": 1}
    )
    return data[-1] if data else {}


def get_taker_long_short_ratio(symbol: str, period="1h"):
    data = http_get_json(
        f"{FUTURES_API_BASE}/futures/data/takerlongshortRatio",
        params={"symbol": symbol, "period": period, "limit": 1}
    )
    return data[-1] if data else {}


def main():
    pairs = load_top_pairs()
    futures_symbols = get_futures_symbols()

    rows = []

    for symbol in pairs:
        if symbol not in futures_symbols:
            print(f"[INFO] No futures contract for {symbol}, skipping")
            continue

        try:
            oi = get_open_interest(symbol)
            pi = get_premium_index(symbol)
            fr = get_last_funding(symbol)
            tk = get_ticker_24h(symbol)
            top_pos = get_top_long_short_position_ratio(symbol, period="1h")
            taker = get_taker_long_short_ratio(symbol, period="1h")

            row = {
                "trading_pair": symbol,
                "mark_price": to_float_safe(pi.get("markPrice")),
                "index_price": to_float_safe(pi.get("indexPrice")),
                "estimated_settle_price": to_float_safe(pi.get("estimatedSettlePrice")),
                "last_funding_rate": to_float_safe(pi.get("lastFundingRate")),
                "next_funding_time": pi.get("nextFundingTime"),
                "open_interest": to_float_safe(oi.get("openInterest")),
                "futures_last_price": to_float_safe(tk.get("lastPrice")),
                "futures_price_change_pct_24h": to_float_safe(tk.get("priceChangePercent")),
                "futures_base_volume_24h": to_float_safe(tk.get("volume")),
                "futures_quote_volume_24h": to_float_safe(tk.get("quoteVolume")),
                "futures_trade_count_24h": int(float(tk.get("count", 0))) if tk.get("count") is not None else 0,
                "funding_rate_last_snapshot": to_float_safe(fr.get("fundingRate")),
                "funding_time_last_snapshot": fr.get("fundingTime"),
                "top_trader_long_short_position_ratio_1h": to_float_safe(top_pos.get("longShortRatio")),
                "top_trader_long_account_pct_1h": to_float_safe(top_pos.get("longAccount")),
                "top_trader_short_account_pct_1h": to_float_safe(top_pos.get("shortAccount")),
                "taker_long_short_ratio_1h": to_float_safe(taker.get("buySellRatio")),
                "taker_buy_vol_1h": to_float_safe(taker.get("buyVol")),
                "taker_sell_vol_1h": to_float_safe(taker.get("sellVol")),
            }

            rows.append(row)
            print(f"[OK] derivatives {symbol}")

        except Exception as e:
            print(f"[WARN] derivatives failed {symbol}: {e}")

    df = pd.DataFrame(rows)
    out_path = os.path.join(DATA_DIR, "derivatives_snapshot_v2.csv")
    save_csv(df, out_path)


if __name__ == "__main__":
    main()