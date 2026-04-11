"""
Module: main.py
Description: FastAPI application for NL2SQL Clinic Chatbot.

Provides REST API endpoints for natural language to SQL conversion.
Uses a Vanna 2.0 Agent for SQL generation and SQLite for execution.

Endpoints:
    - POST /chat - Ask a question in natural language, receive SQL + results
    - GET /health - Health check: database connectivity and memory item count
    
Usage:
    uvicorn main:app --port 8000
    
    
    
"""

# =================================================================
# Imports
# ==================================================================

import logging
import re
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from vanna.core.user import RequestContext
from vanna.components import RichTextComponent, StatusCardComponent

from config import (
    CACHE_ENABLED,
    DATABASE_PATH,
    GEMINI_MODEL,
    LLM_PROVIDER,
    LOG_LEVEL,
    MAX_RESULT_ROWS,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_MAX_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    SERVER_HOST,
    SERVER_PORT,
)

from utils import QueryCache, RateLimiter, generate_chart, setup_logging

from validators import (
    DatabaseExecutionError,
    InputValidationError,
    LLMServiceError,
    NL2SQLError,
    SQLValidationError,
    validate_question,
    validate_sql,
)

from vanna_setup import create_agent, get_agent_memory

# =================================================================
# CONSTANTS
# =================================================================

logger = logging.getLogger(__name__)

# Module-level singletons - created once at startup, reused across requests
_query_cache: QueryCache = QueryCache()
_rate_limiter: RateLimiter = RateLimiter(
    max_requests=RATE_LIMIT_MAX_REQUESTS,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)

# =================================================================
# PYDANTIC MODELS
# =================================================================

class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""

    question: str = Field(
        ...,
        description="Natural-language question about clinic data.",
        min_length=1,
        max_length=500,
    )

class ChatResponse(BaseModel):
    """Structured response returned by the /chat endpoint."""

    error: bool
    message: str
    sql_query: Optional[str]
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    chart: Optional[Dict[str, Any]]
    chart_type: Optional[str]




class HealthResponse(BaseModel):
    """Response returned by the /health endpoint."""

    status: str
    database: str
    agent_memory_items: int
    llm_provider: str
    model: str
    cache: Optional[Dict[str, Any]] = None
    rate_limiter: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standardised error response returned when any processing stage fails.

    All fields mirror ChatResponse so clients can handle success and error
    responses with the same shape - only the ``error`` flag differs.

    Attributes:
        error: Always True for error responses.
        message: Human-readable description of what went wrong.
        error_type: Category label - one of "validation", "sql_validation",
            "generation", "execution", or "unknown".
        sql_query: The SQL that caused the error, if available.
        columns: Always empty list on error.
        rows: Always empty list on error.
        row_count: Always 0 on error.
        chart: Always None on error.
        chart_type: Always None on error.
    """

    error: bool = True
    message: str
    error_type: str = "unknown"
    sql_query: Optional[str] = None
    columns: List[Any] = []
    rows: List[Any] = []
    row_count: int = 0
    chart: Optional[Dict[str, Any]] = None
    chart_type: Optional[str] = None


# ================================
# APPLICATION SETUP
# ================================

app = FastAPI(
    title="NL2SQL Clinic Chatbot",
    description="Natural language to SQL chatbot for clinic management data.",
    version="1.0.0",
)

# Allow browser-based clients on any origin (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================
# FUNCTIONS
# ================================

def create_error_response(
    message: str,
    error_type: str = "unknown",
    sql_query: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a standardised error response dictionary.

    Args:
        message: Human-readable error message for the client.
        error_type: Category of error (validation, generation, execution).
        sql_query: The SQL that caused the error, if applicable.

    Returns:
        Standardised response dictionary with all required keys.
    """
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


def _extract_sql_from_text(text: str) -> Optional[str]:
    """Extract the first SELECT statement from agent response text.

    Tries to find SQL in fenced code blocks first, then falls back to
    detecting a bare SELECT statement.

    Args:
        text: Raw text content returned by the agent.

    Returns:
        Extracted SQL string, or None if no SELECT statement is found.
    """
    # Pattern 1: SQL inside a fenced markdown code block (```sql ... ``` or ``` ... ```)
    code_block = re.search(
        r"```(?:sql)?\s*(SELECT[\s\S]+?)\s*```",
        text,
        re.IGNORECASE,
    )
    if code_block:
        return code_block.group(1).strip()

    # Pattern 2: Bare SELECT statement spanning one or more lines until a blank line or end
    bare_select = re.search(
        r"(SELECT[\s\S]+?)(?:\n\s*\n|$)",
        text,
        re.IGNORECASE,
    )
    if bare_select:
        return bare_select.group(1).strip()

    return None


async def process_question(question: str, client_ip: str) -> Dict[str, Any]:
    """Orchestrate the full question-to-answer pipeline.

    Steps:
        1. Validate question input.
        2. Check query cache for a previous identical question.
        3. Send question to Vanna 2.0 Agent to generate SQL.
        4. Validate the generated SQL for safety.
        5. Execute SQL against the clinic database.
        6. Optionally generate a Plotly chart.
        7. Cache and return the structured response.

    Args:
        question: Natural-language question from the user.
        client_ip: Client IP address used for logging purposes.

    Returns:
        Standardised response dictionary (see ChatResponse).

    Raises:
        InputValidationError: When the question fails length or content checks.
        LLMServiceError: When the agent fails to generate SQL or times out.
        SQLValidationError: When the generated SQL fails security validation.
        DatabaseExecutionError: When SQL execution against the database fails.
    """
    start_time = time.time()

    # --- Step 1: Input validation ---
    is_valid, reason = validate_question(question)
    if not is_valid:
        logger.warning("Input validation failed from %s: %s", client_ip, reason)
        raise InputValidationError(reason)

    logger.info("Processing question from %s: '%s'", client_ip, question[:80])

    # --- Step 2: Cache lookup ---
    if CACHE_ENABLED:
        cached = _query_cache.get(question)
        if cached is not None:
            logger.info("Cache hit for question: '%s'", question[:60])
            return cached

    # --- Step 3: Send to Vanna 2.0 Agent ---
    response_text_parts: List[str] = []
    sql_query: Optional[str] = None

    try:
        # create_agent() is placed inside the try block so initialisation
        # failures (e.g. bad API key) are also caught and re-raised uniformly.
        agent = create_agent()
        request_context = RequestContext(remote_addr=client_ip)

        async for component in agent.send_message(
            request_context=request_context,
            message=question,
            conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        ):
            rc = getattr(component, "rich_component", None)
            sc = getattr(component, "simple_component", None)
            
            # --- Extract SQL from StatusCardComponent.metadata ---
            # Vanna yields a StatusCardComponent with title="Executing run_sql..."
            # and metadata={"sql": "<query>"} before executing the RunSqlTool.
            # We capture on status="running" (first emit) so we get the SQL
            # before execution and re-validate it overselves below.
            if (
                sql_query is None
                and isinstance(rc, StatusCardComponent)
                and "run_sql" in (rc.title or "").lower()
                and getattr(rc, "status", None) == "running"
            ):
                metadata = getattr(rc, "metadata", None) or {}
                candidate = metadata.get("sql") if isinstance(metadata, dict) else None
                if candidate and isinstance(candidate, str):
                    sql_query = candidate
                    logger.debug("SQL captured from StatusCardComponent.metadata: %s", sql_query[:120])
                    
            # --- Accumulate final natural-language answer text ---
            # RichTextComponent carries the LLM's prose answer (last turn).
            if isinstance(rc, RichTextComponent):
                text = getattr(rc, "content", None)
                if text:
                    response_text_parts.append(text)
                    
            # SimpleTextComponent (simple_componenet.text) carries a plain-text
            # summary - append is too so the fallback regex has content to scan.
            if sc is not None:
                plain = getattr(sc, "text", None)
                if plain:
                    response_text_parts.append(plain)

    except TimeoutError as exc:
        # Handle LLM request timeout specifically so the user gets a clear message
        logger.warning("LLM timeout for question: '%s'", question[:50])
        raise LLMServiceError(
            "The AI took too long to respond. Please try again."
        ) from exc
    except ConnectionError as exc:
        # Surface network failures separately from general LLM errors
        logger.error("Lost connection to LLM service: %s", exc)
        raise LLMServiceError(
            "Connection error. Please check your API key and network connectivity."
        ) from exc
    except LLMServiceError:
        # Re-raise LLMServiceError from create_agent() without double-wrapping
        raise
    except Exception as exc:
        logger.error(
            "Agent error for question '%s': %s", question[:60], exc, exc_info=True
        )
        raise LLMServiceError(f"AI service error: {exc}") from exc

    response_text = " ".join(response_text_parts).strip()

    # Fallback: try to extract SQL via regex from the text response
    if not sql_query:
        sql_query = _extract_sql_from_text(response_text)

    if not sql_query:
        logger.warning("No SQL generated for question: '%s'", question[:60])
        raise LLMServiceError(
            "Could not generate a SQL query for your question. "
            "Please try rephrasing or be more specific."
        )

    logger.info("Generated SQL (%d chars): %s", len(sql_query), sql_query[:200])

    # --- Step 4: SQL safety validation ---
    is_valid, reason = validate_sql(sql_query)
    if not is_valid:
        logger.warning("SQL validation failed: %s | SQL: %s", reason, sql_query[:100])
        raise SQLValidationError(
            f"The generated SQL was rejected for safety: {reason}"
        )

    # --- Step 5: Execute SQL against the clinic database ---
    columns: List[str] = []
    rows: List[List[Any]] = []
    row_count: int = 0

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.execute(sql_query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [list(row) for row in cursor.fetchall()]
        row_count = len(rows)
        conn.close()
    except sqlite3.OperationalError as exc:
        logger.error("SQLite operational error: %s | SQL: %s", exc, sql_query[:200])
        raise DatabaseExecutionError(f"Database query error: {exc}") from exc
    except sqlite3.Error as exc:
        logger.error("SQLite error: %s | SQL: %s", exc, sql_query[:200])
        raise DatabaseExecutionError("An unexpected database error occurred.") from exc

    logger.info("Query executed: %d rows returned | SQL: %s", row_count, sql_query[:80])

    # --- Step 5b: Truncate large result sets to avoid huge payloads ---
    truncated = False
    if row_count > MAX_RESULT_ROWS:
        logger.warning(
            "Result truncated from %d to %d rows", row_count, MAX_RESULT_ROWS
        )
        rows = rows[:MAX_RESULT_ROWS]
        truncated = True

    # --- Step 6: Optional chart generation ---
    chart: Optional[Dict[str, Any]] = None
    chart_type: Optional[str] = None

    if rows and columns:
        try:
            df = pd.DataFrame(rows, columns=columns)
            chart_data = generate_chart(df, question)
            if chart_data:
                chart = chart_data.get("chart")
                chart_type = chart_data.get("chart_type")
        except Exception as exc:
            # Chart failure is non-fatal; proceed without one
            logger.warning("Chart generation skipped: %s", exc)

    # Build a clean summary message when the agent response text is absent
    if not response_text:
        response_text = (
            f"Query returned {row_count} row{'s' if row_count != 1 else ''}."
        )

    # Append truncation notice so the client knows results were trimmed
    if truncated:
        response_text += (
            f" (Showing first {MAX_RESULT_ROWS} of {row_count} rows.)"
        )

    elapsed_ms = (time.time() - start_time) * 1000
    logger.info(
        "Question answered in %.0fms | %d rows | SQL: %s",
        elapsed_ms,
        row_count,
        sql_query[:80],
    )

    result: Dict[str, Any] = {
        "error": False,
        "message": response_text,
        "sql_query": sql_query,
        "columns": columns,
        "rows": rows,
        "row_count": row_count,
        "chart": chart,
        "chart_type": chart_type,
    }
    
    # --- Step 7: Cache successful result ---
    if CACHE_ENABLED:
        _query_cache.set(question, result)

    return result

# =============================================================================
# ROUTES
# =============================================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> Dict[str, Any]:
    """Ask a natural language question about the clinic database.

    Args:
        request: FastAPI Request object (used to read client IP).
        body: Validated request body containing the question.

    Returns:
        Structured JSON response with SQL, results, and optional chart.
    """
    # Resolve client IP for rate limiting and logging
    client_ip: str = request.client.host if request.client else "unknown"

    # Enforce rate limit before any expensive processing
    if RATE_LIMIT_ENABLED and not _rate_limiter.is_allowed(client_ip):
        remaining_seconds = RATE_LIMIT_WINDOW_SECONDS
        logger.warning("Rate limit exceeded for IP: %s", client_ip)
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded. "
                f"You may make {_rate_limiter._max} requests per "
                f"{remaining_seconds}s window. "
                f"Please wait and try again."
            ),
        )

    # Log remaining quota so operators can spot near-limit clients
    if RATE_LIMIT_ENABLED:
        logger.debug(
            "Rate limit check passed for %s — %d requests remaining",
            client_ip,
            _rate_limiter.remaining(client_ip),
        )

    # --- Error handling hierarchy (specific -> general) -------------------
    # Each exception type is caught in order of specificity so that the most
    # precise HTTP status code and error category are always returned.
    try:
        response = await process_question(body.question, client_ip)
        return response
    except InputValidationError as exc:
        # Bad user input — client error (400)
        logger.warning("Input validation error from %s: %s", client_ip, exc)
        return JSONResponse(
            status_code=400,
            content=create_error_response(str(exc), "validation"),
        )
    except SQLValidationError as exc:
        # Generated SQL failed safety checks — client / prompt error (400)
        logger.warning("SQL validation error from %s: %s", client_ip, exc)
        return JSONResponse(
            status_code=400,
            content=create_error_response(str(exc), "sql_validation"),
        )
    except DatabaseExecutionError as exc:
        # SQL was valid but the database rejected or failed to execute it (500)
        logger.error("Database execution error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=create_error_response(str(exc), "execution"),
        )
    except LLMServiceError as exc:
        # LLM timed out, lost connection, or returned no usable SQL (500)
        logger.error("LLM service error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=create_error_response(str(exc), "generation"),
        )
    except NL2SQLError as exc:
        # Any other application-specific error not matched above (500)
        logger.error("NL2SQL error: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content=create_error_response(str(exc), "unknown"),
        )
    except Exception as exc:
        # Catch-all for truly unexpected errors — avoid leaking internals
        logger.error(
            "Unexpected error processing question: %s", exc, exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                "An unexpected error occurred. Please try again.", "unknown"
            ),
        )


@app.get("/health", response_model=HealthResponse)
async def health() -> Dict[str, Any]:
    """Return service health status, database connectivity, and memory stats.

    Returns:
        Health status dictionary.
    """
    # --- Database connectivity check ---
    db_status = "connected"
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.execute("SELECT 1")
        conn.close()
    except Exception as exc:
        logger.warning("Health check: database unreachable - %s", exc)
        db_status = "disconnected"

    # --- Agent memory item count ---
    memory_count = 0
    try:
        memory = get_agent_memory()
        # DemoAgentMemory stores memories in internal dicts; probe common names
        for attr in ("_tool_usages", "_text_memories", "_memories"):
            if hasattr(memory, attr):
                memory_count += len(getattr(memory, attr))
    except Exception:
        pass  # Non-critical; fall back to 0

    return {
        "status": "ok",
        "database": db_status,
        "agent_memory_items": memory_count,
        "llm_provider": LLM_PROVIDER,
        "model": GEMINI_MODEL,
        "cache": _query_cache.info(),
        "rate_limiter": _rate_limiter.info(),
    }


# ======================================================================
# MAIN EXECUTION
# ======================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=SERVER_HOST, port=SERVER_PORT, reload=False)