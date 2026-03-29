import argparse
import csv
import glob
import os
import time
from copy import deepcopy
from datetime import datetime, timezone

import requests

from collector_config import CONFIG as BASE_CONFIG


def build_runtime_config(interval=None, rank_start=None, rank_end=None, futures_limit=None, output_dir=None):
    config = deepcopy(BASE_CONFIG)

    if interval is not None:
        config["futures_metrics"]["period"] = interval

    if futures_limit is not None:
        config["futures_metrics"]["limit"] = futures_limit

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


def build_output_path(config):
    output_cfg = config["output"]
    selection = config["selection"]
    interval = config["futures_metrics"]["period"]
    now = datetime.now()

    date_folder = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

    folder = os.path.join(output_cfg["base_dir"], date_folder)
    os.makedirs(folder, exist_ok=True)

    return os.path.join(
        folder,
        f"{output_cfg['futures_file_prefix']}_{interval}_rank_{selection['rank_start']}_{selection['rank_end']}_{timestamp}.csv"
    )


def save_csv(rows, path):
    if not rows:
        print("Нет данных для сохранения")
        return

    all_keys = set()
    for row in rows:
        all_keys.update(row.keys())

    fieldnames = sorted(all_keys)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fetch_open_interest_current(config, symbol):
    return get_json(config, config["api"]["open_interest_url"], params={"symbol": symbol})


def fetch_open_interest_history(config, symbol):
    params = {
        "symbol": symbol,
        "period": config["futures_metrics"]["period"],
        "limit": config["futures_metrics"]["limit"]
    }
    return get_json(config, config["api"]["open_interest_hist_url"], params=params)


def fetch_funding_history(config, symbol):
    params = {
        "symbol": symbol,
        "limit": config["futures_metrics"]["limit"]
    }
    return get_json(config, config["api"]["funding_rate_url"], params=params)


def fetch_funding_rate_current(config, symbol):
    history = fetch_funding_history(config, symbol)
    return history[-1] if history else {}


def fetch_global_long_short_account_ratio(config, symbol):
    params = {
        "symbol": symbol,
        "period": config["futures_metrics"]["period"],
        "limit": config["futures_metrics"]["limit"]
    }
    return get_json(config, config["api"]["global_long_short_account_ratio_url"], params=params)


def fetch_top_long_short_account_ratio(config, symbol):
    params = {
        "symbol": symbol,
        "period": config["futures_metrics"]["period"],
        "limit": config["futures_metrics"]["limit"]
    }
    return get_json(config, config["api"]["top_long_short_account_ratio_url"], params=params)


def fetch_top_long_short_position_ratio(config, symbol):
    params = {
        "symbol": symbol,
        "period": config["futures_metrics"]["period"],
        "limit": config["futures_metrics"]["limit"]
    }
    return get_json(config, config["api"]["top_long_short_position_ratio_url"], params=params)


def fetch_taker_buy_sell_volume(config, symbol):
    params = {
        "symbol": symbol,
        "period": config["futures_metrics"]["period"],
        "limit": config["futures_metrics"]["limit"]
    }
    return get_json(config, config["api"]["taker_long_short_ratio_url"], params=params)


def fetch_mark_price_snapshot(config, symbol):
    return get_json(config, config["api"]["premium_index_url"], params={"symbol": symbol})


def rows_from_open_interest_current(symbol, data, interval):
    return [{
        "symbol": symbol,
        "interval": interval,
        "metric_type": "open_interest_current",
        "timestamp": data.get("time"),
        "datetime": ms_to_datetime_str(data.get("time")),
        "openInterest": data.get("openInterest"),
    }]


def rows_from_open_interest_history(symbol, data, interval):
    rows = []
    for item in data:
        ts = item.get("timestamp")
        rows.append({
            "symbol": symbol,
            "interval": interval,
            "metric_type": "open_interest_history",
            "timestamp": ts,
            "datetime": ms_to_datetime_str(ts),
            "sumOpenInterest": item.get("sumOpenInterest"),
            "sumOpenInterestValue": item.get("sumOpenInterestValue"),
            "cmcCirculatingSupply": item.get("CMCCirculatingSupply"),
        })
    return rows


def rows_from_funding_history(symbol, data, interval):
    rows = []
    for item in data:
        ts = item.get("fundingTime")
        rows.append({
            "symbol": symbol,
            "interval": interval,
            "metric_type": "funding_history",
            "timestamp": ts,
            "datetime": ms_to_datetime_str(ts),
            "fundingRate": item.get("fundingRate"),
            "markPrice": item.get("markPrice"),
        })
    return rows


def rows_from_funding_rate_current(symbol, data, interval):
    ts = data.get("fundingTime")
    return [{
        "symbol": symbol,
        "interval": interval,
        "metric_type": "funding_rate_current",
        "timestamp": ts,
        "datetime": ms_to_datetime_str(ts),
        "fundingRate": data.get("fundingRate"),
        "markPrice": data.get("markPrice"),
    }]


def rows_from_ratio(symbol, data, metric_type, interval):
    rows = []
    for item in data:
        ts = item.get("timestamp")
        row = {
            "symbol": symbol,
            "interval": interval,
            "metric_type": metric_type,
            "timestamp": ts,
            "datetime": ms_to_datetime_str(ts),
        }
        for k, v in item.items():
            if k != "timestamp":
                row[k] = v
        rows.append(row)
    return rows


def rows_from_mark_price_snapshot(symbol, data, interval):
    ts = data.get("time")
    return [{
        "symbol": symbol,
        "interval": interval,
        "metric_type": "mark_price_snapshot",
        "timestamp": ts,
        "datetime": ms_to_datetime_str(ts),
        "markPrice": data.get("markPrice"),
        "indexPrice": data.get("indexPrice"),
        "estimatedSettlePrice": data.get("estimatedSettlePrice"),
        "lastFundingRate": data.get("lastFundingRate"),
        "nextFundingTime": data.get("nextFundingTime"),
        "nextFundingDatetime": ms_to_datetime_str(data.get("nextFundingTime")),
        "interestRate": data.get("interestRate"),
    }]


def run_collect_futures_metrics(ranked_csv_path=None, interval=None, rank_start=None, rank_end=None, futures_limit=None, output_dir=None):
    config = build_runtime_config(
        interval=interval,
        rank_start=rank_start,
        rank_end=rank_end,
        futures_limit=futures_limit,
        output_dir=output_dir
    )

    if ranked_csv_path is None:
        ranked_csv_path = find_latest_ranked_csv(config)

    print(f"Используется ranked CSV: {ranked_csv_path}")
    print(f"Период futures-метрик: {config['futures_metrics']['period']}")
    print(f"Диапазон rank: {config['selection']['rank_start']} - {config['selection']['rank_end']}")
    print(f"Лимит futures-метрик: {config['futures_metrics']['limit']}")

    symbols = read_symbols_by_rank_range(
        ranked_csv_path,
        symbol_column=config["input"]["symbol_column"],
        rank_column=config["input"]["rank_column"],
        rank_start=config["selection"]["rank_start"],
        rank_end=config["selection"]["rank_end"]
    )

    print(f"Количество символов для сбора: {len(symbols)}")

    features = config["features_futures"]
    all_rows = []
    interval_value = config["futures_metrics"]["period"]

    for symbol in symbols:
        print(f"Сбор futures-метрик: {symbol}")

        if features["open_interest_current"]:
            try:
                all_rows.extend(rows_from_open_interest_current(symbol, fetch_open_interest_current(config, symbol), interval_value))
            except Exception as e:
                print(f"Ошибка open_interest_current {symbol}: {e}")

        if features["open_interest_history"]:
            try:
                all_rows.extend(rows_from_open_interest_history(symbol, fetch_open_interest_history(config, symbol), interval_value))
            except Exception as e:
                print(f"Ошибка open_interest_history {symbol}: {e}")

        if features["funding_history"]:
            try:
                all_rows.extend(rows_from_funding_history(symbol, fetch_funding_history(config, symbol), interval_value))
            except Exception as e:
                print(f"Ошибка funding_history {symbol}: {e}")

        if features["funding_rate_current"]:
            try:
                all_rows.extend(rows_from_funding_rate_current(symbol, fetch_funding_rate_current(config, symbol), interval_value))
            except Exception as e:
                print(f"Ошибка funding_rate_current {symbol}: {e}")

        if features["global_long_short_account_ratio"]:
            try:
                data = fetch_global_long_short_account_ratio(config, symbol)
                all_rows.extend(rows_from_ratio(symbol, data, "global_long_short_account_ratio", interval_value))
            except Exception as e:
                print(f"Ошибка global_long_short_account_ratio {symbol}: {e}")

        if features["top_long_short_account_ratio"]:
            try:
                data = fetch_top_long_short_account_ratio(config, symbol)
                all_rows.extend(rows_from_ratio(symbol, data, "top_long_short_account_ratio", interval_value))
            except Exception as e:
                print(f"Ошибка top_long_short_account_ratio {symbol}: {e}")

        if features["top_long_short_position_ratio"]:
            try:
                data = fetch_top_long_short_position_ratio(config, symbol)
                all_rows.extend(rows_from_ratio(symbol, data, "top_long_short_position_ratio", interval_value))
            except Exception as e:
                print(f"Ошибка top_long_short_position_ratio {symbol}: {e}")

        if features["taker_buy_sell_volume"]:
            try:
                data = fetch_taker_buy_sell_volume(config, symbol)
                all_rows.extend(rows_from_ratio(symbol, data, "taker_buy_sell_volume", interval_value))
            except Exception as e:
                print(f"Ошибка taker_buy_sell_volume {symbol}: {e}")

        if features["mark_price_snapshot"]:
            try:
                all_rows.extend(rows_from_mark_price_snapshot(symbol, fetch_mark_price_snapshot(config, symbol), interval_value))
            except Exception as e:
                print(f"Ошибка mark_price_snapshot {symbol}: {e}")

    output_path = build_output_path(config)
    save_csv(all_rows, output_path)

    print(f"\nГотово. CSV сохранен: {output_path}")
    return output_path


def parse_args():
    parser = argparse.ArgumentParser(description="Сбор futures-метрик Binance Futures")
    parser.add_argument("--interval", type=str, default=None, help="Период метрик, например 1h, 4h, 1d")
    parser.add_argument("--rank-start", type=int, default=None, help="Начало диапазона ранга")
    parser.add_argument("--rank-end", type=int, default=None, help="Конец диапазона ранга")
    parser.add_argument("--futures-limit", type=int, default=None, help="Количество исторических точек на инструмент")
    parser.add_argument("--output-dir", type=str, default=None, help="Папка для сохранения")
    return parser.parse_args()


def main():
    args = parse_args()

    run_collect_futures_metrics(
        interval=args.interval,
        rank_start=args.rank_start,
        rank_end=args.rank_end,
        futures_limit=args.futures_limit,
        output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()