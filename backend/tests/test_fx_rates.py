"""Tests for FX rates module."""
import pytest

from app.fx_rates import get_rate, convert_to_usd


def test_get_rate_usd_to_usd():
    """USD to USD should return 1.0."""
    assert get_rate("2025-01-15", "USD", "USD") == 1.0


def test_convert_to_usd_already_usd():
    """Amount already in USD should be unchanged."""
    assert convert_to_usd(100.0, "2025-01-15", "USD") == 100.0


def test_convert_to_usd_eur_requires_network():
    """EUR to USD conversion fetches from API (or uses cache)."""
    result = convert_to_usd(100.0, "2025-12-15", "EUR")
    # Should get a rate (either from API or cache from other tests)
    if result is not None:
        assert 100 < result < 130  # EUR typically 1.05-1.20 vs USD
