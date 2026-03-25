import os
import pandas as pd
from config import SPOT_API_BASE, DATA_DIR, ORDERBOOK_LIMIT
from utils import http_get_json, save_csv, to_float_safe


def load_top_pairs_df():
    path = os.path.join(DATA_DIR, "top20_usdt_pairs.csv")
    return pd.read_csv(path)


def calc_depth_usd(side_levels, mid_price: float, bps: float) -> float:
    if mid_price <= 0:
        return 0.0

    threshold = mid_price * (bps / 10000.0)
    total_usd = 0.0

    for price_str, qty_str in side_levels:
        price = to_float_safe(price_str)
        qty = to_float_safe(qty_str)
        if abs(price - mid_price) <= threshold:
            total_usd += price * qty

    return total_usd


def main():
    universe = load_top_pairs_df()
    rows = []

    for _, r in universe.iterrows():
        symbol = str(r["trading_pair"])

        try:
            book = http_get_json(
                f"{SPOT_API_BASE}/api/v3/depth",
                params={"symbol": symbol, "limit": ORDERBOOK_LIMIT}
            )

            bids = book.get("bids", [])
            asks = book.get("asks", [])

            if not bids or not asks:
                print(f"[WARN] Empty orderbook {symbol}")
                continue

            best_bid = to_float_safe(bids[0][0])
            best_ask = to_float_safe(asks[0][0])
            mid = (best_bid + best_ask) / 2.0 if best_bid and best_ask else 0.0
            spread_pct = ((best_ask - best_bid) / mid * 100.0) if mid > 0 else None

            depth_bid_10bps_usd = calc_depth_usd(bids, mid, 10)
            depth_ask_10bps_usd = calc_depth_usd(asks, mid, 10)
            depth_bid_25bps_usd = calc_depth_usd(bids, mid, 25)
            depth_ask_25bps_usd = calc_depth_usd(asks, mid, 25)
            depth_bid_50bps_usd = calc_depth_usd(bids, mid, 50)
            depth_ask_50bps_usd = calc_depth_usd(asks, mid, 50)

            quote_vol_24h = to_float_safe(r.get("quote_volume_24h", 0))
            trade_count_24h = int(float(r.get("trade_count_24h", 0))) if pd.notna(r.get("trade_count_24h")) else 0

            liquidity_score = (
                quote_vol_24h * 0.50 +
                (depth_bid_25bps_usd + depth_ask_25bps_usd) * 0.35 +
                max(trade_count_24h, 0) * 0.15
            )

            rows.append({
                "trading_pair": symbol,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "mid_price": mid,
                "spread_pct": spread_pct,
                "depth_bid_10bps_usd": depth_bid_10bps_usd,
                "depth_ask_10bps_usd": depth_ask_10bps_usd,
                "depth_bid_25bps_usd": depth_bid_25bps_usd,
                "depth_ask_25bps_usd": depth_ask_25bps_usd,
                "depth_bid_50bps_usd": depth_bid_50bps_usd,
                "depth_ask_50bps_usd": depth_ask_50bps_usd,
                "quote_volume_24h": quote_vol_24h,
                "trade_count_24h": trade_count_24h,
                "liquidity_score": liquidity_score
            })

            print(f"[OK] liquidity {symbol}")

        except Exception as e:
            print(f"[WARN] liquidity failed {symbol}: {e}")

    df = pd.DataFrame(rows).sort_values("liquidity_score", ascending=False)
    out_path = os.path.join(DATA_DIR, "liquidity_snapshot.csv")
    save_csv(df, out_path)


if __name__ == "__main__":
    main()