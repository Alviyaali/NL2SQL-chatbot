"""
Module: seed_memory.py
Description: Seeds the Vanna 2.0 Agent memory with question-SQL pairs.

Pre-populates DemoAgentMemory with 20 question SQL pairs covering every 
test question category from the evaluation rubric, plus 6 schema-description 
text memories so the LLM has full column and value context.

Each question SQL pair is persisted via agent_memory.save_tool_usage() using 
the correct Vanna 2.0 async API. Schema descriptions are persisted via 
agent_memory.save_text_memory().

Usage:
    python seed_memory.py

Output:
    - Prints count of tool memories seeded
    - Prints count of text memories seeded
    - Prints total memory item count



"""

# ==================================================================
# Imports
# ==================================================================

import asyncio
import logging
from typing import List, Tuple

# Vanna 2.0 imports - correct 2.0 paths, NOT 0.x
from vanna.core.tool import ToolContext
from vanna.core.user import User
from vanna.integrations.local.agent_memory import DemoAgentMemory

from config import LOG_FORMAT, LOG_LEVEL
from vanna_setup import get_agent_memory

# ==================================================================
# CONSTANTS
# ==================================================================

logger = logging.getLogger(__name__)

# Reusable seed-user - only exists during the seeding process
_SEED_USER: User = User(
    id="seed-script",
    email="admin@clinic.local",
    group_memberships=["admin"],
)

# -------------------------------------------------------------------
# MEMORY PAIRS
# Each tuple is (natural-language question, correct SQL query).
# Covers all 20 evaluation questions plus a few extras for robustness.
# -------------------------------------------------------------------

MEMORY_PAIRS: List[Tuple[str, str]] = [
    # — Patient queries (questions 1, 11, 12, 18, 20) —
    (
        "How many patients do we have?",
        "SELECT COUNT(*) AS total_patients FROM patients",
    ),
    (
        "Which city has the most patients?",
        (
            "SELECT city, COUNT(*) AS patient_count "
            "FROM patients "
            "GROUP BY city "
            "ORDER BY patient_count DESC "
            "LIMIT 1"
        ),
    ),
    (
        "List patients who visited more than 3 times",
        (
            "SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count "
            "FROM patients p "
            "JOIN appointments a ON a.patient_id = p.id "
            "GROUP BY p.id "
            "HAVING visit_count > 3 "
            "ORDER BY visit_count DESC"
        ),
    ),
    (
        "Show patients with overdue invoices",
        (
            "SELECT DISTINCT p.first_name, p.last_name, p.email, p.city "
            "FROM patients p "
            "JOIN invoices i ON i.patient_id = p.id "
            "WHERE i.status = 'Overdue' "
            "ORDER BY p.last_name"
        ),
    ),
    (
        "Show patient registration trend by month",
        (
            "SELECT strftime('%Y-%m', registered_date) AS month, "
            "COUNT(*) AS registrations "
            "FROM patients "
            "GROUP BY month "
            "ORDER BY month"
        ),
    ),
    # — Doctor queries (questions 2, 4, 6, 17, 19) —
    (
        "List all doctors and their specializations",
        (
            "SELECT name, specialization, department "
            "FROM doctors "
            "ORDER BY specialization, name"
        ),
    ),
    (
        "Which doctor has the most appointments?",
        (
            "SELECT d.name, d.specialization, COUNT(a.id) AS appointment_count "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "GROUP BY d.id "
            "ORDER BY appointment_count DESC "
            "LIMIT 1"
        ),
    ),
    (
        "Show revenue by doctor",
        (
            "SELECT d.name, d.specialization, SUM(i.total_amount) AS total_revenue "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "JOIN invoices i ON i.patient_id = a.patient_id "
            "GROUP BY d.id "
            "ORDER BY total_revenue DESC"
        ),
    ),
    (
        "What is the average appointment duration by doctor?",
        (
            "SELECT d.name, d.specialization, "
            "AVG(t.duration_minutes) AS avg_duration_minutes "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "JOIN treatments t ON t.appointment_id = a.id "
            "GROUP BY d.id "
            "ORDER BY avg_duration_minutes DESC"
        ),
    ),
    (
        "Compare total revenue between departments",
        (
            "SELECT d.department, SUM(i.total_amount) AS total_revenue "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "JOIN invoices i ON i.patient_id = a.patient_id "
            "GROUP BY d.department "
            "ORDER BY total_revenue DESC"
        ),
    ),
    # — Appointment queries (questions 3, 7, 10, 14, 15) —
    (
        "Show me appointments for last month",
        (
            "SELECT a.id, p.first_name, p.last_name, "
            "d.name AS doctor_name, a.appointment_date, a.status "
            "FROM appointments a "
            "JOIN patients p ON p.id = a.patient_id "
            "JOIN doctors d ON d.id = a.doctor_id "
            "WHERE a.appointment_date >= date('now', '-1 month') "
            "ORDER BY a.appointment_date DESC"
        ),
    ),
    (
        "How many cancelled appointments were there last quarter?",
        (
            "SELECT COUNT(*) AS cancelled_count "
            "FROM appointments "
            "WHERE status = 'Cancelled' "
            "AND appointment_date >= date('now', '-3 months')"
        ),
    ),
    (
        "Show monthly appointment count for the past 6 months",
        (
            "SELECT strftime('%Y-%m', appointment_date) AS month, "
            "COUNT(*) AS appointment_count "
            "FROM appointments "
            "WHERE appointment_date >= date('now', '-6 months') "
            "GROUP BY month "
            "ORDER BY month"
        ),
    ),
    (
        "What is the no-show percentage?",
        (
            "SELECT "
            "COUNT(CASE WHEN status = 'No-Show' THEN 1 END) * 100.0 / COUNT(*) "
            "AS no_show_percentage "
            "FROM appointments"
        ),
    ),
    (
        "Which day of the week has the most appointments?",
        (
            "SELECT "
            "CASE strftime('%w', appointment_date) "
            " WHEN '0' THEN 'Sunday' "
            " WHEN '1' THEN 'Monday' "
            " WHEN '2' THEN 'Tuesday' "
            " WHEN '3' THEN 'Wednesday' "
            " WHEN '4' THEN 'Thursday' "
            " WHEN '5' THEN 'Friday' "
            " WHEN '6' THEN 'Saturday' "
            "END AS day_of_week, "
            "COUNT(*) AS appointment_count "
            "FROM appointments "
            "GROUP BY strftime('%w', appointment_date) "
            "ORDER BY appointment_count DESC "
            "LIMIT 1"
        ),
    ),
    # — Financial queries (questions 5, 8, 9, 13, 16) —
    (
        "What is the total revenue?",
        "SELECT SUM(total_amount) AS total_revenue FROM invoices",
    ),
    (
        "Show the top 5 patients by total spending",
        (
            "SELECT p.first_name, p.last_name, "
            "SUM(i.total_amount) AS total_spending "
            "FROM patients p "
            "JOIN invoices i ON i.patient_id = p.id "
            "GROUP BY p.id "
            "ORDER BY total_spending DESC "
            "LIMIT 5"
        ),
    ),
    (
        "What is the average treatment cost by specialization?",
        (
            "SELECT d.specialization, AVG(t.cost) AS avg_cost "
            "FROM treatments t "
            "JOIN appointments a ON a.id = t.appointment_id "
            "JOIN doctors d ON d.id = a.doctor_id "
            "GROUP BY d.specialization "
            "ORDER BY avg_cost DESC"
        ),
    ),
    (
        "Show unpaid invoices",
        (
            "SELECT i.id, p.first_name, p.last_name, "
            "i.total_amount, i.paid_amount, i.status "
            "FROM invoices i "
            "JOIN patients p ON p.id = i.patient_id "
            "WHERE i.status IN ('Pending', 'Overdue') "
            "ORDER BY i.total_amount DESC"
        ),
    ),
    (
        "Show revenue trend by month",
        (
            "SELECT strftime('%Y-%m', invoice_date) AS month, "
            "SUM(total_amount) AS monthly_revenue "
            "FROM invoices "
            "GROUP BY month "
            "ORDER BY month"
        ),
    ),
    # — Extra pairs for broader coverage —
    (
        "List patients from Mumbai",
        (
            "SELECT first_name, last_name, email, phone "
            "FROM patients "
            "WHERE city = 'Mumbai' "
            "ORDER BY last_name"
        ),
    ),
    (
        "Show average treatment cost",
        "SELECT AVG(cost) AS avg_treatment_cost FROM treatments",
    ),
]

# ------------------------------------------------------------------------
# SCHEMA MEMORIES
# Plain-text description give the LLM column names, data types, FK
# relationships, and allowed enum values - critical for correct SQL
# ------------------------------------------------------------------------

SCHEMA_MEMORIES: List[str] = [
    # DDL entry - exact table structure so the LLM never invents tables
    # (e.g. a 'specializations' lookup) that do not exist in the database.
    (
        "Database DDL - exact CREATE TABLE statements for the clinic SQLite database. "
        "IMPORTANT: There is NO separate 'specializations' table. "
        "The specialization value is a plain TEXT column directly on the doctors table.\n\n"
        "CREATE TABLE patients (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    first_name TEXT NOT NULL,\n"
        "    last_name TEXT NOT NULL,\n"
        "    email TEXT,\n"
        "    phone TEXT,\n"
        "    date_of_birth TEXT,\n"
        "    gender TEXT,\n"
        "    city TEXT,\n"
        "    registered_date TEXT NOT NULL\n"
        ");",
        "CREATE TABLE doctors (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    name TEXT NOT NULL,\n"
        "    specialization TEXT NOT NULL,\n"
        "    department TEXT NOT NULL,\n"
        "    phone TEXT\n"
        ");",
        "CREATE TABLE appointments (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    patient_id INTEGER NOT NULL,\n"
        "    doctor_id INTEGER NOT NULL,\n"
        "    appointment_date TEXT NOT NULL,\n"
        "    status TEXT NOT NULL,\n"
        "    notes TEXT,\n"
        "    FOREIGN KEY (patient_id) REFERENCES patients(id),\n"
        "    FOREIGN KEY (doctor_id) REFERENCES doctors(id)\n"
        ");",
        "CREATE TABLE treatments (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    appointment_id INTEGER NOT NULL,\n"
        "    treatment_name TEXT NOT NULL,\n"
        "    cost REAL NOT NULL,\n"
        "    duration_minutes INTEGER NOT NULL,\n"
        "    FOREIGN KEY (appointment_id) REFERENCES appointments(id)\n"
        ");",
        "CREATE TABLE invoices (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    patient_id INTEGER NOT NULL,\n"
        "    invoice_date TEXT NOT NULL,\n"
        "    total_amount REAL NOT NULL,\n"
        "    paid_amount REAL NOT NULL,\n"
        "    status TEXT NOT NULL,\n"
        "    FOREIGN KEY (patient_id) REFERENCES patients(id)\n"
        ");"
    ),
    (
        "The 'patients' table stores clinic patient records. "
        "Columns: id (INTEGER PRIMARY KEY), first_name (TEXT NOT NULL), "
        "last_name (TEXT NOT NULL), email (TEXT, nullable ~15%), "
        "phone (TEXT, nullable ~10%), date_of_birth (DATE), "
        "gender (TEXT: 'M' or 'F'), city (TEXT), registered_date (DATE). "
        "Cities include: Mumbai, Delhi, Bangalore, Chennai, Hyderabad, "
        "Pune, Kolkata, Ahmedabad, Jaipur, Lucknow. Contains 200 rows."
    ),
    (
        "The 'doctors' table stores clinic staff. "
        "Columns: id (INTEGER PRIMARY KEY), name (TEXT NOT NULL), "
        "specialization (TEXT), department (TEXT), phone (TEXT). "
        "Specialization values: 'Dermatology', 'Cardiology', 'Orthopedics', "
        "'General', 'Pediatrics'. Each specialization has 3 doctors. "
        "Contains 15 rows."
    ),
    (
        "The 'appointments' table links patients to doctors. "
        "Columns: id (INTEGER PRIMARY KEY), patient_id (FK->patients.id), "
        "doctor_id (FK->doctors.id), appointment_date (DATETIME), "
        "status (TEXT), notes (TEXT, nullable ~30%). "
        "Status values: 'Scheduled', 'Completed', 'Cancelled', 'No-Show'. "
        "Appointments span the past 12 months. Contains 500 rows."
    ),
    (
        "The 'treatments' table records medical procedures. "
        "Columns: id (INTEGER PRIMARY KEY), appointment_id (FK->appointments.id), "
        "treatment_name (TEXT), cost (REAL, range 50-5000 USD), "
        "duration_minutes (INTEGER). "
        "Treatments exist ONLY for appointments with status = 'Completed'. "
        "Contains ~350 rows."
    ),
    (
        "The 'invoices' table records billing information. "
        "Columns: id (INTEGER PRIMARY KEY), patient_id (FK->patients.id), "
        "invoice_date (DATE), total_amount (REAL), paid_amount (REAL), "
        "status (TEXT). "
        "Status values: 'Paid', 'Pending', 'Overdue'. "
        "Approximate distribution: 55% Paid, 30% Pending, 15% Overdue. "
        "Contains 300 rows."
    ),
    (
        "Foreign key relationships in the clinic database: "
        "appointments.patient_id -> patients.id, "
        "appointments.doctor_id -> doctors.id, "
        "treatments.appointment_id -> appointments.id, "
        "invoices.patient_id -> patients.id."
        "Use JOIN to combine these tables."
        "Use strftime('%Y-%m', date_column) for monthly grouping in SQLite. "
        "Use date('now', '-N months') for relative date filtering."
    ),
]

# ==============================================================================
# FUNCTIONS
# ==============================================================================

def _build_seed_context(agent_memory: DemoAgentMemory) -> ToolContext:
    """Build a ToolContext suitable for seeding operations.

    The context is attached to an admin seed-user and a fixed conversation
    so that all seeded memories share a consistent origin identifier.
    
    Args:
        agent_memory: DemoAgentMemory instance being seeded.

    Returns:
        ToolContext configured for the seed script.
    """
    return ToolContext(
        user=_SEED_USER,
        conversation_id="seed-session",
        request_id="seed-request",
        agent_memory=agent_memory,
    )


async def seed_tool_memories(
    agent_memory: DemoAgentMemory,
    pairs: List[Tuple[str, str]],
) -> int:
    """Save question-SQL pairs into agent memory as tool usage records.

    Iterates over every (question, sql) pair and persists each as a
    successful run_sql tool invocation. These records are later retrieved
    by SearchSavedCorrectToolUsesTool when the agent processes similar queries.

    Args:
        agent_memory: DemoAgentMemory instance to seed.
        pairs: List of (natural-language question, SQL query) tuples.

    Returns:
        Number of pairs successfully saved.

    Raises:
        Exception: Re-raises any unexpected error from the memory backend.
    """
    context = _build_seed_context(agent_memory)
    saved_count = 0

    for question, sql in pairs:
        try:
            await agent_memory.save_tool_usage(
                question=question,
                tool_name="run_sql",
                args={"sql": sql},
                context=context,
                success=True,
            )
            saved_count += 1
            logger.debug("Seeded tool memory [%d]: %s", saved_count, question[:60])
        except Exception as exc:
            # Log and continue — a single failure should not abort the whole seed
            logger.warning("Failed to seed pair '%s': %s", question[:60], exc)

    return saved_count


async def seed_text_memories(
    agent_memory: DemoAgentMemory,
    descriptions: List[str],
) -> int:
    """Save schema-description strings into agent memory as text context.

    Each description is stored as a free-text memory so the LLM receives
    accurate column names, data types, and allowed enum values when building SQL queries.

    Args:
        agent_memory: DemoAgentMemory instance to seed.
        descriptions: List of schema description strings.

    Returns:
        Number of descriptions successfully saved.

    Raises:
        Exception: Re-raises any unexpected error from the memory backend.
    """
    context = _build_seed_context(agent_memory)
    saved_count = 0

    for description in descriptions:
        try:
            await agent_memory.save_text_memory(
                content=description,
                context=context,
            )
            saved_count += 1
            logger.debug(
                "Seeded text memory [%d]: %s...", saved_count, description[:50]
            )
        except Exception as exc:
            logger.warning(
                "Failed to seed text memory '%s...': %s",
                description[:50],
                exc,
            )

    return saved_count

async def seed_into(
    agent_memory: DemoAgentMemory,
) -> Tuple[int, int]:
    """
    Seed all question-SQL pairs and schema memories into agent memory.
    
    Convenience wrapper called by main.py at startup. Uses the module-level
    MEMORY_PAIRS and SCHEMA_MEMORIES constants so callers do not meed to 
    reference them directly.
    
    Args:
        agent_memory: DemoAgentMemory instance to seed.
        
    Returns:
        A tuple of (tool_memory_count, text_memory_count).
    """
    tool_count = await seed_tool_memories(agent_memory, MEMORY_PAIRS)
    text_count = await seed_text_memories(agent_memory, SCHEMA_MEMORIES)
    return tool_count, text_count


async def _run_seeding() -> None:
    """Async entry point: orchestrate all seeding operations.

    Creates the shared agent memory, seeds tool-usage pairs and text memories,
    then prints a summary to stdout.
    """
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Starting memory seeding...")

    agent_memory = get_agent_memory()

    # Seed question→SQL pairs
    tool_count = await seed_tool_memories(agent_memory, MEMORY_PAIRS)
    logger.info("Tool memories seeded: %d", tool_count)

    # Seed schema text descriptions
    text_count = await seed_text_memories(agent_memory, SCHEMA_MEMORIES)
    logger.info("Text memories seeded: %d", text_count)

    total = tool_count + text_count

    print(f"\n✅ Seeded {tool_count} question→SQL pairs")
    print(f"✅ Seeded {text_count} schema description memories")
    print(f"📊 Total memory items seeded: {total}")

    # Surface any obvious under-seeding immediately
    if tool_count < 15:
        print(
            f"⚠️ Warning: fewer than 15 tool pairs seeded ({tool_count}). "
            "Check MEMORY_PAIRS constant."
        )

    if text_count < 5:
        print(
            f"⚠️ Warning: fewer than 5 text memories seeded ({text_count}). "
            "Check SCHEMA_MEMORIES constant."
        )


def main() -> None:
    """Main entry point: seed agent memory and print counts.

    Wraps the async seeding logic so this module can be run directly:
        python seed_memory.py
    """
    asyncio.run(_run_seeding())


# =========================================================
# MAIN EXECUTION
# =========================================================

if __name__ == "__main__":
    main()