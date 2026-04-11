"""
Module: test_validator.py
Description: Unit tests for the SQL and input validation functions.

Test cover all validation rules defined in validators.py including:
    - Valid SELECT queries pass
    - Non-SELECT queries are rejected
    - Blocked keywords are caught
    - System table access is rejected
    - Semicolon injection is rejected
    - Question length bounds are enforced
    
Usage: 
    pytest tests/test_validator.py -v
    
    
    
"""

# ==============================================================
# IMPORTS
# ==============================================================

import pytest

from validators import validate_sql, validate_question


# ==============================================================
# SQL VALIDATION TESTS
# ==============================================================

class TestValidateSql:
    """Tests for the validate_sql() function."""

    def test_valid_select_passes(self) -> None:
        """A plain SELECT query should pass validation."""
        is_valid, msg = validate_sql("SELECT * FROM patients")
        assert is_valid is True
        assert msg == ""

    def test_select_with_join_passes(self) -> None:
        """A SELECT with JOIN should pass validation."""
        sql = (
            "SELECT p.first_name, d.name "
            "FROM patients p "
            "JOIN appointments a ON a.patient_id = p.id "
            "JOIN doctors d ON d.id = a.doctor_id"
        )
        is_valid, msg = validate_sql(sql)
        assert is_valid is True
        assert msg == ""

    def test_drop_table_blocked(self) -> None:
        """DROP TABLE must be rejected before the SELECT check fires."""
        is_valid, msg = validate_sql("DROP TABLE patients")
        assert is_valid is False
        # Non-SELECT triggers the SELECT rule, not the keyword rule
        assert "SELECT" in msg or "keyword" in msg.lower()

    def test_insert_blocked(self) -> None:
        """INSERT must be rejected."""
        is_valid, msg = validate_sql("INSERT INTO patients VALUES (1, 'John', 'Doe')")
        assert is_valid is False

    def test_update_blocked(self) -> None:
        """UPDATE must be rejected."""
        is_valid, msg = validate_sql("UPDATE patients SET first_name = 'Jane'")
        assert is_valid is False

    def test_delete_blocked(self) -> None:
        """DELETE must be rejected."""
        is_valid, msg = validate_sql("DELETE FROM patients WHERE id = 1")
        assert is_valid is False

    def test_system_table_blocked(self) -> None:
        """Queries targeting sqlite_master must be rejected."""
        is_valid, msg = validate_sql("SELECT * FROM sqlite_master")
        assert is_valid is False
        assert "system table" in msg.lower()

    def test_semicolon_injection_blocked(self) -> None:
        """Multiple statements joined with semicolons must be rejected."""
        is_valid, msg = validate_sql("SELECT * FROM patients; DROP TABLE patients")
        assert is_valid is False
        assert "semicolon" in msg.lower() or "multiple" in msg.lower()

    def test_empty_sql_rejected(self) -> None:
        """An empty SQL string must be rejected."""
        is_valid, msg = validate_sql("")
        assert is_valid is False
        assert "empty" in msg.lower()

    def test_mixed_case_keyword_blocked(self) -> None:
        """Blocked keywords in mixed case (e.g. DRoP) must still be caught."""
        is_valid, msg = validate_sql("DrOp TABLE patients")
        assert is_valid is False

    def test_comment_hidden_drop_blocked(self) -> None:
        """A DROP hidden inside block comments must be rejected."""
        # After comment stripping, the remaining text is 'DROP TABLE patients'
        # which does not start with SELECT.
        is_valid, msg = validate_sql("/* harmless */ DROP TABLE patients")
        assert is_valid is False

    def test_select_keyword_in_subquery_passes(self) -> None:
        """A nested SELECT subquery must still pass validation."""
        sql = (
            "SELECT first_name FROM patients "
            "WHERE id IN (SELECT patient_id FROM appointments WHERE status = 'Completed')"
        )
        is_valid, msg = validate_sql(sql)
        assert is_valid is True

    def test_null_byte_blocked(self) -> None:
        """A SQL string containing a NULL byte must be rejected."""
        is_valid, msg = validate_sql("SELECT * FROM patients\x00")
        assert is_valid is False
        assert "null" in msg.lower()

    def test_none_raises_value_error(self) -> None:
        """Passing None should raise ValueError, not return a tuple."""
        with pytest.raises(ValueError):
            validate_sql(None)  # type: ignore[arg-type]

    def test_too_long_sql_rejected(self) -> None:
        """SQL exceeding MAX_SQL_LENGTH must be rejected."""
        is_valid, msg = validate_sql("SELECT * FROM patients WHERE id = " + "1" * 5001)
        assert is_valid is False
        assert "too long" in msg.lower()


# =============================================================================
# QUESTION VALIDATION TESTS
# =============================================================================

class TestValidateQuestion:
    """Tests for the validate_question() function."""

    def test_valid_question_passes(self) -> None:
        """A normal question should pass validation."""
        is_valid, msg = validate_question("How many patients do we have?")
        assert is_valid is True
        assert msg == ""

    def test_empty_question_rejected(self) -> None:
        """An empty string must be rejected."""
        is_valid, msg = validate_question("")
        assert is_valid is False
        assert "empty" in msg.lower()

    def test_whitespace_only_rejected(self) -> None:
        """A whitespace-only string must be rejected."""
        is_valid, msg = validate_question("   ")
        assert is_valid is False
        assert "empty" in msg.lower()

    def test_too_short_rejected(self) -> None:
        """A question shorter than MIN_QUESTION_LENGTH must be rejected."""
        is_valid, msg = validate_question("Hi")
        assert is_valid is False
        assert "short" in msg.lower()

    def test_too_long_rejected(self) -> None:
        """A question longer than MAX_QUESTION_LENGTH must be rejected."""
        is_valid, msg = validate_question("a" * 501)
        assert is_valid is False
        assert "long" in msg.lower()

    def test_no_letters_rejected(self) -> None:
        """A string with no alphabetic characters must be rejected."""
        is_valid, msg = validate_question("12345 !@#$%")
        assert is_valid is False
        assert "letter" in msg.lower()

    def test_exactly_min_length_passes(self) -> None:
        """A question of exactly MIN_QUESTION_LENGTH characters must pass."""
        # MIN_QUESTION_LENGTH is 3; 'abc' meets that threshold exactly
        is_valid, _ = validate_question("abc")
        assert is_valid is True

    def test_exactly_max_length_passes(self) -> None:
        """A question of exactly MAX_QUESTION_LENGTH characters must pass."""
        is_valid, _ = validate_question("a" * 500)
        assert is_valid is True