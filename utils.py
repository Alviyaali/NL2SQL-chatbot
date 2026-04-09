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

