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
