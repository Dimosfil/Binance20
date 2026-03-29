import argparse
import csv
import glob
import os
import time
from copy import deepcopy
from datetime import datetime, timezone

import requests

from collector_config import CONFIG as BASE_CONFIG


def build_runtime_config(interval=None, rank_start=None, rank_end=None, candles_limit=None, output_dir=None):
    config = deepcopy(BASE_CONFIG)

    if interval is not None:
        config["market"]["interval"] = interval

    if candles_limit is not None:
        config["market"]["candles_limit"] = candles_limit

    if rank_start is not None:
        config["selection"]["rank_start"] = rank_start

    if rank_end is not None:
        config["selection"]["rank_end"] = rank_end

    if output_dir is not None:
        config["output"]["base_dir"] = output_dir

    return config


def sleep_pause(config):
    time.sleep(config["api"]["request_pause_seconds"])


def get_json(config, url, params=None):
    timeout = config["api"]["timeout"]
    max_retries = config["api"]["max_retries"]
    retry_delay = config["api"]["retry_delay_seconds"]

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            sleep_pause(config)
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            last_error = e
            print(f"Ошибка запроса ({attempt}/{max_retries}) {url} params={params}: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)

    raise last_error


def ms_to_datetime_str(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def find_latest_ranked_csv(config):
    input_cfg = config["input"]
    search_pattern = os.path.join(input_cfg["ranked_csv_dir"], "**", "*.csv")
    files = glob.glob(search_pattern, recursive=True)

    filtered = []
    for path in files:
        if input_cfg["ranked_csv_pattern"] in os.path.basename(path):
            filtered.append(path)

    if not filtered:
        raise FileNotFoundError("Не найден ни один ranked CSV файл")

    filtered.sort(key=os.path.getmtime, reverse=True)
    return filtered[0]


def read_symbols_by_rank_range(file_path, symbol_column, rank_column, rank_start, rank_end):
    symbols = []

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rank = int(row.get(rank_column, 0))
            except (ValueError, TypeError):
                continue

            if rank_start <= rank <= rank_end:
                symbol = row.get(symbol_column, "").strip().upper()
                if symbol:
                    symbols.append(symbol)

    return symbols


def ema(values, period):
    result = [None] * len(values)
    if len(values) < period:
        return result

    multiplier = 2 / (period + 1)
    sma = sum(values[:period]) / period
    result[period - 1] = sma

    prev_ema = sma
    for i in range(period, len(values)):
        prev_ema = (values[i] - prev_ema) * multiplier + prev_ema
        result[i] = prev_ema

    return result


def rsi(values, period=14):
    result = [None] * len(values)
    if len(values) <= period:
        return result

    gains = []
    losses = []

    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    result[period] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))

    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = max(delta, 0)
        loss = abs(min(delta, 0))

        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period

        result[i] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))

    return result


def atr(highs, lows, closes, period=14):
    result = [None] * len(closes)
    if len(closes) <= period:
        return result

    tr_values = [None]
    for i in range(1, len(closes)):
        tr_values.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        ))

    first_atr = sum(tr_values[1:period + 1]) / period
    result[period] = first_atr

    prev_atr = first_atr
    for i in range(period + 1, len(closes)):
        prev_atr = ((prev_atr * (period - 1)) + tr_values[i]) / period
        result[i] = prev_atr

    return result


def calc_fibonacci(highs, lows, closes, lookback, retracement_levels, extension_levels):
    if len(closes) < lookback:
        return {}

    recent_high = max(highs[-lookback:])
    recent_low = min(lows[-lookback:])
    diff = recent_high - recent_low

    if diff == 0:
        return {}

    result = {
        "fib_high": recent_high,
        "fib_low": recent_low,
        "fib_range": diff,
        "fib_last_close": closes[-1]
    }

    for level in retracement_levels:
        result[f"fib_retr_{level}"] = recent_high - diff * level

    for level in extension_levels:
        result[f"fib_ext_{level}"] = recent_low + diff * level

    return result


def fetch_klines(config, symbol):
    params = {
        "symbol": symbol,
        "interval": config["market"]["interval"],
        "limit": config["market"]["candles_limit"]
    }

    data = get_json(config, config["api"]["klines_url"], params=params)

    rows = []
    for item in data:
        rows.append({
            "timestamp": int(item[0]),
            "datetime": ms_to_datetime_str(int(item[0])),
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
            "close_time": int(item[6]),
            "close_datetime": ms_to_datetime_str(int(item[6])),
            "quote_asset_volume": float(item[7]),
            "number_of_trades": int(item[8]),
            "taker_buy_base_volume": float(item[9]),
            "taker_buy_quote_volume": float(item[10]),
        })
    return rows


def fetch_mark_price_klines(config, symbol):
    params = {
        "symbol": symbol,
        "interval": config["market"]["interval"],
        "limit": config["market"]["candles_limit"]
    }

    data = get_json(config, config["api"]["mark_price_klines_url"], params=params)

    result = {}
    for item in data:
        ts = int(item[0])
        result[ts] = {
            "mark_open": float(item[1]),
            "mark_high": float(item[2]),
            "mark_low": float(item[3]),
            "mark_close": float(item[4]),
            "mark_volume": float(item[5]),
        }
    return result


def build_output_path(config):
    output_cfg = config["output"]
    selection = config["selection"]
    interval = config["market"]["interval"]
    now = datetime.now()

    date_folder = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

    folder = os.path.join(output_cfg["base_dir"], date_folder)
    os.makedirs(folder, exist_ok=True)

    return os.path.join(
        folder,
        f"{output_cfg['candles_file_prefix']}_{interval}_rank_{selection['rank_start']}_{selection['rank_end']}_{timestamp}.csv"
    )


def save_csv(rows, path):
    if not rows:
        print("Нет данных для сохранения")
        return

    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def process_symbol(config, symbol):
    features = config["features_candles"]
    fib_cfg = config["fibonacci"]

    rows = fetch_klines(config, symbol)
    if not rows:
        return []

    closes = [row["close"] for row in rows]
    highs = [row["high"] for row in rows]
    lows = [row["low"] for row in rows]

    ema20_values = ema(closes, 20) if features["ema20"] else [None] * len(rows)
    ema50_values = ema(closes, 50) if features["ema50"] else [None] * len(rows)
    ema200_values = ema(closes, 200) if features["ema200"] else [None] * len(rows)
    rsi14_values = rsi(closes, 14) if features["rsi14"] else [None] * len(rows)
    atr14_values = atr(highs, lows, closes, 14) if features["atr14"] else [None] * len(rows)

    fib_data = {}
    if features["fibonacci"]:
        fib_data = calc_fibonacci(
            highs,
            lows,
            closes,
            fib_cfg["lookback"],
            fib_cfg["retracement_levels"],
            fib_cfg["extension_levels"]
        )

    mark_map = {}
    if features["mark_price_klines"]:
        try:
            mark_map = fetch_mark_price_klines(config, symbol)
        except Exception as e:
            print(f"Не удалось получить markPriceKlines для {symbol}: {e}")

    output_rows = []
    for i, row in enumerate(rows):
        out = {
            "symbol": symbol,
            "interval": config["market"]["interval"],
            "timestamp": row["timestamp"],
            "datetime": row["datetime"]
        }

        if features["open"]:
            out["open"] = row["open"]
        if features["high"]:
            out["high"] = row["high"]
        if features["low"]:
            out["low"] = row["low"]
        if features["close"]:
            out["close"] = row["close"]
        if features["volume"]:
            out["volume"] = row["volume"]
        if features["quote_asset_volume"]:
            out["quote_asset_volume"] = row["quote_asset_volume"]
        if features["number_of_trades"]:
            out["number_of_trades"] = row["number_of_trades"]
        if features["taker_buy_base_volume"]:
            out["taker_buy_base_volume"] = row["taker_buy_base_volume"]
        if features["taker_buy_quote_volume"]:
            out["taker_buy_quote_volume"] = row["taker_buy_quote_volume"]

        if features["ema20"]:
            out["ema20"] = ema20_values[i]
        if features["ema50"]:
            out["ema50"] = ema50_values[i]
        if features["ema200"]:
            out["ema200"] = ema200_values[i]
        if features["rsi14"]:
            out["rsi14"] = rsi14_values[i]
        if features["atr14"]:
            out["atr14"] = atr14_values[i]

        if features["fibonacci"]:
            out.update(fib_data)

        if features["mark_price_klines"]:
            mark = mark_map.get(row["timestamp"], {})
            out["mark_open"] = mark.get("mark_open")
            out["mark_high"] = mark.get("mark_high")
            out["mark_low"] = mark.get("mark_low")
            out["mark_close"] = mark.get("mark_close")
            out["mark_volume"] = mark.get("mark_volume")

        output_rows.append(out)

    return output_rows


def run_collect_candles(ranked_csv_path=None, interval=None, rank_start=None, rank_end=None, candles_limit=None, output_dir=None):
    config = build_runtime_config(
        interval=interval,
        rank_start=rank_start,
        rank_end=rank_end,
        candles_limit=candles_limit,
        output_dir=output_dir
    )

    if ranked_csv_path is None:
        ranked_csv_path = find_latest_ranked_csv(config)

    print(f"Используется ranked CSV: {ranked_csv_path}")
    print(f"Таймфрейм свечей: {config['market']['interval']}")
    print(f"Диапазон rank: {config['selection']['rank_start']} - {config['selection']['rank_end']}")
    print(f"Лимит свечей: {config['market']['candles_limit']}")

    symbols = read_symbols_by_rank_range(
        ranked_csv_path,
        symbol_column=config["input"]["symbol_column"],
        rank_column=config["input"]["rank_column"],
        rank_start=config["selection"]["rank_start"],
        rank_end=config["selection"]["rank_end"]
    )

    print(f"Количество символов для сбора: {len(symbols)}")

    all_rows = []
    for symbol in symbols:
        print(f"Сбор свечей и индикаторов: {symbol}")
        try:
            all_rows.extend(process_symbol(config, symbol))
        except Exception as e:
            print(f"Ошибка по {symbol}: {e}")

    output_path = build_output_path(config)
    save_csv(all_rows, output_path)

    print(f"\nГотово. CSV сохранен: {output_path}")
    return output_path


def parse_args():
    parser = argparse.ArgumentParser(description="Сбор свечей и индикаторов Binance Futures")
    parser.add_argument("--interval", type=str, default=None, help="Таймфрейм свечей, например 1h, 4h, 1d")
    parser.add_argument("--rank-start", type=int, default=None, help="Начало диапазона ранга")
    parser.add_argument("--rank-end", type=int, default=None, help="Конец диапазона ранга")
    parser.add_argument("--candles-limit", type=int, default=None, help="Количество свечей на инструмент")
    parser.add_argument("--output-dir", type=str, default=None, help="Папка для сохранения")
    return parser.parse_args()


def main():
    args = parse_args()

    run_collect_candles(
        interval=args.interval,
        rank_start=args.rank_start,
        rank_end=args.rank_end,
        candles_limit=args.candles_limit,
        output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()