"""
Module: test_utils.py
Description: Unit tests for bonous-feature utility classes and functions.

Tests cover:
    - QueryCache: get/set, TTL expiration, eviction, clear, hit/miss stats
    - RateLimiter: allow/deny, sliding window, remaining, reset, stats
    - generate_chart: bar/line/pie auto-detection, forced type, edge cases
    
Usage:
    pytest tests/test_utils.py -v
    
    
    
"""

# ==============================================================
# IMPORTS
# ==============================================================

import time
from unittest.mock import patch

import pandas as pd
import pytest

from utils import QueryCache, RateLimiter, generate_chart

# ==============================================================
# QUERY CACHE TESTS
# ==============================================================


class TestQueryCache:
    """Tests for the QueryCache class."""

    def test_set_and_get_returns_cached_value(self) -> None:
        """A value stored via set() should be returned by get()."""
        cache = QueryCache(max_size=10, ttl_seconds=300)
        response = {"row_count": 42}
        cache.set("How many patients?", response)

        result = cache.get("How many patients?")
        assert result == response

    def test_get_missing_key_returns_none(self) -> None:
        """Requesting a key that was never stored should return None."""
        cache = QueryCache(max_size=10, ttl_seconds=300)
        assert cache.get("nonexistent question") is None

    def test_normalisation_ignores_case_and_whitespace(self) -> None:
        """Variations in case and surrounding whitespace should resolve to the same entry."""
        cache = QueryCache(max_size=10, ttl_seconds=300)
        cache.set("How many patients?", {"count": 200})

        # Same question with different casing and extra spaces
        assert cache.get("  HOW MANY PATIENTS?  ") == {"count": 200}

    def test_ttl_expiration(self) -> None:
        """Entries older than TTL seconds should be evicted on access."""
        cache = QueryCache(max_size=10, ttl_seconds=1)
        cache.set("question", {"data": True})

        # Simulate time passing beyond the TTL
        time.sleep(1.1)

        assert cache.get("question") is None

    def test_eviction_at_max_size(self) -> None:
        """When at capacity, the oldest entry should be evicted on insert."""
        cache = QueryCache(max_size=2, ttl_seconds=300)
        cache.set("q1", {"id": 1})
        cache.set("q2", {"id": 2})

        # This insert should evict q1 (oldest)
        cache.set("q3", {"id": 3})

        assert cache.get("q1") is None
        assert cache.get("q2") == {"id": 2}
        assert cache.get("q3") == {"id": 3}

    def test_size_property(self) -> None:
        """The size property should reflect the current entry count."""
        cache = QueryCache(max_size=10, ttl_seconds=300)
        assert cache.size == 0

        cache.set("q1", {"data": 1})
        assert cache.size == 1

        cache.set("q2", {"data": 2})
        assert cache.size == 2

    def test_clear_removes_all_entries(self) -> None:
        """clear() should empty the cache and return the evicted count."""
        cache = QueryCache(max_size=10, ttl_seconds=300)
        cache.set("q1", {"data": 1})
        cache.set("q2", {"data": 2})

        removed = cache.clear()
        assert removed == 2
        assert cache.size == 0
        assert cache.get("q1") is None

    def test_hit_miss_counters(self) -> None:
        """Hits and misses should be tracked separately."""
        cache = QueryCache(max_size=10, ttl_seconds=300)
        cache.set("q1", {"data": 1})

        cache.get("q1")  # hit
        cache.get("q1")  # hit
        cache.get("missing")  # miss

        info = cache.info()
        assert info["hits"] == 2
        assert info["misses"] == 1

    def test_info_returns_complete_stats(self) -> None:
        """info() should include size, max_size, ttl, hits, and misses."""
        cache = QueryCache(max_size=50, ttl_seconds=120)
        info = cache.info()

        assert info["size"] == 0
        assert info["max_size"] == 50
        assert info["ttl_seconds"] == 120
        assert info["hits"] == 0
        assert info["misses"] == 0

    def test_overwrite_existing_key(self) -> None:
        """Setting the same question twice should overwrite the old value."""
        cache = QueryCache(max_size=10, ttl_seconds=300)
        cache.set("q1", {"version": 1})
        cache.set("q1", {"version": 2})

        assert cache.get("q1") == {"version": 2}
        # Should still only be one entry
        assert cache.size == 1


# ================================================================
# RATE LIMITER TESTS
# ================================================================

class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_allows_within_limit(self) -> None:
        """Requests within the limit should be allowed."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.1") is True

    def test_blocks_over_limit(self) -> None:
        """The request exceeding the limit should be denied."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.is_allowed("10.0.0.1")  # 1
        limiter.is_allowed("10.0.0.1")  # 2
        assert limiter.is_allowed("10.0.0.1") is False  # 3rd -> blocked

    def test_separate_ips_are_independent(self) -> None:
        """Rate limits should be tracked per IP, not globally."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.2") is True
        # First IP is now over the limit
        assert limiter.is_allowed("10.0.0.1") is False

    def test_window_expires_allows_again(self) -> None:
        """After the window expires, requests should be allowed again."""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.1") is False

        time.sleep(1.1)
        assert limiter.is_allowed("10.0.0.1") is True

    def test_remaining_reports_correctly(self) -> None:
        """remaining() should decrease as requests are made."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.remaining("10.0.0.1") == 5

        limiter.is_allowed("10.0.0.1")
        assert limiter.remaining("10.0.0.1") == 4

        limiter.is_allowed("10.0.0.1")
        assert limiter.remaining("10.0.0.1") == 3

    def test_reset_single_ip(self) -> None:
        """reset(ip) should clear only that IP's history."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.is_allowed("10.0.0.1")
        limiter.is_allowed("10.0.0.2")

        limiter.reset("10.0.0.1")
        # IP 1 should be allowed again; IP 2 should still be blocked
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.2") is False

    def test_reset_all_ips(self) -> None:
        """reset() with no argument should clear all tracked IPs."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.is_allowed("10.0.0.1")
        limiter.is_allowed("10.0.0.2")

        limiter.reset()
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.2") is True

    def test_info_returns_stats(self) -> None:
        """info() should include counters and configuration values."""
        limiter = RateLimiter(max_requests=5, window_seconds=30)
        limiter.is_allowed("10.0.0.1")  # allowed
        limiter.is_allowed("10.0.0.1")  # allowed

        info = limiter.info()
        assert info["max_requests_per_window"] == 5
        assert info["window_seconds"] == 30
        assert info["tracked_ips"] == 1
        assert info["total_allowed"] == 2
        assert info["total_rejected"] == 0

    def test_info_tracks_rejections(self) -> None:
        """Rejected requests should increment the rejected counter."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.is_allowed("10.0.0.1")  # allowed
        limiter.is_allowed("10.0.0.1")  # rejected

        info = limiter.info()
        assert info["total_allowed"] == 1
        assert info["total_rejected"] == 1


# ================================================================
# CHART GENERATION TESTS
# ================================================================

class TestGenerateChart:
    """Tests for the generate_chart() function."""

    def _make_df(self, data: dict) -> pd.DataFrame:
        """Helper to create a DataFrame from a column dict."""
        return pd.DataFrame(data)

    # ------------------------------------------------------------------
    # Edge cases that should return None
    # ------------------------------------------------------------------

    def test_none_dataframe_returns_none(self) -> None:
        """None input should return None."""
        assert generate_chart(None, "test") is None

    def test_empty_dataframe_returns_none(self) -> None:
        """An empty DataFrame should return None."""
        df = pd.DataFrame()
        assert generate_chart(df, "test") is None

    def test_single_column_returns_none(self) -> None:
        """A single-column DataFrame has nothing to plot on two axes."""
        df = self._make_df({"count": [10, 20]})
        assert generate_chart(df, "test") is None

    def test_no_numeric_columns_returns_none(self) -> None:
        """Without numeric data there is no value axis to plot."""
        df = self._make_df({"name": ["Alice", "Bob"], "city": ["A", "B"]})
        assert generate_chart(df, "test") is None

    # ------------------------------------------------------------------
    # Auto-detection: bar chart (default)
    # ------------------------------------------------------------------

    def test_default_is_bar_chart(self) -> None:
        """A simple category + count dataset should produce a bar chart."""
        df = self._make_df({"city": ["Mumbai", "Delhi"], "count": [100, 80]})
        result = generate_chart(df, "How many patients per city?")

        assert result is not None
        assert result["chart_type"] == "bar"
        assert "chart" in result

    # ------------------------------------------------------------------
    # Auto-detection: line chart
    # ------------------------------------------------------------------

    def test_date_column_triggers_line_chart(self) -> None:
        """A column named 'month' should trigger line chart detection."""
        df = self._make_df(
            {
                "month": ["2026-01", "2026-02", "2026-03"],
                "count": [40, 55, 60],
            }
        )
        result = generate_chart(df, "Show monthly appointment counts")

        assert result is not None
        assert result["chart_type"] == "line"

    def test_trend_keyword_triggers_line_chart(self) -> None:
        """The word 'trend' in the question should trigger line chart."""
        df = self._make_df(
            {
                "category": ["Q1", "Q2", "Q3"],
                "revenue": [1000, 1500, 1200],
            }
        )
        result = generate_chart(df, "Show revenue trend")

        assert result is not None
        assert result["chart_type"] == "line"

    # ------------------------------------------------------------------
    # Auto-detection: pie chart
    # ------------------------------------------------------------------

    def test_distribution_keyword_triggers_pie_chart(self) -> None:
        """The word 'distribution' with few categories → pie chart."""
        df = self._make_df(
            {
                "status": ["Paid", "Pending", "Overdue"],
                "count": [55, 30, 15],
            }
        )
        result = generate_chart(df, "Show invoice status distribution")

        assert result is not None
        assert result["chart_type"] == "pie"

    def test_by_status_triggers_pie_chart(self) -> None:
        """'by status' in the question should trigger pie chart."""
        df = self._make_df(
            {
                "status": ["Completed", "Cancelled", "No-Show"],
                "count": [250, 100, 75],
            }
        )
        result = generate_chart(df, "Appointment count by status")

        assert result is not None
        assert result["chart_type"] == "pie"

    def test_too_many_categories_falls_back_to_bar(self) -> None:
        """Pie detection should fall back to bar when rows exceed threshold."""
        df = self._make_df(
            {
                "city": [f"City_{i}" for i in range(12)],
                "count": list(range(12)),
            }
        )
        result = generate_chart(df, "Patient distribution by city")

        assert result is not None
        # 12 > CHART_PIE_MAX_CATEGORIES (8) → should be bar, not pie
        assert result["chart_type"] == "bar"

    # ------------------------------------------------------------------
    # Forced chart type
    # ------------------------------------------------------------------

    def test_forced_chart_type_overrides_auto(self) -> None:
        """Explicitly passing chart_type should override auto-detection."""
        df = self._make_df(
            {
                "month": ["2026-01", "2026-02"],
                "count": [40, 55],
            }
        )
        # Would auto-detect as 'line', but we force 'bar'
        result = generate_chart(df, "Monthly counts", chart_type="bar")

        assert result is not None
        assert result["chart_type"] == "bar"

    def test_forced_pie_chart(self) -> None:
        """Forcing 'pie' should produce a pie chart regardless of data shape."""
        df = self._make_df(
            {
                "category": ["A", "B", "C"],
                "value": [10, 20, 30],
            }
        )
        result = generate_chart(df, "some question", chart_type="pie")

        assert result is not None
        assert result["chart_type"] == "pie"

    # ------------------------------------------------------------------
    # Output structure
    # ------------------------------------------------------------------

    def test_chart_output_has_plotly_structure(self) -> None:
        """The chart dict should contain Plotly's data and layout keys."""
        df = self._make_df({"x": ["a", "b"], "y": [1, 2]})
        result = generate_chart(df, "test question")

        assert result is not None
        chart = result["chart"]
        assert "data" in chart
        assert "layout" in chart
        
        
# ===============================================================
# MAIN EXECUTION
# ===============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])