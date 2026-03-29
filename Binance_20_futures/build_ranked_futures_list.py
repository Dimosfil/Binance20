import csv
import os
from datetime import datetime

import requests

from config import CONFIG


def get_json(url, timeout=15):
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def normalize_list(values):
    return {str(v).upper() for v in values}


def get_futures_symbols():
    url = CONFIG["api"]["futures_exchange_info_url"]
    timeout = CONFIG["api"]["timeout"]

    data = get_json(url, timeout=timeout)
    symbols = {}

    for item in data.get("symbols", []):
        if item.get("status") != "TRADING":
            continue

        if item.get("contractType") != "PERPETUAL":
            continue

        symbol = item.get("symbol")
        symbols[symbol] = {
            "baseAsset": item.get("baseAsset", "").upper(),
            "quoteAsset": item.get("quoteAsset", "").upper(),
        }

    return symbols


def should_exclude(base_asset, symbol, filters):
    base_asset = base_asset.upper()
    symbol = symbol.upper()

    if filters["exclude_stablecoins"]:
        stablecoins = normalize_list(filters["stablecoins"])
        if base_asset in stablecoins:
            return True

    if filters["exclude_pegged_tokens"]:
        pegged_tokens = normalize_list(filters["pegged_tokens"])
        if base_asset in pegged_tokens:
            return True

    exclude_base_assets = normalize_list(filters["exclude_base_assets"])
    if base_asset in exclude_base_assets:
        return True

    exclude_symbols = normalize_list(filters["exclude_symbols"])
    if symbol in exclude_symbols:
        return True

    prefixes = normalize_list(filters["exclude_base_asset_prefixes"])
    for prefix in prefixes:
        if base_asset.startswith(prefix):
            return True

    suffixes = normalize_list(filters["exclude_base_asset_suffixes"])
    for suffix in suffixes:
        if base_asset.endswith(suffix):
            return True

    return False


def get_ranked_futures():
    filters = CONFIG["filter"]
    api = CONFIG["api"]

    symbol_meta = get_futures_symbols()
    tickers = get_json(api["futures_ticker_url"], timeout=api["timeout"])

    result = []
    quote_asset = filters["quote_asset"].upper()

    for item in tickers:
        symbol = str(item.get("symbol", "")).upper()
        if symbol not in symbol_meta:
            continue

        base_asset = symbol_meta[symbol]["baseAsset"]
        current_quote_asset = symbol_meta[symbol]["quoteAsset"]

        if current_quote_asset != quote_asset:
            continue

        if should_exclude(base_asset, symbol, filters):
            continue

        try:
            result.append({
                "symbol": symbol,
                "baseAsset": base_asset,
                "quoteAsset": current_quote_asset,
                "lastPrice": float(item["lastPrice"]),
                "priceChangePercent": float(item["priceChangePercent"]),
                "volume": float(item["volume"]),
                "quoteVolume": float(item["quoteVolume"]),
            })
        except (KeyError, ValueError, TypeError):
            continue

    result.sort(key=lambda x: x["quoteVolume"], reverse=True)

    ranked = []
    for i, row in enumerate(result, start=1):
        ranked.append({
            "rank": i,
            **row
        })

    return ranked


def create_output_path():
    base_dir = CONFIG["output"]["base_dir"]
    now = datetime.now()

    date_folder = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

    folder_path = os.path.join(base_dir, date_folder)
    os.makedirs(folder_path, exist_ok=True)

    return os.path.join(folder_path, f"binance_futures_ranked_{timestamp}.csv")


def save_to_csv(rows, filename):
    fieldnames = [
        "rank",
        "symbol",
        "baseAsset",
        "quoteAsset",
        "lastPrice",
        "priceChangePercent",
        "volume",
        "quoteVolume",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_preview(rows, preview_n=20):
    print(f"{'Rank':<6} {'Пара':<15} {'База':<12} {'Цена':<15} {'Изм.%':<10} {'Объем 24ч':>20}")
    print("-" * 95)

    for row in rows[:preview_n]:
        print(
            f"{row['rank']:<6} "
            f"{row['symbol']:<15} "
            f"{row['baseAsset']:<12} "
            f"{row['lastPrice']:<15.8f} "
            f"{row['priceChangePercent']:<10.2f} "
            f"{row['quoteVolume']:>20,.2f}"
        )


def run_build_ranked_futures():
    ranked_rows = get_ranked_futures()
    output_file = create_output_path()

    save_to_csv(ranked_rows, output_file)
    print_preview(ranked_rows, preview_n=20)

    print(f"\nПолный рейтинг сохранен: {output_file}")
    print(f"Всего инструментов в рейтинге: {len(ranked_rows)}")

    return output_file, ranked_rows


def main():
    run_build_ranked_futures()


if __name__ == "__main__":
    main()