"""
Module: vanna_setup.py
Description: Initializes the Vanna 2.0 Agent with all required components.

Sets up the LLM service, tool registry, agent memory, and user resolver.
Exports a configured Vanna agent instance ready for use by the FastAPI application.

Components:
    - LLM Service: GeminiLlmService (Google Gemini)
    - SQL Runner: SqliteRunner (built-in SQLite support)
    - Tools: RunSqlTool, VisualizeDateTool, SaveQuestionToolArgsTool,
             SearchSavedCorrectToolUserTool, SaveTextMemoryTool
    - Memory: DemoAgentMemory (in-memory singleton, populated by seed_memory.py)
    - User Resolver: SimpleUserResolver (default admin user for all requests)
"""




# =================================================================
# Imports
# ==================================================================

import logging
import os 
from typing import Optional
from dotenv import load_dotenv

# Vanna 2.0 imports
from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.tools import RunSqlTool, VisualizeDateTool
from vanna.tools.agent_memory import (
    SaveQuestionToolArgsTool,
    SearchSavedCorrectToolUsesTool,
    SaveTextMemoryTool,
)
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.local import LocalFileSystem
from vanna.integrations.google import GeminiLlmService

from config import (
    DATABASE_PATH,
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    AGENT_MEMORY_MAX_ITEMS,
    AGENT_TEMPERATURE,
)
from validators import LLMServiceError 

# =================================================================
# CONSTANTS
# =================================================================

logger = logging.getLogger(__name__)

# Directory used by VisualizeDataTool to write generated chart files
CHART_STORAGE_DIR : str = "./data_storage"

# Access group labels - must align with User.group_membership below
_GROUP_ADMIN: str = "admin"
_GROUP_USER: str = "user"

# =================================================================
# MODULE-LEVEL SINGLETONS
# =================================================================

# Both are created lazily on first call; shared across seed_memory.py and main.py
_agent_memory: Optional[DemoAgentMemory] = None
_agent: Optional[Agent] = None

# =================================================================
# CLASSES
# =================================================================


class SimpleUserResolver(UserResolver):
    """Resolves all incoming requests to a single default admin user.

    In a production system this would authenticate the caller and look up
    their real identity and group memberships. For this demo every request
    is mapped to the same anonymous admin so that all registered tools are
    accessible without additional auth configuration.
    """

    async def get_user(self, request_context: RequestContext) -> User:
        """Return a default admin user for every incoming request.

        Args:
            request_context: The incoming request context (unused here).

        Returns:
            User with both 'admin' and 'user' group memberships, granting
            access to every tool registered in the ToolRegistry.
        """
        return User(
            id="default-user",
            name="Clinic User",
            email="user@clinic.local",
            # group_memberships controls which tools this user can invoke;
            # must match the access_groups passed to register_local_tool()
            group_memberships=[_GROUP_ADMIN, _GROUP_USER],
        )


# =============================================================================
# FUNCTIONS
# =============================================================================

def _build_llm_service() -> GeminiLlmService:
    """Instantiate the Google Gemini LLM service from config.

    Returns:
        Configured GeminiLlmService ready for the Agent.

    Raises:
        ValueError: If GOOGLE_API_KEY is not set in the environment.
    """
    if not GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY is not set. "
            "Add it to your .env file: GOOGLE_API_KEY=your-key-here"
        )

    logger.info("Initializing GeminiLlmService (model=%s)", GEMINI_MODEL)
    return GeminiLlmService(
        model=GEMINI_MODEL,
        api_key=GOOGLE_API_KEY,
        temperature=AGENT_TEMPERATURE,
    )


def _build_tool_registry() -> ToolRegistry:
    """Build the ToolRegistry and register all five required tools.

    Tools registered:
        1. RunSqlTool                    - executes SELECT queries on clinic.db
        2. VisualizeDataTool             - generates Plotly charts from results
        3. SaveQuestionToolArgsTool       - persists successful Q+SQL patterns
        4. SearchSavedCorrectToolUsesTool - retrieves past successful patterns
        5. SaveTextMemoryTool            - saves schema/business-rule text memories

    Returns:
        Populated ToolRegistry instance.
    """

    # Ensure the chart output directory exists before the tool tries to write
    os.makedirs(CHART_STORAGE_DIR, exist_ok=True)

    tools = ToolRegistry()

    # 1. SQL execution - both admin and regular users may run queries
    tools.register_local_tool(
        RunSqlTool(sql_runner=SqliteRunner(database_path=DATABASE_PATH)),
        access_groups=[_GROUP_ADMIN, _GROUP_USER],
    )
    logger.debug("Registered RunSqlTool (database_path=%s)", DATABASE_PATH)

    # 2. Visualization - generate charts for aggregated query results
    tools.register_local_tool(
        VisualizeDataTool(
            file_system=LocalFileSystem(working_directory=CHART_STORAGE_DIR)
        ),
        access_groups=[_GROUP_ADMIN, _GROUP_USER],
    )
    logger.debug("Registered VisualizeDataTool (chart_dir=%s)", CHART_STORAGE_DIR)

    # 3. Save learned Q+SQL pattern - admin-only to prevent memory pollution
    tools.register_local_tool(
        SaveQuestionToolArgsTool(),
        access_groups=[_GROUP_ADMIN],
    )
    logger.debug("Registered SaveQuestionToolArgsTool (admin-only)")

    # 4. Search past patterns - all users benefit from prior learnings
    tools.register_local_tool(
        SearchSavedCorrectToolUsesTool(),
        access_groups=[_GROUP_ADMIN, _GROUP_USER],
    )
    logger.debug("Registered SearchSavedCorrectToolUsesTool")

    # 5. Text memory - stores schema descriptions and business rules
    tools.register_local_tool(
        SaveTextMemoryTool(),
        access_groups=[_GROUP_ADMIN, _GROUP_USER],
    )
    logger.debug("Registered SaveTextMemoryTool")

    logger.info("ToolRegistry ready - 5 tools registered")
    return tools


def get_agent_memory() -> DemoAgentMemory:
    """Return the shared DemoAgentMemory singleton.

    Creates the instance on first call; subsequent calls return the same
    object so that seed_memory.py and main.py operate on the exact same
    in-memory store.

    Note:
        DemoAgentMemory is volatile - all memories are lost on process
        restart. Run seed_memory.py before every server start.

    Returns:
        Shared DemoAgentMemory instance.
    """

    global _agent_memory

    if _agent_memory is None:
        _agent_memory = DemoAgentMemory(max_items=AGENT_MEMORY_MAX_ITEMS)
        logger.info(
            "DemoAgentMemory created (max_items=%d)", AGENT_MEMORY_MAX_ITEMS
        )

    return _agent_memory


def create_agent() -> Agent:
    """Create and return the fully configured Vanna 2.0 Agent singleton.

    Wires together the LLM service, tool registry, agent memory, and user
    resolver into a single Agent ready for send_message() calls. Returns
    the cached instance on subsequent calls to avoid redundant initialisation.

    Returns:
        Configured Agent instance.

    Raises:
        ValueError: If GOOGLE_API_KEY is not configured in the environment.
    """
    global _agent

    # Return cached instance - prevents double-init when imported by multiple modules
    if _agent is not None:
        logger.debug("Returning cached Agent instance")
        return _agent

    # Reload .env in case this is called before the FastAPI startup event
    load_dotenv()

    llm = _build_llm_service()
    tools = _build_tool_registry()
    memory = get_agent_memory()
    user_resolver = SimpleUserResolver()

    # AgentConfig controls how many tool-call iterations the LLM may perform
    # before giving a final answer; 10 is sufficient for multi-step SQL queries
    config = AgentConfig(max_tool_iterations=10)

    try:
        _agent = Agent(
            llm_service=llm,
            tool_registry=tools,
            agent_memory=memory,
            user_resolver=user_resolver,
            config=config,
        )
    except ValueError:
        # Re-raise configuration errors (e.g. bad API key format) as-is
        # so callers receive a descriptive message without extra wrapping.
        raise
    except Exception as exc:
        logger.error("Failed to instantiate Vanna Agent: %s", exc, exc_info=True)
        raise LLMServiceError(
            f"Failed to initialize AI service: {exc}"
        ) from exc

    logger.info("Vanna 2.0 Agent created successfully")
    return _agent


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    # Quick smoke-test: create the agent and confirm no import/config errors
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    )

    logger.info("Running vanna_setup.py smoke-test...")
    try:
        agent = create_agent()
        memory = get_agent_memory()
        logger.info("✅ Agent created  — type: %s", type(agent).__name__)
        logger.info("✅ Memory ready   — type: %s", type(memory).__name__)
        logger.info("✅ Phase 3 validation passed")
    except ValueError as exc:
        logger.error("❌ Configuration error: %s", exc)
    except Exception as exc:
        logger.error("❌ Unexpected error: %s", exc, exc_info=True)
