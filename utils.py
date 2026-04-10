"""
Module: utils.py
Description: Shared utilities for the NL2SQL Clinic Chatbot.

Provides common utilities used across multiple modules:
    - Structured logging setup with per-module loggers
    - Query caching (in memory, SHA-256 key normalisation, TTL expiration)
    - Rate limiting (per-IP, sliding window with statistics)
    - Chart generation helpers (Plotly auto-detection: bar, line, pie)



"""




# ==============================================================
# IMPORTS
# ==============================================================

import hashlib
import json
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px

from config import (
    CACHE_MAX_SIZE,
    CACHE_TTL_SECONDS,
    CHART_DATE_INDICATORS,
    CHART_PIE_KEYWORDS,
    CHART_PIE_MAX_CATEGORIES,
    CHART_TREND_KEYWORDS,
    LOG_LEVEL,
    LOG_FORMAT,
    RATE_LIMIT_MAX_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
)

# ==============================================================
# CONSTANTS
# ==============================================================

logger = logging.getLogger(__name__)

# ==============================================================
# FUNCTIONS - LOGGING
# ==============================================================

def setup_logging(level: str = LOG_LEVEL) -> logging.Loggers:
    """Configure structured logging for the entire application.

    Sets up the root logger with a consistent timestamp + module + level 
    format so every log line across all modules is uniform and easy to 
    parse by humans and log-aggregation tools alike.

    Args:
        level: Logging level string (e.g. "INFO", "DEBUG", "WARNING"). 
            Defaults to the value of ``config.LOG_LEVEL``.

    Returns:
        The application-wide ``nl2sql`` logger instance.

    Example:
        >>> app_logger = setup_logging("DEBUG")
        >>> app_logger.info("Server starting up")
        2026-04-08 12:00:00 | nl2sql | INFO | Server starting up
    """

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format=LOG_FORMAT, 
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    app_logger = logging.getLogger("nl2sql")
    app_logger.setLevel(numeric_level)

    return app_logger



# ==============================================================
# FUNCTIONS - CHART GENERATION
# ==============================================================

def _detect_chart_type(
    df: pd.DataFrame,
    question: str,
    columns: List[str],
    numeric_cols: List[str],
) -> str:
    """Determine the best chart type from data shape and question keywords.

    Decision logic (evaluated in priority order):
        1. Date/time column **or** trend keyword -> ``line``
        2. Distribution/proportion keyword **and** <= MAX categories -> ``pie``
        3. Everything else -> ``bar``

    Args:
        df: Query result DataFrame.
        question: Original natural-language question.
        columns: All column names in the DataFrame.
        numeric_cols: Subset of column names that are numeric.

    Returns:
        One of ``"line"``, ``"pie"``, or ``"bar"``.
    """
    question_lower = question.lower()

    # --- Check for temporal / trend data -> line chart -------------------------
    has_date_col = any(
        any(ind in col.lower() for ind in CHART_DATE_INDICATORS)
        for col in columns
    )
    is_trend_question = any(kw in question_lower for kw in CHART_TREND_KEYWORDS)

    if has_date_col or is_trend_question:
        return "line"

    # --- Check for distribution / proportion data -> pie chart -----------------
    is_pie_question = any(kw in question_lower for kw in CHART_PIE_KEYWORDS)
    # Also treat "by status", "by gender", "by city" as distribution queries
    has_distribution_grouping = any(
        f"by {grp}" in question_lower
        for grp in ("status", "gender", "city", "specialization", "department", "type")
    )

    if (is_pie_question or has_distribution_grouping) and len(df) <= CHART_PIE_MAX_CATEGORIES:
        return "pie"

    # --- Default: bar chart ----------------------------------------------------
    return "bar"


def generate_chart(
    df: pd.DataFrame,
    question: str,
    chart_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Auto-detect chart type and generate a Plotly JSON-serialisable dict.

    Heuristics (when ``chart_type`` is not forced):
      - Date/time column **or** trend keyword in question -> **line** chart
      - Distribution keyword **or** "by <category>" pattern with
        <= ``CHART_PIE_MAX_CATEGORIES`` rows -> **pie** chart
      - All other grouped/aggregated results -> **bar** chart

    Args:
        df: Query result as a DataFrame.
        question: Original natural-language question (drives heuristics).
        chart_type: Force a specific chart type (``"bar"``, ``"line"``,
            ``"pie"``). When ``None``, the type is auto-detected.

    Returns:
        A dict with keys ``"chart"`` (Plotly JSON) and ``"chart_type"``
        (string), or ``None`` when the data shape is not suitable for
        visualisation (e.g. single-column result or zero rows).
    
    Example:
        >>> result = generate_chart(df, "Revenue by month")
        >>> result["chart_type"]
        "line"
    """
    # Guard: need at least two columns and one row for a meaningful chart
    if df is None or df.empty or len(df.columns) < 2:
        return None

    cols = df.columns.tolist()
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    non_numeric_cols = [c for c in cols if c not in numeric_cols]

    # A chart requires at least one numeric axis for the value dimension
    if not numeric_cols:
        return None

    # Choose axis columns: first non-numeric as x, first numeric as y
    x_col = non_numeric_cols[0] if non_numeric_cols else cols[0]
    y_col = numeric_cols[0]

    # Resolve chart type through heuristic helper when not explicitly given
    if chart_type is None:
        chart_type = _detect_chart_type(df, question, cols, numeric_cols)

    try:
        # Truncate long questions for chart titles to keep layout tidy
        title = question[:80] + ("..." if len(question) > 80 else "")

        if chart_type == "line":
            fig = px.line(
                df, x=x_col, y=y_col, title=title,
                markers=True,
                labels={x_col: x_col.replace("_", " ").title(),
                        y_col: y_col.replace("_", " ").title()},
            )
        elif chart_type == "pie":
            fig = px.pie(
                df, names=x_col, values=y_col, title=title,
                hole=0.3,  # donut style for better readability
            )
        else:  # default: bar
            fig = px.bar(
                df, x=x_col, y=y_col, title=title,
                labels={x_col: x_col.replace("_", " ").title(),
                        y_col: y_col.replace("_", " ").title()},
            )

        # Apply a clean, minimal layout that works in both light and dark UIs
        fig.update_layout(
            template="plotly_white",
            margin=dict(l=40, r=20, t=50, b=40),
        )

        chart_json = json.loads(fig.to_json())
        logger.info(
            "Chart generated | type=%s rows=%d x=%s y=%s",
            chart_type, len(df), x_col, y_col,
        )
        return {
            "chart": chart_json,
            "chart_type": chart_type,
        }

    except Exception as exc:
        logger.warning("Chart generation failed for type '%s': %s", chart_type, exc)
        return None


# ============================================================================
# CLASSES
# ============================================================================

class QueryCache:
    """In-memory cache for storing repeated question-response pairs.

    Uses SHA-256 hashed keys derived from normalised questions and
    TTL-based expiration to avoid stale responses. Tracks hit/miss
    statistics for observability in the ``/health`` endpoint.

    Attributes:
        _cache: Internal dict mapping hash -> {response, timestamp}.
        _max_size: Maximum number of cached entries before eviction.
        _ttl: Time-to-live in seconds for each cache entry.
        _hits: Number of cache hits since instantiation.
        _misses: Number of cache misses since instantiation.

    Example:
        >>> cache = QueryCache(max_size=100, ttl_seconds=300)
        >>> cache.set("How many patients?", {"row_count": 200})
        >>> cache.get("How many patients?")
        {'row_count': 200}
        >>> cache.info()
        {'size': 1, 'max_size': 100, 'ttl_seconds': 300, 'hits': 1, 'misses': 0}
    """

    def __init__(
        self,
        max_size: int = CACHE_MAX_SIZE,
        ttl_seconds: int = CACHE_TTL_SECONDS,
    ) -> None:
        """Initialise the cache with size and TTL limits.

        Args:
            max_size: Maximum entries before oldest is evicted.
            ttl_seconds: Seconds until a cache entry expires.
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hits: int = 0
        self._misses: int = 0

    # --------------------------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------------------------

    def _make_key(self, question: str) -> str:
        """Create a stable cache key from a normalised question string.

        Normalises whitespace and case so that cosmetic variations such as
        extra spaces or mixed capitalisation resolve to the same entry.

        Args:
            question: Raw question string.

        Returns:
            SHA-256 hex digest of the normalised question.
        """
        normalised = question.strip().lower()
        return hashlib.sha256(normalised.encode()).hexdigest()

    # --------------------------------------------------------------------------
    # Public interface
    # --------------------------------------------------------------------------

    def get(self, question: str) -> Optional[Dict[str, Any]]:
        """Return a cached response if it exists and has not expired.

        Increments the internal hit or miss counter for observability.

        Args:
            question: Question string to look up.

        Returns:
            Cached response dict, or ``None`` if absent or expired.
        """
        key = self._make_key(question)
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        # Evict stale entries transparently instead of serving stale data
        if time.time() - entry["timestamp"] > self._ttl:
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        return entry["response"]

    def set(self, question: str, response: Dict[str, Any]) -> None:
        """Store a response in the cache, evicting the oldest entry if full.

        Args:
            question: Question string used as the cache key source.
            response: Response dict to cache.
        """
        # Evict the oldest entry (minimum timestamp) when at capacity
        if len(self._cache) >= self._max_size:
            oldest_key = min(
                self._cache, key=lambda k: self._cache[k]["timestamp"]
            )
            del self._cache[oldest_key]
            logger.debug("Cache eviction triggered - oldest entry removed")

        key = self._make_key(question)
        self._cache[key] = {"response": response, "timestamp": time.time()}

    def clear(self) -> int:
        """Remove all entries from the cache.

        Returns:
            Number of entries that were removed.
        """
        count = len(self._cache)
        self._cache.clear()
        logger.info("Cache cleared - %d entries removed", count)
        return count

    @property
    def size(self) -> int:
        """Return the current number of cached entries."""
        return len(self._cache)

    def info(self) -> Dict[str, Any]:
        """Return cache statistics for observability (e.g. /health endpoint).

        Returns:
            Dictionary with size, max_size, ttl_seconds, hits, and misses.
        """
        return {
            "size": self.size,
            "max_size": self._max_size,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
        }


class RateLimiter:
    """Per-IP rate limiter using a sliding-window algorithm.

    Tracks request timestamps per IP address and rejects requests
    that exceed the configured threshold within the time window.
    Exposes statistics for monitoring.

    Attributes:
        _requests: Mapping of client IP -> list of request timestamps.
        _max: Maximum allowed requests per window.
        _window: Window size in seconds.
        _total_allowed: Cumulative count of requests that were allowed.
        _total_rejected: Cumulative count of requests that were rejected.

    Example:
        >>> limiter = RateLimiter(max_requests=10, window_seconds=60)
        >>> limiter.is_allowed("192.168.1.1")
        True
        >>> limiter.remaining("192.168.1.1")
        9
    """

    def __init__(
        self,
        max_requests: int = RATE_LIMIT_MAX_REQUESTS,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ) -> None:
        """Initialise the rate limiter.

        Args:
            max_requests: Maximum requests allowed per window per IP.
            window_seconds: Duration of the sliding window in seconds.
        """
        # defaultdict avoids KeyError on first access for a new IP
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._max = max_requests
        self._window = window_seconds
        self._total_allowed: int = 0
        self._total_rejected: int = 0

    def is_allowed(self, client_ip: str) -> bool:
        """Check whether a client IP is within its rate limit.

        Records the current request timestamp if allowed.

        Args:
            client_ip: IPv4 or IPv6 address string of the client.

        Returns:
            ``True`` if the request is allowed, ``False`` if the limit
            is exceeded.
        """
        now = time.time()
        # Drop timestamps outside the sliding window before counting
        self._requests[client_ip] = [
            ts for ts in self._requests[client_ip] if now - ts < self._window
        ]
        if len(self._requests[client_ip]) >= self._max:
            self._total_rejected += 1
            return False

        self._requests[client_ip].append(now)
        self._total_allowed += 1
        return True

    def remaining(self, client_ip: str) -> int:
        """Return the number of requests the client can still make this window.

        Args:
            client_ip: IPv4 or IPv6 address string of the client.

        Returns:
            Non-negative integer count of remaining allowed requests.
        """
        now = time.time()
        recent = [
            ts for ts in self._requests[client_ip] if now - ts < self._window
        ]
        return max(0, self._max - len(recent))

    def reset(self, client_ip: Optional[str] = None) -> None:
        """Reset rate-limit tracking.

        Args:
            client_ip: If provided, only clear the history for this IP.
                If ``None``, clear all tracked IPs.
        """
        if client_ip:
            self._requests.pop(client_ip, None)
            logger.debug("Rate-limit history reset for IP %s", client_ip)
        else:
            self._requests.clear()
            logger.debug("Rate-limit history reset for all IPs")

    def info(self) -> Dict[str, Any]:
        """Return rate-limiter statistics for observability.

        Returns:
            Dictionary with configuration and cumulative counters.
        """
        return {
            "max_requests_per_window": self._max,
            "window_seconds": self._window,
            "tracked_ips": len(self._requests),
            "total_allowed": self._total_allowed,
            "total_rejected": self._total_rejected,
        }


# ================================================================
# MAIN EXECUTION
# ================================================================

if __name__ == "__main__":
    pass