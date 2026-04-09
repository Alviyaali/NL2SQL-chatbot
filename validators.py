"""
Module: validators.py
Description: SQL and input validation for the NL2SQL Clinic Chatbot.

Provides security validation for generated SQL queries and input validation
for user questions. All SQL queries must pass these checks before execution
against the database.

Security Rules: 
    - Only SELECT queries are allowed
    - Dangerous keywords (DROP, DELETE, INSERT, etc.) are blocked
    - System table access is blocked (sqlite_master, etc.)
    - Multiple-statement execution (semicolon injection) is blocked
    - Comment-based injection patterns are rejected
    
    
    
"""

# ==============================================================
# IMPORTS
# ==============================================================

import logging
import re
from typing import Any, Dict, Optional, Tuple

from config import (
    BLOCKED_SQL_KEYWORDS,
    BLOCKED_SYSTEM_TABLES,
    MAX_QUESTION_LENGTH,
    MAX_SQL_LENGTH,
    MIN_QUESTION_LENGTH,
)



# ==============================================================
# CONSTANTS
# ==============================================================

logger = logging.getLogger(__name__)

# ==============================================================
# EXCEPTIONS
# ==============================================================


class NL2SQLError(Exception):
    """Base exception for all NL2SQL application errors."""


class InputValidationError(NL2SQLError):
    """Raised when user input fails validation checks."""


class SQLValidationError(NL2SQLError):
    """Raised when a generated SQL query fails security validation."""


class DatabaseExecutionError(NL2SQLError):
    """Raised when SQL execution against the database fails."""


class LLMServiceError(NL2SQLError):
    """Raised when the LLM service fails to respond or times out."""


# =============================================================================
# FUNCTIONS
# =============================================================================


def create_error_response(
    message: str,
    error_type: str = "unknown",
    sql_query: Optional[str] = None,
    status_code: int = 500,
) -> Dict[str, Any]:
    """Create a standardized error response dictionary.

    Produces a consistently shaped dict that the FastAPI layer can return
    directly, regardless of which validation or execution stage failed.

    Args:
        message: Human-readable description of the error.
        error_type: Category label — one of "validation", "generation",
            "execution", "no_results", or "unknown".
        sql_query: The SQL string that caused the error, if applicable.
        status_code: Intended HTTP status code (informational only; callers
            must still pass this to JSONResponse).

    Returns:
        A dict with a fixed set of keys so callers never need to build the
        shape themselves:

        {
            "error": True,
            "message": str,
            "error_type": str,
            "sql_query": Optional[str],
            "columns": [],
            "rows": [],
            "row_count": 0,
            "chart": None,
            "chart_type": None,
        }

    Examples:
        >>> create_error_response("Too long", "validation")
        {'error': True, 'message': 'Too long', 'error_type': 'validation', ...}
    """
    logger.debug(
        "Creating error response | type=%s status=%d msg=%s",
        error_type,
        status_code,
        message[:120],
    )
    return {
        "error": True,
        "message": message,
        "error_type": error_type,
        "sql_query": sql_query,
        "columns": [],
        "rows": [],
        "row_count": 0,
        "chart": None,
        "chart_type": None,
    }


def validate_question(question: str) -> Tuple[bool, str]:
    """Validate a user question for length, content, and basic safety.

    Args:
        question: Raw question string submitted by the user.

    Returns:
        A tuple of (is_valid, error_message).
        - (True, "") if all checks pass.
        - (False, "reason") if any check fails.
    """
    # Reject empty or whitespace-only input before any other checks
    if not question or not question.strip():
        return False, "Question cannot be empty"

    question_stripped = question.strip()

    if len(question_stripped) < MIN_QUESTION_LENGTH:
        return (
            False,
            f"Question too short (minimum {MIN_QUESTION_LENGTH} characters)",
        )

    if len(question) > MAX_QUESTION_LENGTH:
        return (
            False,
            f"Question too long ({len(question)} characters, maximum {MAX_QUESTION_LENGTH})",
        )

    # Reject pure numeric or punctuation-only strings with no alphabetic content
    if not any(c.isalpha() for c in question):
        return False, "Question must contain at least one letter"

    logger.debug("Question validation passed: '%s'", question_stripped[:60])
    return True, ""


def validate_sql(sql: str) -> Tuple[bool, str]:
    """Validate a generated SQL query for safety before execution.

    Checks that the query is a SELECT statement and contains no dangerous
    keywords, system table references, or injection patterns.

    Args:
        sql: The SQL query string to validate.

    Returns:
        A tuple of (is_valid, error_message).
        - (True, "") if the query passes all checks.
        - (False, "reason") if the query fails any check.

    Raises:
        ValueError: If sql is None.

    Examples:
        >>> validate_sql("SELECT * FROM patients")
        (True, "")
        >>> validate_sql("DROP TABLE patients")
        (False, "Only SELECT queries are allowed")
    """
    if sql is None:
        raise ValueError("sql argument cannot be None")

    sql_stripped = sql.strip()
    if not sql_stripped:
        return False, "SQL query cannot be empty"

    # Reject suspiciously long queries before further processing
    if len(sql) > MAX_SQL_LENGTH:
        return False, f"SQL query is too long (maximum {MAX_SQL_LENGTH} characters)"

    # NULL bytes can be used to truncate strings in some database drivers
    if "\x00" in sql:
        return False, "SQL query contains illegal null bytes"

    # Strip block comments and line comments so they cannot be used to hide
    # malicious keywords (e.g. "/* DROP */ SELECT ...").
    sql_no_comments = re.sub(r"/\*.*?\*/", " ", sql_stripped, flags=re.DOTALL)
    sql_no_comments = re.sub(r"--[^\n]*", " ", sql_no_comments)
    sql_normalized = sql_no_comments.strip()

    # Rule 1: Query must start with SELECT (after comment removal)
    if not re.match(r"^\s*SELECT\b", sql_normalized, re.IGNORECASE):
        return False, "Only SELECT queries are allowed"

    # Rule 2: Semicolon injection — a single trailing semicolon is fine,
    # but any semicolon mid-query indicates stacked statements.
    sql_no_trailing = sql_normalized.rstrip().rstrip(";")
    if ";" in sql_no_trailing:
        return False, "Multiple SQL statements are not allowed (semicolon injection detected)"

    # Rule 3: Blocked dangerous keywords checked at word boundaries to avoid
    # false positives (e.g. 'SELECTED' should not match 'SELECT').
    for keyword in BLOCKED_SQL_KEYWORDS:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, sql_normalized, re.IGNORECASE):
            logger.warning("Blocked keyword '%s' in SQL: %s", keyword, sql[:80])
            return False, f"Blocked keyword detected: {keyword}"

    # Rule 4: System table access must be blocked even if expressed as a
    # quoted identifier or with different casing.
    sql_lower = sql_normalized.lower()
    for table in BLOCKED_SYSTEM_TABLES:
        if table.lower() in sql_lower:
            logger.warning("System table '%s' referenced in SQL: %s", table, sql[:80])
            return False, f"Access to system table '{table}' is not allowed"

    logger.debug("SQL validation passed: %s", sql[:80])
    return True, ""


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    pass
