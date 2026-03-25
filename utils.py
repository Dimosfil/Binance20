import time
import requests
import pandas as pd
from typing import Optional
from config import REQUEST_TIMEOUT, REQUEST_SLEEP_SEC


def http_get_json(url: str, params: Optional[dict] = None):
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    time.sleep(REQUEST_SLEEP_SEC)
    return response.json()


def to_float_safe(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def save_csv(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[OK] Saved: {path} | rows={len(df)}")