CONFIG = {
    "api": {
        "futures_ticker_url": "https://fapi.binance.com/fapi/v1/ticker/24hr",
        "futures_exchange_info_url": "https://fapi.binance.com/fapi/v1/exchangeInfo",
        "timeout": 15,
    },

    "filter": {
        "quote_asset": "USDT",

        "exclude_stablecoins": True,
        "stablecoins": [
            "USDT", "USDC", "BUSD", "FDUSD", "TUSD", "USDP", "DAI",
            "EUR", "EURT", "TRY", "UAH", "RUB", "BRL", "BIDR",
            "IDRT", "AUD", "GBP", "NGN", "ZAR"
        ],

        "exclude_pegged_tokens": True,
        "pegged_tokens": [
            "WBTC", "BBTC", "BTCB",
            "WETH", "WBETH", "BETH",
            "STETH", "WSTETH",
            "RENBTC", "SBTC"
        ],

        "exclude_base_assets": [],
        "exclude_base_asset_prefixes": [],
        "exclude_base_asset_suffixes": [],
        "exclude_symbols": []
    },

    "output": {
        "base_dir": "reports"
    }
}