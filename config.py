"""
Module: config.py
Description: Central configuration for the NL2SQL Clinic chatbot.

All configurable values are defined here as named constants.
Environment variables override defaults where applicable.
Import from this module to avoide magic number scattered across the codebase.

"""
# ==================================================================
# Imports
# ==================================================================
import os 
from dotenv import load_dotenv

load_dotenv()

# ==================================================================
# DATABASE CONFIGURATION
# ==================================================================
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./clinic.db")
DATABASE_NAME: str = "clinic.db"

# ==================================================================
# LLM CONFIGURATION
# ==================================================================

# Supported providers: "gemini" | "groq" | "ollama"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")

# Google Gemini settings (Option A – default)
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Groq settings (Option B)
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Ollama settings (Option C – local, no API key required)
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

# ==================================================================
# AGENT CONFIGURATION
# ==================================================================

AGENT_MEMORY_MAX_ITEMS: int = 1000
AGENT_STREAM_RESPONSES: bool = True
AGENT_TEMPERATURE: float = 0.7

# ==================================================================
# INPUT VALIDATION
# ==================================================================

MAX_QUESTION_LENGTH: int = 500
MIN_QUESTION_LENGTH: int = 3

# ==================================================================
# SQL VALIDATION
# ==================================================================

# Maximum length of a generated SQL query accepted for execution
MAX_SQL_LENGTH: int = 5000

# Keywords that indicate dangerous SQL operations
BLOCKED_SQL_KEYWORDS: list = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "CREATE", "TRUNCATE", "EXEC", "EXECUTE",
    "xp_", "sp_", "GRANT", "REVOKE", "SHUTDOWN",
    "UNION", "INTO OUTFILE", "LOAD_FILE",
]

# System tables that should never be queried directly by the user
BLOCKED_SYSTEM_TABLES: list = [
    "sqlite_master", "sqlite_sequence", "sqlite_temp_master",
    "information_schema", "sys.", "sysobjects",
]

# ==================================================================
# RATE LIMITING
# ==================================================================

RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_MAX_REQUESTS: int = 10
RATE_LIMIT_WINDOW_SECONDS: int = 60

# ==================================================================
# CACHING
# ==================================================================

CACHE_ENABLED: bool = True
CACHE_MAX_SIZE: int = 100
CACHE_TTL_SECONDS: int = 300  # 5 minutes

# ==================================================================
# RESULT LIMITS
# ==================================================================

# Maximum number of rows returned to the client (prevents huge payloads)
MAX_RESULT_ROWS: int = 500

# ==================================================================
# LOGGING
# ==================================================================

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"

# ==================================================================
# SERVER
# ==================================================================

SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))

# ==================================================================
# DATA GENERATION (used by setup_database.py)
# ==================================================================

NUM_PATIENTS: int = 200
NUM_DOCTORS: int = 15
NUM_APPOINTMENTS: int = 500
NUM_TREATMENTS: int = 350
NUM_INVOICES: int = 300

SPECIALIZATIONS: list = [
    "Dermatology",
    "Cardiology",
    "Orthopedics",
    "General",
    "Pediatrics",
]

CITIES: list = [
    "Mumbai",
    "Delhi",
    "Bangalore",
    "Chennai",
    "Hyderabad",
    "Pune",
    "Kolkata",
    "Ahmedabad",
    "Jaipur",
    "Lucknow",
]

APPOINTMENT_STATUSES: list = ["Scheduled", "Completed", "Cancelled", "No-Show"]
# Most appointments should be completed; roughly match real-world clinic data
APPOINTMENT_STATUS_WEIGHTS: list = [0.15, 0.50, 0.20, 0.15]

INVOICE_STATUSES: list = ["Paid", "Pending", "Overdue"]
# More invoices should be paid than outstanding
INVOICE_STATUS_WEIGHTS: list = [0.55, 0.30, 0.15]

# ==================================================================
# CHART DETECTION KEYWORDS
# ==================================================================

# Column-name fragments that indicate a temporal axis -> line chart
CHART_DATE_INDICATORS: list = [
    "month", "date", "year", "week", "day", "time", "period", "quarter",
]

# Question keywords that imply a trend -> line chart
CHART_TREND_KEYWORDS: list = [
    "trend", "over time", "monthly", "weekly", "by month",
    "by year", "by week", "growth", "timeline",
]

# Question keywords that imply a distribution / proportion -> pie chart
CHART_PIE_KEYWORDS: list = [
    "distribution", "breakdown", "proportion", "percentage",
    "share", "ratio", "split", "composition", "pie",
]

# Maximum number of categories before switching from pie to bar chart
# (too many slices make pie charts unreadable)
CHART_PIE_MAX_CATEGORIES: int = 8