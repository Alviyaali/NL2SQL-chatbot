"""
Module: setup_database.py
Description: Creates the clinic SQLite database with schema and dummy data.

This module creates a SQLite database (clinic.db) with 5 tables:
patients, doctors, appointments, treatments, and invoices.
It populates these tables with realistic dummy data suitable for testing the NL2SQL chatbot.


Usage:
    python setup_database.py
    
Output: 
    - Creates clinic.db in the current directory
    - Prints a summary of created records
"""

# ==================================================================
# Imports
# ==================================================================

import logging
import os
import sqlite3
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple


from config import (
    APPOINTMENT_STATUS_WEIGHTS,
    APPOINTMENT_STATUSES,
    CITIES,
    DATABASE_PATH,
    INVOICE_STATUS_WEIGHTS,
    INVOICE_STATUSES,
    NUM_APPOINTMENTS,
    NUM_DOCTORS,
    NUM_PATIENTS,
    NUM_TREATMENTS,
    NUM_INVOICES,
    SPECIALIZATIONS,
)

# ==================================================================
# CONSTANTS
# ==================================================================

logger = logging.getLogger(__name__)

# Indian first names — split by gender for realistic assignment
FIRST_NAMES_MALE: List[str] = [
    "Aarav", "Arjun", "Vivaan", "Aditya", "Vihaan", "Sai", "Aryan",
    "Reyansh", "Ayaan", "Krishna", "Ishaan", "Shaurya", "Atharv",
    "Rahul", "Raj", "Amit", "Suresh", "Vijay", "Ravi", "Manoj",
    "Deepak", "Rakesh", "Nikhil", "Karthik", "Rohan", "Vikram", "Sunil",
    "Prateek", "Gaurav", "Siddharth", "Varun", "Tarun", "Harish", "Naveen",
]

FIRST_NAMES_FEMALE: List[str] = [
    "Priya", "Ananya", "Isha", "Kavya", "Pooja", "Neha", "Sneha", "Riya",
    "Tanvi", "Aisha", "Diya", "Meera", "Siya", "Nisha", "Simran", "Anjali",
    "Divya", "Swati", "Rekha", "Sunita", "Radha", "Poonam", "Geeta", "Lata",
    "Shreya", "Natasha", "Bhavna", "Seema", "Amrita", "Vandana", "Usha",
]

LAST_NAMES: List[str] = [
    "Sharma", "Verma", "Gupta", "Kumar", "Singh", "Joshi", "Patel",
    "Malhotra", "Agarwal", "Mehta", "Shah", "Reddy", "Nair", "Iyer",
    "Rao", "Desai", "Jain", "Kapoor", "Chopra", "Bose", "Mishra",
    "Pandey", "Tiwari", "Chaudhary", "Saxena", "Sinha", "Roy", "Das",
    "Mukherjee", "Chatterjee", "Bhattacharya", "Pillai",
]

# Exactly 15 doctor names — 3 per specialization
DOCTOR_NAMES: List[str] = [
    "Dr. Rajesh Sharma",   "Dr. Priya Nair",      "Dr. Anil Kumar",
    "Dr. Sunita Verma",    "Dr. Manoj Gupta",     "Dr. Kavitha Reddy",
    "Dr. Vikram Singh",    "Dr. Ananya Iyer",     "Dr. Suresh Patel",
    "Dr. Meera Joshi",     "Dr. Deepak Malhotra", "Dr. Sneha Agarwal",
    "Dr. Arjun Mehta",     "Dr. Pooja Shah",      "Dr. Rahul Desai",
]

# Maps specialization -> department name shown in the doctors table
DEPARTMENTS: Dict[str, str] = {
    "Dermatology": "Skin Care",
    "Cardiology": "Heart & Vascular",
    "Orthopedics": "Bone & Joint",
    "General": "General Medicine",
    "Pediatrics": "Child Health",
}

TREATMENT_NAMES: List[str] = [
    "General Consultation", "Blood Test", "X-Ray", "ECG", "MRI Scan",
    "Ultrasound", "Skin Biopsy", "Physiotherapy", "Vaccination",
    "Blood Pressure Monitoring", "Diabetes Management",
    "Orthopedic Consultation", "Cardiology Checkup", "Pediatric Checkup",
    "Dermatology Treatment", "Minor Surgery", "Eye Examination",
    "Nutritional Counseling", "Wound Dressing", "IV Therapy",
]

APPOINTMENT_NOTES: List[str] = [
    "Patient reports mild fever",
    "Follow-up consultation required",
    "Patient advised rest for 3 days",
    "Medication prescribed",
    "Lab reports reviewed",
    "Referred to specialist",
    "Routine checkup",
    "Patient recovering well",
    "Blood pressure elevated",
    "Vaccination administered",
]

GENDERS: List[str] = ["Male", "Female", "Other"]
# Reflect a roughly balanced real-world gender split
GENDER_WEIGHTS: List[float] = [0.49, 0.49, 0.02]

EMAIL_DOMAINS: List[str] = [
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "mail.com",
]

# ==================================================================
# DATABASE SETUP FUNCTIONS
# ==================================================================

def create_connection(db_path: str) -> sqlite3.Connection:
    """Create and return a SQLite database connection with foreign keys enabled.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Active SQLite connection object.
    """
    conn = sqlite3.connect(db_path)
    # SQLite disables FK enforcement by default; enable it per connection
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def drop_existing_tables(cursor: sqlite3.Cursor) -> None:
    """Drop all existing clinic tables to allow a clean recreation.

    Tables are dropped in reverse dependency order to satisfy FK constraints.

    Args:
        cursor: Active database cursor.
    """
    # Treatments reference appointments; drop dependents first
    tables = ["treatments", "invoices", "appointments", "doctors", "patients"]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")


def create_patients_table(cursor: sqlite3.Cursor) -> None:
    """Create the patients table.

    Args:
        cursor: Active database cursor.
    """
    cursor.execute("""
        CREATE TABLE patients (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name      TEXT NOT NULL,
            last_name       TEXT NOT NULL,
            email           TEXT,
            phone           TEXT,
            date_of_birth   TEXT,
            gender          TEXT,
            city            TEXT,
            registered_date TEXT NOT NULL
        )
    """)


def create_doctors_table(cursor: sqlite3.Cursor) -> None:
    """Create the doctors table.

    Args:
        cursor: Active database cursor.
    """
    cursor.execute("""
        CREATE TABLE doctors (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            specialization TEXT NOT NULL,
            department    TEXT NOT NULL,
            phone         TEXT NOT NULL
        )
    """)


def create_appointments_table(cursor: sqlite3.Cursor) -> None:
    """Create the appointments table with foreign key references to patients and doctors.

    Args:
        cursor: Active database cursor.
    """
    cursor.execute("""
        CREATE TABLE appointments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id       INTEGER NOT NULL,
            doctor_id        INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            status           TEXT NOT NULL,
            notes            TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )
    """)


def create_treatments_table(cursor: sqlite3.Cursor) -> None:
    """Create the treatments table with a foreign key reference to appointments.

    Args:
        cursor: Active database cursor.
    """
    cursor.execute("""
        CREATE TABLE treatments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id   INTEGER NOT NULL,
            treatment_name   TEXT NOT NULL,
            cost             REAL NOT NULL,
            duration_minutes INTEGER NOT NULL,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id)
        )
    """)


def create_invoices_table(cursor: sqlite3.Cursor) -> None:
    """Create the invoices table with a foreign key reference to patients.

    Args:
        cursor: Active database cursor.
    """
    cursor.execute("""
        CREATE TABLE invoices (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id    INTEGER NOT NULL,
            invoice_date  TEXT NOT NULL,
            total_amount  REAL NOT NULL,
            paid_amount   REAL NOT NULL,
            status        TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)


def create_all_tables(cursor: sqlite3.Cursor) -> None:
    """Create all five clinic database tables in dependency order.

    Tables are created so that referenced tables always exist before
    the tables that reference them.

    Args:
        cursor: Active database cursor.
    """
    create_patients_table(cursor)
    create_doctors_table(cursor)
    create_appointments_table(cursor)
    create_treatments_table(cursor)
    create_invoices_table(cursor)

# ==================================================================
# DATA GENERATION HELPERS
# ==================================================================

def random_date_str(start_days_ago: int, end_days_ago: int = 0) -> str:
    """Generate a random date string in YYYY-MM-DD format within a past window.

    Args:
        start_days_ago: The farthest point in the past (inclusive), in days.
        end_days_ago: The closest point in the past (inclusive), in days.
            Defaults to 0 (today).

    Returns:
        Date string formatted as YYYY-MM-DD.

    Examples:
        >>> random_date_str(365, 30)  # Between 30 and 365 days ago
        "2025-08-15"
    """
    days_ago = random.randint(end_days_ago, start_days_ago)
    target_date = datetime.now() - timedelta(days=days_ago)
    return target_date.strftime("%Y-%m-%d")


def generate_email(first_name: str, last_name: str) -> str:
    """Generate a realistic email address derived from a patient's name.

    Uses multiple name-pattern templates to create variety across patients.

    Args:
        first_name: Patient's first name.
        last_name: Patient's last name.

    Returns:
        Email address string, e.g. "priya.sharma@gmail.com".
    """
    suffix = random.randint(1, 99)
    patterns = [
        f"{first_name.lower()}.{last_name.lower()}",
        f"{first_name.lower()}{suffix}",
        f"{first_name[0].lower()}{last_name.lower()}",
        f"{first_name.lower()}{first_name[0].lower()}",
    ]
    return f"{random.choice(patterns)}@{random.choice(EMAIL_DOMAINS)}"

def generate_phone() -> str:
    """Generate a realistic 10-digit Indian mobile number.

    Returns:
        Phone number string starting with 6, 7, 8, or 9.
    """
    # Indian mobile numbers begin with 6, 7, 8, or 9
    prefix = random.choice(["6", "7", "8", "9"])
    digits = "".join(str(random.randint(0, 9)) for _ in range(9))
    return f"{prefix}{digits}"


def build_doctor_appointment_weights(doctor_ids: List[int]) -> List[float]:
    """Create unequal appointment weights to simulate doctor load imbalance.

    The top ~30% of doctors receive 3× the appointment rate of the rest,
    mirroring how popular or senior doctors tend to be busier.

    Args:
        doctor_ids: Ordered list of doctor IDs.

    Returns:
        List of float weights, one per doctor ID.
    """
    popular_count = max(1, int(len(doctor_ids) * 0.3))
    # Popular doctors get triple the weight of their colleagues
    weights = [3.0 if i < popular_count else 1.0 for i in range(len(doctor_ids))]
    return weights


def generate_appointment_patient_ids(
    patient_ids: List[int],
    count: int,
) -> List[int]:
    """Assign patient IDs to appointments with a realistic visit-frequency distribution.

    Distribution targets:
        ~20% of patients -> high-frequency visitors (weight 7)
        ~30% of patients -> moderate visitors (weight 3)
        ~50% of patients -> single-visit patients (weight 1)

    Args:
        patient_ids: Full list of patient IDs to draw from.
        count: Total number of appointment-to-patient assignments needed.

    Returns:
        List of patient IDs of length `count`.
    """
    num_patients = len(patient_ids)
    repeat_count = int(num_patients * 0.2)
    moderate_count = int(num_patients * 0.3)
    single_count = num_patients - repeat_count - moderate_count

    weights = (
        [7.0] * repeat_count +
        [3.0] * moderate_count +
        [1.0] * single_count
    )
    return random.choices(patient_ids, weights=weights, k=count)


# =============================================================================
# DATA INSERTION FUNCTIONS
# =============================================================================

def insert_doctors(cursor: sqlite3.Cursor) -> List[int]:
    """Insert 15 doctors – exactly 3 per specialization – and return their IDs.

    Args:
        cursor: Active database cursor.

    Returns:
        List of inserted doctor IDs (1-indexed, length 15).
    """
    doctors: List[Dict[str, Any]] = []

    # Pair each specialization with the next three names from DOCTOR_NAMES
    for spec_idx, specialization in enumerate(SPECIALIZATIONS):
        for slot in range(3):
            doctors.append({
                "name": DOCTOR_NAMES[spec_idx * 3 + slot],
                "specialization": specialization,
                "department": DEPARTMENTS[specialization],
                "phone": generate_phone(),
            })

    cursor.executemany(
        """
        INSERT INTO doctors (name, specialization, department, phone)
        VALUES (:name, :specialization, :department, :phone)
        """,
        doctors,
    )
    return list(range(1, len(doctors) + 1))


def generate_patient_record() -> Dict[str, Any]:
    """Generate a single random patient record with realistic field values.

    Applies NULL rates: ~15% missing email, ~10% missing phone,
    to simulate incomplete real-world patient data.

    Returns:
        Dictionary mapping patient column names to their values.
    """
    gender = random.choices(GENDERS, weights=GENDER_WEIGHTS, k=1)[0]
    # Pick from the appropriate name pool based on gender
    first_name_pool = FIRST_NAMES_FEMALE if gender == "Female" else FIRST_NAMES_MALE
    first_name = random.choice(first_name_pool)
    last_name = random.choice(LAST_NAMES)

    # Apply realistic NULL rates for optional contact fields
    email = generate_email(first_name, last_name) if random.random() > 0.15 else None
    phone = generate_phone() if random.random() > 0.10 else None

    # Patient ages: 10–80 years old
    age_days = random.randint(365 * 10, 365 * 80)
    dob = (datetime.now() - timedelta(days=age_days)).strftime("%Y-%m-%d")

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "date_of_birth": dob,
        "gender": gender,
        "city": random.choice(CITIES),
        # Patients registered within the last 2 years
        "registered_date": random_date_str(730),
    }


def insert_patients(cursor: sqlite3.Cursor, count: int) -> List[int]:
    """Insert patient records and return their IDs.

    Args:
        cursor: Active database cursor.
        count: Number of patients to insert.

    Returns:
        List of inserted patient IDs (1-indexed).
    """
    patients = [generate_patient_record() for _ in range(count)]
    cursor.executemany(
        """
        INSERT INTO patients
            (first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
        VALUES
            (:first_name, :last_name, :email, :phone, :date_of_birth, :gender, :city, :registered_date)
        """,
        patients,
    )
    return list(range(1, count + 1))


def insert_appointments(
    cursor: sqlite3.Cursor,
    patient_ids: List[int],
    doctor_ids: List[int],
    count: int,
) -> Tuple[List[int], List[int]]:
    """Insert appointment records and return all and completed appointment IDs.

    Applies ~30% NULL rate for notes to simulate missing documentation.

    Args:
        cursor: Active database cursor.
        patient_ids: List of available patient IDs.
        doctor_ids: List of available doctor IDs.
        count: Number of appointments to insert.

    Returns:
        Tuple of (all_appointment_ids, completed_appointment_ids).
    """
    doctor_weights = build_doctor_appointment_weights(doctor_ids)
    assigned_patients = generate_appointment_patient_ids(patient_ids, count)

    appointments: List[Dict[str, Any]] = []
    for patient_id in assigned_patients:
        doctor_id = random.choices(doctor_ids, weights=doctor_weights, k=1)[0]
        status = random.choices(
            APPOINTMENT_STATUSES, weights=APPOINTMENT_STATUS_WEIGHTS, k=1
        )[0]
        # ~30% of appointments have no attached notes
        notes = random.choice(APPOINTMENT_NOTES) if random.random() > 0.30 else None

        appointments.append({
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "appointment_date": random_date_str(365),  # Within the past year
            "status": status,
            "notes": notes,
        })

    cursor.executemany(
        """
        INSERT INTO appointments (patient_id, doctor_id, appointment_date, status, notes)
        VALUES (:patient_id, :doctor_id, :appointment_date, :status, :notes)
        """,
        appointments,
    )

    # Fetch IDs split by status so callers can use the completed subset
    cursor.execute("SELECT id, status FROM appointments")
    rows = cursor.fetchall()
    all_ids = [row[0] for row in rows]
    completed_ids = [row[0] for row in rows if row[1] == "Completed"]
    return all_ids, completed_ids


def insert_treatments(
    cursor: sqlite3.Cursor,
    completed_appointment_ids: List[int],
    count: int,
) -> int:
    """Insert treatment records linked only to completed appointments.

    Treatments are distributed across completed appointments using sampling
    with replacement, so some appointments may have multiple treatments.

    Args:
        cursor: Active database cursor.
        completed_appointment_ids: IDs of completed appointments only.
        count: Total number of treatments to insert.

    Returns:
        Number of treatments inserted (0 if no completed appointments exist).
    """
    if not completed_appointment_ids:
        logger.warning("No completed appointments found; skipping treatment insertion.")
        return 0

    # Sampling with replacement allows multiple treatments per appointment
    assigned_ids = random.choices(completed_appointment_ids, k=count)
    treatments: List[Dict[str, Any]] = []
    for appointment_id in assigned_ids:
        treatments.append({
            "appointment_id": appointment_id,
            "treatment_name": random.choice(TREATMENT_NAMES),
            # Realistic clinical costs in USD; spread is intentionally wide
            "cost": round(random.uniform(50.0, 5000.0), 2),
            "duration_minutes": random.choice([15, 20, 30, 45, 60, 90, 120]),
        })

    cursor.executemany(
        """
        INSERT INTO treatments (appointment_id, treatment_name, cost, duration_minutes)
        VALUES (:appointment_id, :treatment_name, :cost, :duration_minutes)
        """,
        treatments,
    )
    return len(treatments)


def generate_invoice_record(patient_id: int) -> Dict[str, Any]:
    """Generate a single invoice record with a status-consistent paid amount.

    Args:
        patient_id: ID of the patient this invoice belongs to.

    Returns:
        Dictionary mapping invoice column names to their values.
    """
    status = random.choices(INVOICE_STATUSES, weights=INVOICE_STATUS_WEIGHTS, k=1)[0]
    total_amount = round(random.uniform(50.0, 5000.0), 2)

    # Derive paid_amount based on status for data consistency
    if status == "Paid":
        paid_amount = total_amount
    elif status == "Pending":
        # Partial advance payment is common for pending invoices
        paid_amount = round(random.uniform(0.0, total_amount * 0.5), 2)
    else:  # Overdue — no payment received yet
        paid_amount = 0.0

    return {
        "patient_id": patient_id,
        "invoice_date": random_date_str(365),
        "total_amount": total_amount,
        "paid_amount": paid_amount,
        "status": status,
    }


def insert_invoices(
    cursor: sqlite3.Cursor,
    patient_ids: List[int],
    count: int,
) -> int:
    """Insert invoice records assigned randomly across patients.

    Args:
        cursor: Active database cursor.
        patient_ids: List of available patient IDs.
        count: Number of invoices to insert.

    Returns:
        Number of invoices inserted.
    """
    # A patient can have multiple invoices (different visits/billing periods)
    assigned_patient_ids = random.choices(patient_ids, k=count)
    invoices = [generate_invoice_record(pid) for pid in assigned_patient_ids]

    cursor.executemany(
        """
        INSERT INTO invoices (patient_id, invoice_date, total_amount, paid_amount, status)
        VALUES (:patient_id, :invoice_date, :total_amount, :paid_amount, :status)
        """,
        invoices,
    )
    return len(invoices)

# =============================================================================
# REPORTING
# =============================================================================

def print_table_counts(cursor: sqlite3.Cursor) -> None:
    """Print the record count for each clinic table."""

    tables = {
        "patients": "Patients",
        "doctors": "Doctors",
        "appointments": "Appointments",
        "treatments": "Treatments",
        "invoices": "Invoices"
    }

    for table, label in tables.items():
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {label:<15} {count:>5} records")


def print_status_breakdown(cursor: sqlite3.Cursor) -> None:
    """Print appointment and invoice status breakdowns.
    
    Args:
        cursor: Active database cursor.
    """

    cursor.execute(
        "SELECT status, COUNT(*) FROM appointments GROUP BY status ORDER BY COUNT(*) DESC"
    )
    print("\n Appointment Status Breakdown:")
    for status, count in cursor.fetchall():
        print(f"  {status:<15} {count:>5}")

    cursor.execute(
        "SELECT status, COUNT(*) FROM invoices GROUP BY status ORDER BY COUNT(*) DESC"
    )
    print("\n Invoice Status Breakdown:")
    for status, count in cursor.fetchall():
        print(f"  {status:<15} {count:>5}")


def print_summary(cursor: sqlite3.Cursor) -> None:
    """Print a complete summary of all records inserted into the database.
    
    """

    print("\n" + "=" * 52)
    print(" DATABASE SETUP COMPLETE – RECORD SUMMARY")
    print("=" * 52)

    print_table_counts(cursor)
    print_status_breakdown(cursor)

    print("=" * 52 + "\n")


# =================================
# MAIN EXECUTION
# =================================

def main() -> None:
    """Main entry point: create the database schema and populate with dummy data."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Remove any existing database so each run produces a clean, reproducible state
    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)
        logger.info("Removed existing database: %s", DATABASE_PATH)

    logger.info("Creating database: %s", DATABASE_PATH)

    conn = create_connection(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        logger.info("Dropping and recreating tables...")
        drop_existing_tables(cursor)
        create_all_tables(cursor)

        logger.info("Inserting %d doctors...", NUM_DOCTORS)
        doctor_ids = insert_doctors(cursor)

        logger.info("Inserting %d patients...", NUM_PATIENTS)
        patient_ids = insert_patients(cursor, NUM_PATIENTS)

        logger.info("Inserting %d appointments...", NUM_APPOINTMENTS)
        _,completed_ids = insert_appointments(
            cursor, patient_ids, doctor_ids, NUM_APPOINTMENTS
        )

        logger.info(
            "%d appointments are marked Completed (eligible for treatments).",
            len(completed_ids),
        )

        logger.info("Inserting %d treatments...", NUM_TREATMENTS)
        inserted_treatments = insert_treatments(
            cursor, completed_ids, NUM_TREATMENTS
        )
        logger.info("%d treatments inserted.", inserted_treatments)

        logger.info("Inserting %d invoices...", NUM_INVOICES)
        insert_invoices(cursor, patient_ids, NUM_INVOICES)

        conn.commit()
        print_summary(cursor)

    except Exception as exc:
        conn.rollback()
        logger.error("Database setup failed: %s", exc, exc_info=True)

    finally:
        conn.close()
        

if __name__ == "__main__":
    main()