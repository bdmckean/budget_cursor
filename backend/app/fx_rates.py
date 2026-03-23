"""
Currency conversion using Frankfurter API (free, no API key).
Caches rates by date to minimize API calls.
"""
import json
import logging
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).parent.parent / "fx_rates_cache.json"
FRANKFURTER_API = "https://api.frankfurter.dev/v1"


def _load_cache() -> dict:
    """Load rate cache from disk."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_cache(cache: dict) -> None:
    """Persist rate cache to disk."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def get_rate(date_str: str, from_currency: str, to_currency: str) -> Optional[float]:
    """
    Get exchange rate for a date. Converts 1 unit of from_currency to to_currency.
    Uses Frankfurter API with disk cache. Returns None if fetch fails.
    """
    from_currency = (from_currency or "").strip().upper()[:3]
    to_currency = (to_currency or "").strip().upper()[:3]

    if not from_currency or not to_currency:
        return None
    if from_currency == to_currency:
        return 1.0

    cache_key = f"{date_str}:{from_currency}:{to_currency}"
    cache = _load_cache()
    if cache_key in cache:
        return cache[cache_key]

    try:
        url = f"{FRANKFURTER_API}/{date_str}"
        params = {"from": from_currency, "to": to_currency}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rate = data.get("rates", {}).get(to_currency)
        if rate is not None:
            cache[cache_key] = rate
            _save_cache(cache)
            return rate
    except (requests.RequestException, KeyError) as e:
        logger.warning("FX rate fetch failed for %s: %s", cache_key, e)

    return None


def convert_to_usd(
    amount: float, date_str: str, from_currency: str
) -> Optional[float]:
    """
    Convert amount from given currency to USD using the rate for that date.
    Returns None if conversion fails (e.g. unsupported currency).
    """
    if from_currency.upper() == "USD":
        return amount
    rate = get_rate(date_str, from_currency, "USD")
    if rate is None:
        return None
    return round(amount * rate, 2)
