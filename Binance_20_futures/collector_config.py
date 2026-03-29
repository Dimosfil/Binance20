CONFIG = {
    "input": {
        "ranked_csv_dir": "reports",
        "ranked_csv_pattern": "binance_futures_ranked",
        "symbol_column": "symbol",
        "rank_column": "rank"
    },

    "selection": {
        "rank_start": 1,
        "rank_end": 20
    },

    "market": {
        "interval": "1h",
        "candles_limit": 1000
    },

    "futures_metrics": {
        "period": "1h",
        "limit": 200
    },

    "api": {
        "timeout": 20,
        "max_retries": 5,
        "retry_delay_seconds": 2,
        "request_pause_seconds": 0.2,

        "klines_url": "https://fapi.binance.com/fapi/v1/klines",
        "mark_price_klines_url": "https://fapi.binance.com/fapi/v1/markPriceKlines",
        "premium_index_url": "https://fapi.binance.com/fapi/v1/premiumIndex",
        "open_interest_url": "https://fapi.binance.com/fapi/v1/openInterest",
        "open_interest_hist_url": "https://fapi.binance.com/futures/data/openInterestHist",
        "funding_rate_url": "https://fapi.binance.com/fapi/v1/fundingRate",
        "global_long_short_account_ratio_url": "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
        "top_long_short_account_ratio_url": "https://fapi.binance.com/futures/data/topLongShortAccountRatio",
        "top_long_short_position_ratio_url": "https://fapi.binance.com/futures/data/topLongShortPositionRatio",
        "taker_long_short_ratio_url": "https://fapi.binance.com/futures/data/takerlongshortRatio"
    },

    "features_candles": {
        "open": True,
        "high": True,
        "low": True,
        "close": True,
        "volume": True,
        "quote_asset_volume": True,
        "number_of_trades": True,
        "taker_buy_base_volume": True,
        "taker_buy_quote_volume": True,

        "ema20": True,
        "ema50": True,
        "ema200": True,
        "rsi14": True,
        "atr14": True,
        "fibonacci": True,
        "mark_price_klines": True
    },

    "features_futures": {
        "open_interest_current": True,
        "open_interest_history": True,
        "funding_rate_current": True,
        "funding_history": True,
        "global_long_short_account_ratio": True,
        "top_long_short_account_ratio": True,
        "top_long_short_position_ratio": True,
        "taker_buy_sell_volume": True,
        "mark_price_snapshot": True
    },

    "fibonacci": {
        "lookback": 100,
        "retracement_levels": [0.236, 0.382, 0.5, 0.618, 0.786],
        "extension_levels": [1.272, 1.618, 2.0, 2.618]
    },

    "output": {
        "base_dir": "collected_data",
        "candles_file_prefix": "candles_indicators",
        "futures_file_prefix": "futures_metrics"
    }
}