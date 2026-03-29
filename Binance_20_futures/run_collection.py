import argparse

from build_ranked_futures_list import run_build_ranked_futures
from collect_candles_indicators import run_collect_candles
from collect_futures_metrics import run_collect_futures_metrics


def parse_args():
    parser = argparse.ArgumentParser(description="Универсальный сборщик данных Binance Futures")

    parser.add_argument("--interval", type=str, default="1h", help="Таймфрейм: 1h, 4h, 1d и т.д.")
    parser.add_argument("--rank-start", type=int, default=1, help="Начало диапазона ранга")
    parser.add_argument("--rank-end", type=int, default=20, help="Конец диапазона ранга")
    parser.add_argument("--candles-limit", type=int, default=1000, help="Количество свечей")
    parser.add_argument("--futures-limit", type=int, default=200, help="Количество исторических futures-точек")
    parser.add_argument("--output-dir", type=str, default="collected_data", help="Базовая папка для сохранения")
    parser.add_argument("--skip-rank-build", action="store_true", help="Не строить новый ranked CSV, использовать последний")
    parser.add_argument("--skip-candles", action="store_true", help="Пропустить сбор свечей и индикаторов")
    parser.add_argument("--skip-futures", action="store_true", help="Пропустить сбор фьючерсных метрик")

    return parser.parse_args()


def main():
    args = parse_args()

    ranked_csv_path = None
    ranked_rows = []

    if not args.skip_rank_build:
        print("Шаг 1/3: Строим полный рейтинг фьючерсов...")
        ranked_csv_path, ranked_rows = run_build_ranked_futures()
    else:
        print("Шаг 1/3: Построение рейтинга пропущено, будет использован последний ranked CSV")

    candles_csv_path = None
    futures_csv_path = None

    if not args.skip_candles:
        print("\nШаг 2/3: Собираем свечи и индикаторы...")
        candles_csv_path = run_collect_candles(
            ranked_csv_path=ranked_csv_path,
            interval=args.interval,
            rank_start=args.rank_start,
            rank_end=args.rank_end,
            candles_limit=args.candles_limit,
            output_dir=args.output_dir
        )

    if not args.skip_futures:
        print("\nШаг 3/3: Собираем фьючерсные метрики...")
        futures_csv_path = run_collect_futures_metrics(
            ranked_csv_path=ranked_csv_path,
            interval=args.interval,
            rank_start=args.rank_start,
            rank_end=args.rank_end,
            futures_limit=args.futures_limit,
            output_dir=args.output_dir
        )

    print("\nГотово.")
    print(f"Interval: {args.interval}")
    print(f"Rank range: {args.rank_start} - {args.rank_end}")
    print(f"Candles limit: {args.candles_limit}")
    print(f"Futures limit: {args.futures_limit}")

    if ranked_csv_path:
        print(f"Рейтинг: {ranked_csv_path}")
    if candles_csv_path:
        print(f"Свечи и индикаторы: {candles_csv_path}")
    if futures_csv_path:
        print(f"Фьючерсные метрики: {futures_csv_path}")

    if ranked_rows:
        print(f"Инструментов в полном рейтинге: {len(ranked_rows)}")


if __name__ == "__main__":
    main()