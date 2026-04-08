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

