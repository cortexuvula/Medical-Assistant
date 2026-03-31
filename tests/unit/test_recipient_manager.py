"""
Comprehensive tests for managers/recipient_manager.py.

Tests cover:
- Singleton behaviour
- CRUD: get_all_recipients, get_recipient, save_recipient, update_recipient, delete_recipient
- Usage tracking: increment_usage, toggle_favorite
- Queries: get_recent_recipients, get_frequent_recipients, get_favorites,
           search_recipients, get_recipients_by_specialty
- CSV import: import_from_csv, preview_csv
- Helpers: _parse_csv_row, _check_duplicate, get_formatted_address, _row_to_dict
"""

import csv
import os
import sys
import pytest
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))

from managers.recipient_manager import RecipientManager, get_recipient_manager  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row_15():
    """Return a 15-element row tuple (old schema)."""
    return (
        1,           # id
        "Dr. Smith", # name
        "specialist",# recipient_type
        "Cardiology",# specialty
        "Heart Clinic",  # facility
        "123 Main St",   # address
        "555-1111",      # fax
        "555-2222",      # phone
        "smith@example.com",  # email
        "Some notes",    # notes
        "2024-01-01",    # last_used
        5,               # use_count
        1,               # is_favorite
        "2023-01-01",    # created_at
        "2024-01-01",    # updated_at
    )


def _make_row_25():
    """Return a 25-element row tuple (new schema after migration 10)."""
    return _make_row_15() + (
        "John",       # first_name
        "Smith",      # last_name
        "A",          # middle_name
        "Dr.",        # title
        "PAY001",     # payee_number
        "PRAC001",    # practitioner_number
        "100 Office Rd",  # office_address
        "Calgary",    # city
        "AB",         # province
        "T1X 1X1",    # postal_code
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_manager():
    """
    Yield a fresh RecipientManager with a fully mocked db_manager.

    Resets the singleton both before and after the test so isolation is
    guaranteed regardless of module-level initialisation order.
    """
    RecipientManager._instance = None

    mock_db = MagicMock()
    with patch("managers.recipient_manager.get_db_manager", return_value=mock_db):
        mgr = RecipientManager()
        yield mgr, mock_db

    # Cleanup – next test gets a virgin singleton slot
    RecipientManager._instance = None


# ===========================================================================
# TestRecipientManagerSingleton
# ===========================================================================

class TestRecipientManagerSingleton:
    """Verify singleton semantics."""

    def test_singleton_returns_same_instance(self):
        """Two consecutive instantiations return the identical object."""
        RecipientManager._instance = None
        with patch("managers.recipient_manager.get_db_manager", return_value=MagicMock()):
            a = RecipientManager()
            b = RecipientManager()
            assert a is b
        RecipientManager._instance = None

    def test_reset_singleton_creates_new_instance(self):
        """After resetting _instance, a new object is created."""
        RecipientManager._instance = None
        with patch("managers.recipient_manager.get_db_manager", return_value=MagicMock()):
            a = RecipientManager()
            RecipientManager._instance = None
            b = RecipientManager()
            assert a is not b
        RecipientManager._instance = None

    def test_module_level_instance_exists(self):
        """The module exposes a convenience ``recipient_manager`` alias."""
        import managers.recipient_manager as rm
        assert rm.recipient_manager is not None


# ===========================================================================
# TestGetAllRecipients
# ===========================================================================

class TestGetAllRecipients:
    """Tests for get_all_recipients."""

    def test_get_all_recipients_no_filter(self, fresh_manager):
        """Without a type filter all rows are fetched and converted."""
        mgr, mock_db = fresh_manager
        row = _make_row_25()
        mock_db.fetchall.return_value = [row]

        result = mgr.get_all_recipients()

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["name"] == "Dr. Smith"
        # Verify no filter param was passed (second call arg absent / None)
        args, kwargs = mock_db.fetchall.call_args
        assert len(args) == 1  # only the SQL string, no params tuple

    def test_get_all_recipients_with_type_filter(self, fresh_manager):
        """Passing recipient_type appends a WHERE clause with the value."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.return_value = [_make_row_25()]

        result = mgr.get_all_recipients(recipient_type="specialist")

        assert len(result) == 1
        args, kwargs = mock_db.fetchall.call_args
        # The second positional arg should be the bind parameter tuple
        assert args[1] == ("specialist",)

    def test_get_all_recipients_returns_empty_list_on_db_error(self, fresh_manager):
        """A database exception is swallowed and an empty list returned."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.side_effect = RuntimeError("db gone")

        result = mgr.get_all_recipients()

        assert result == []

    def test_get_all_recipients_empty_db(self, fresh_manager):
        """fetchall returning None produces an empty list (not an error)."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.return_value = None

        result = mgr.get_all_recipients()

        assert result == []


# ===========================================================================
# TestGetRecipient
# ===========================================================================

class TestGetRecipient:
    """Tests for get_recipient."""

    def test_get_recipient_found(self, fresh_manager):
        """A row returned by fetchone is converted to a dict."""
        mgr, mock_db = fresh_manager
        mock_db.fetchone.return_value = _make_row_25()

        result = mgr.get_recipient(1)

        assert result is not None
        assert result["id"] == 1
        assert result["specialty"] == "Cardiology"

    def test_get_recipient_not_found(self, fresh_manager):
        """fetchone returning None gives back None."""
        mgr, mock_db = fresh_manager
        mock_db.fetchone.return_value = None

        result = mgr.get_recipient(999)

        assert result is None

    def test_get_recipient_db_error(self, fresh_manager):
        """A database exception is swallowed and None returned."""
        mgr, mock_db = fresh_manager
        mock_db.fetchone.side_effect = Exception("connection failed")

        result = mgr.get_recipient(1)

        assert result is None


# ===========================================================================
# TestSaveRecipient
# ===========================================================================

class TestSaveRecipient:
    """Tests for save_recipient."""

    def test_save_recipient_with_name(self, fresh_manager):
        """An explicit 'name' field is used verbatim."""
        mgr, mock_db = fresh_manager
        mock_result = MagicMock()
        mock_result.lastrowid = 42
        mock_db.execute.return_value = mock_result

        recipient_id = mgr.save_recipient({"name": "Dr. Brown", "specialty": "Neurology"})

        assert recipient_id == 42
        args, _ = mock_db.execute.call_args
        # First param in the bind-values tuple should be "Dr. Brown"
        assert args[1][0] == "Dr. Brown"

    def test_save_recipient_builds_name_from_parts(self, fresh_manager):
        """When name is empty, first_name + last_name are joined."""
        mgr, mock_db = fresh_manager
        mock_result = MagicMock()
        mock_result.lastrowid = 10
        mock_db.execute.return_value = mock_result

        recipient_id = mgr.save_recipient({"first_name": "Jane", "last_name": "Doe"})

        assert recipient_id == 10
        args, _ = mock_db.execute.call_args
        assert args[1][0] == "Jane Doe"

    def test_save_recipient_with_title_first_last(self, fresh_manager):
        """Title, first_name and last_name are concatenated in order."""
        mgr, mock_db = fresh_manager
        mock_result = MagicMock()
        mock_result.lastrowid = 7
        mock_db.execute.return_value = mock_result

        recipient_id = mgr.save_recipient(
            {"title": "Dr.", "first_name": "Alice", "last_name": "Wong"}
        )

        assert recipient_id == 7
        args, _ = mock_db.execute.call_args
        assert args[1][0] == "Dr. Alice Wong"

    def test_save_recipient_uses_unknown_when_no_name(self, fresh_manager):
        """If no name parts at all, 'Unknown' is stored."""
        mgr, mock_db = fresh_manager
        mock_result = MagicMock()
        mock_result.lastrowid = 1
        mock_db.execute.return_value = mock_result

        mgr.save_recipient({})

        args, _ = mock_db.execute.call_args
        assert args[1][0] == "Unknown"

    def test_save_recipient_db_error(self, fresh_manager):
        """A database exception produces None return value."""
        mgr, mock_db = fresh_manager
        mock_db.execute.side_effect = Exception("insert failed")

        result = mgr.save_recipient({"name": "Test"})

        assert result is None


# ===========================================================================
# TestUpdateRecipient
# ===========================================================================

class TestUpdateRecipient:
    """Tests for update_recipient."""

    def test_update_recipient_with_explicit_name(self, fresh_manager):
        """An explicit name is forwarded to the UPDATE statement."""
        mgr, mock_db = fresh_manager
        mock_db.execute.return_value = MagicMock()

        result = mgr.update_recipient(1, {"name": "Dr. Updated", "recipient_type": "gp_backreferral"})

        assert result is True
        args, _ = mock_db.execute.call_args
        assert args[1][0] == "Dr. Updated"

    def test_update_recipient_builds_name_from_parts(self, fresh_manager):
        """When name is absent, title + first + last are composed."""
        mgr, mock_db = fresh_manager
        mock_db.execute.return_value = MagicMock()

        result = mgr.update_recipient(
            2, {"title": "Prof.", "first_name": "Tim", "last_name": "Jones"}
        )

        assert result is True
        args, _ = mock_db.execute.call_args
        assert args[1][0] == "Prof. Tim Jones"

    def test_update_recipient_success_returns_true(self, fresh_manager):
        """A successful execute returns True (from the decorator)."""
        mgr, mock_db = fresh_manager
        mock_db.execute.return_value = MagicMock()

        result = mgr.update_recipient(3, {"name": "Valid Name"})

        assert result is True

    def test_update_recipient_db_error_returns_false(self, fresh_manager):
        """A database exception causes the @handle_errors decorator to return False."""
        mgr, mock_db = fresh_manager
        mock_db.execute.side_effect = Exception("update failed")

        result = mgr.update_recipient(1, {"name": "X"})

        assert result is False


# ===========================================================================
# TestDeleteRecipient
# ===========================================================================

class TestDeleteRecipient:
    """Tests for delete_recipient."""

    def test_delete_recipient_success(self, fresh_manager):
        """A successful delete returns True."""
        mgr, mock_db = fresh_manager
        mock_db.execute.return_value = MagicMock()

        result = mgr.delete_recipient(5)

        assert result is True
        args, _ = mock_db.execute.call_args
        assert args[1] == (5,)

    def test_delete_recipient_db_error_returns_false(self, fresh_manager):
        """An exception inside delete is caught by @handle_errors and returns False."""
        mgr, mock_db = fresh_manager
        mock_db.execute.side_effect = Exception("delete failed")

        result = mgr.delete_recipient(5)

        assert result is False


# ===========================================================================
# TestIncrementUsage
# ===========================================================================

class TestIncrementUsage:
    """Tests for increment_usage."""

    def test_increment_usage_executes_sql(self, fresh_manager):
        """increment_usage calls db_manager.execute with the recipient id."""
        mgr, mock_db = fresh_manager
        mock_db.execute.return_value = MagicMock()

        mgr.increment_usage(7)

        mock_db.execute.assert_called_once()
        args, _ = mock_db.execute.call_args
        assert args[1] == (7,)

    def test_increment_usage_returns_true(self, fresh_manager):
        """Returns True on success."""
        mgr, mock_db = fresh_manager
        mock_db.execute.return_value = MagicMock()

        result = mgr.increment_usage(7)

        assert result is True


# ===========================================================================
# TestToggleFavorite
# ===========================================================================

class TestToggleFavorite:
    """Tests for toggle_favorite."""

    def test_toggle_favorite_executes_sql(self, fresh_manager):
        """toggle_favorite calls db_manager.execute with the recipient id."""
        mgr, mock_db = fresh_manager
        mock_db.execute.return_value = MagicMock()

        mgr.toggle_favorite(3)

        mock_db.execute.assert_called_once()
        args, _ = mock_db.execute.call_args
        assert args[1] == (3,)

    def test_toggle_favorite_returns_true(self, fresh_manager):
        """Returns True on success."""
        mgr, mock_db = fresh_manager
        mock_db.execute.return_value = MagicMock()

        result = mgr.toggle_favorite(3)

        assert result is True


# ===========================================================================
# TestGetRecentRecipients
# ===========================================================================

class TestGetRecentRecipients:
    """Tests for get_recent_recipients."""

    def test_get_recent_recipients_default_limit(self, fresh_manager):
        """Default limit of 5 is passed to the SQL query."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.return_value = [_make_row_25()]

        result = mgr.get_recent_recipients()

        assert len(result) == 1
        args, _ = mock_db.fetchall.call_args
        assert args[1] == (5,)

    def test_get_recent_recipients_custom_limit(self, fresh_manager):
        """A custom limit is forwarded correctly."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.return_value = []

        mgr.get_recent_recipients(limit=10)

        args, _ = mock_db.fetchall.call_args
        assert args[1] == (10,)

    def test_get_recent_recipients_empty(self, fresh_manager):
        """None from fetchall returns an empty list."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.return_value = None

        result = mgr.get_recent_recipients()

        assert result == []


# ===========================================================================
# TestGetFrequentRecipients
# ===========================================================================

class TestGetFrequentRecipients:
    """Tests for get_frequent_recipients."""

    def test_get_frequent_recipients_returns_results(self, fresh_manager):
        """Rows returned by fetchall are converted and returned."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.return_value = [_make_row_25(), _make_row_25()]

        result = mgr.get_frequent_recipients()

        assert len(result) == 2

    def test_get_frequent_recipients_empty(self, fresh_manager):
        """Empty result set returns empty list."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.return_value = []

        result = mgr.get_frequent_recipients()

        assert result == []


# ===========================================================================
# TestGetFavorites
# ===========================================================================

class TestGetFavorites:
    """Tests for get_favorites."""

    def test_get_favorites_returns_favorites(self, fresh_manager):
        """Rows are converted and returned."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.return_value = [_make_row_25()]

        result = mgr.get_favorites()

        assert len(result) == 1
        assert result[0]["is_favorite"] is True

    def test_get_favorites_db_error(self, fresh_manager):
        """Exception is swallowed and empty list returned."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.side_effect = Exception("db error")

        result = mgr.get_favorites()

        assert result == []


# ===========================================================================
# TestSearchRecipients
# ===========================================================================

class TestSearchRecipients:
    """Tests for search_recipients (FTS with LIKE fallback)."""

    def test_search_recipients_fts_success(self, fresh_manager):
        """FTS succeeds: converted rows are returned."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.return_value = [_make_row_25()]

        result = mgr.search_recipients("cardio")

        assert len(result) == 1
        # First call is the FTS attempt; it should contain the query
        args, _ = mock_db.fetchall.call_args
        assert args[1] == ("cardio",)

    def test_search_recipients_fts_fallback_on_error(self, fresh_manager):
        """When FTS raises, the LIKE fallback is tried."""
        mgr, mock_db = fresh_manager
        # First call (FTS) raises; second call (LIKE) succeeds
        mock_db.fetchall.side_effect = [
            Exception("no FTS table"),
            [_make_row_25()],
        ]

        result = mgr.search_recipients("smith")

        assert len(result) == 1
        # Second call passes 6 LIKE params
        second_args, _ = mock_db.fetchall.call_args_list[1]
        assert len(second_args[1]) == 6

    def test_search_recipients_fallback_error_returns_empty(self, fresh_manager):
        """Both FTS and LIKE fail: empty list is returned."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.side_effect = Exception("total failure")

        result = mgr.search_recipients("x")

        assert result == []

    def test_search_recipients_fts_empty_results(self, fresh_manager):
        """FTS returning empty list gives back empty list."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.return_value = []

        result = mgr.search_recipients("nobody")

        assert result == []


# ===========================================================================
# TestGetBySpecialty
# ===========================================================================

class TestGetBySpecialty:
    """Tests for get_recipients_by_specialty."""

    def test_get_recipients_by_specialty(self, fresh_manager):
        """Rows matching the specialty are returned."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.return_value = [_make_row_25()]

        result = mgr.get_recipients_by_specialty("Cardiology")

        assert len(result) == 1
        args, _ = mock_db.fetchall.call_args
        assert args[1] == ("Cardiology",)

    def test_get_recipients_by_specialty_error(self, fresh_manager):
        """Exception yields empty list."""
        mgr, mock_db = fresh_manager
        mock_db.fetchall.side_effect = Exception("error")

        result = mgr.get_recipients_by_specialty("X")

        assert result == []


# ===========================================================================
# TestImportFromCsv
# ===========================================================================

class TestImportFromCsv:
    """Tests for import_from_csv."""

    def _write_csv(self, path, rows, headers=None):
        default_headers = [
            "Last Name", "First Name", "Middle Name", "Payee Number",
            "Practitioner Number", "Title", "Specialty", "Phone Number",
            "Fax Number", "Office Name", "Office Address", "City",
            "Province", "Postal Code", "Email",
        ]
        fieldnames = headers or default_headers
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def test_import_from_csv_success(self, fresh_manager, tmp_path):
        """A valid CSV with one row imports one contact."""
        mgr, mock_db = fresh_manager
        # _check_duplicate returns False (no duplicate)
        mock_db.fetchone.return_value = None
        # save_recipient calls db.execute; give it a lastrowid
        mock_result = MagicMock()
        mock_result.lastrowid = 1
        mock_db.execute.return_value = mock_result

        csv_file = tmp_path / "contacts.csv"
        self._write_csv(str(csv_file), [{
            "Last Name": "Jones", "First Name": "Bill", "Middle Name": "",
            "Payee Number": "", "Practitioner Number": "", "Title": "Dr.",
            "Specialty": "Neurology", "Phone Number": "555-0001",
            "Fax Number": "555-0002", "Office Name": "Brain Clinic",
            "Office Address": "1 Brain St", "City": "Edmonton",
            "Province": "AB", "Postal Code": "T5A 0A1", "Email": "",
        }])

        imported, skipped, errors = mgr.import_from_csv(str(csv_file))

        assert imported == 1
        assert skipped == 0
        assert errors == []

    def test_import_from_csv_skips_duplicates(self, fresh_manager, tmp_path):
        """When _check_duplicate returns True the row is skipped."""
        mgr, mock_db = fresh_manager
        # fetchone returns a row → duplicate found
        mock_db.fetchone.return_value = (1,)

        csv_file = tmp_path / "dupes.csv"
        self._write_csv(str(csv_file), [{
            "Last Name": "Smith", "First Name": "John", "Middle Name": "",
            "Payee Number": "", "Practitioner Number": "", "Title": "",
            "Specialty": "Cardiology", "Phone Number": "", "Fax Number": "",
            "Office Name": "", "Office Address": "", "City": "",
            "Province": "", "Postal Code": "", "Email": "",
        }])

        imported, skipped, errors = mgr.import_from_csv(str(csv_file))

        assert imported == 0
        assert skipped == 1
        assert errors == []

    def test_import_from_csv_file_not_found(self, fresh_manager):
        """A missing file adds a 'File not found' error and returns zeros."""
        mgr, mock_db = fresh_manager

        imported, skipped, errors = mgr.import_from_csv("/nonexistent/path/file.csv")

        assert imported == 0
        assert skipped == 0
        assert len(errors) == 1
        assert "File not found" in errors[0]

    def test_import_from_csv_save_failure(self, fresh_manager, tmp_path):
        """When save_recipient returns None an error message is recorded."""
        mgr, mock_db = fresh_manager
        mock_db.fetchone.return_value = None  # no duplicate
        mock_db.execute.return_value = None   # save returns None → no lastrowid

        csv_file = tmp_path / "fail.csv"
        self._write_csv(str(csv_file), [{
            "Last Name": "Brown", "First Name": "Alice", "Middle Name": "",
            "Payee Number": "", "Practitioner Number": "", "Title": "",
            "Specialty": "GP", "Phone Number": "", "Fax Number": "",
            "Office Name": "", "Office Address": "", "City": "",
            "Province": "", "Postal Code": "", "Email": "",
        }])

        imported, skipped, errors = mgr.import_from_csv(str(csv_file))

        assert imported == 0
        assert len(errors) == 1
        assert "Failed to save" in errors[0]

    def test_import_from_csv_row_parse_error(self, fresh_manager, tmp_path):
        """An exception thrown during row parsing is recorded as an error."""
        mgr, mock_db = fresh_manager

        csv_file = tmp_path / "bad.csv"
        # Write a CSV with one data row; then patch _parse_csv_row to raise
        self._write_csv(str(csv_file), [{
            "Last Name": "X", "First Name": "Y", "Middle Name": "",
            "Payee Number": "", "Practitioner Number": "", "Title": "",
            "Specialty": "", "Phone Number": "", "Fax Number": "",
            "Office Name": "", "Office Address": "", "City": "",
            "Province": "", "Postal Code": "", "Email": "",
        }])

        with patch.object(mgr, "_parse_csv_row", side_effect=ValueError("bad row")):
            imported, skipped, errors = mgr.import_from_csv(str(csv_file))

        assert imported == 0
        assert len(errors) == 1
        assert "bad row" in errors[0]


# ===========================================================================
# TestParseCsvRow
# ===========================================================================

class TestParseCsvRow:
    """Tests for _parse_csv_row."""

    def test_parse_csv_row_all_fields(self, fresh_manager):
        """All known CSV columns are mapped correctly."""
        mgr, _ = fresh_manager
        row = {
            "Last Name": "Doe", "First Name": "Jane", "Middle Name": "M",
            "Payee Number": "P001", "Practitioner Number": "PR001",
            "Title": "Dr.", "Specialty": "Oncology",
            "Phone Number": "780-111-2222", "Fax Number": "780-111-3333",
            "Office Name": "Cancer Care", "Office Address": "5 Elm St",
            "City": "Edmonton", "Province": "AB", "Postal Code": "T6G 2E1",
            "Email": "jane@example.com",
        }

        result = mgr._parse_csv_row(row)

        assert result["last_name"] == "Doe"
        assert result["first_name"] == "Jane"
        assert result["middle_name"] == "M"
        assert result["payee_number"] == "P001"
        assert result["practitioner_number"] == "PR001"
        assert result["title"] == "Dr."
        assert result["specialty"] == "Oncology"
        assert result["phone"] == "780-111-2222"
        assert result["fax"] == "780-111-3333"
        assert result["facility"] == "Cancer Care"
        assert result["email"] == "jane@example.com"

    def test_parse_csv_row_builds_address_from_parts(self, fresh_manager):
        """address is built by joining office_address, city, province, postal_code."""
        mgr, _ = fresh_manager
        row = {
            "Office Address": "10 Oak Ave", "City": "Calgary",
            "Province": "AB", "Postal Code": "T2P 1J9",
        }

        result = mgr._parse_csv_row(row)

        assert result["address"] == "10 Oak Ave, Calgary, AB, T2P 1J9"

    def test_parse_csv_row_empty_address_is_none(self, fresh_manager):
        """When all address parts are empty, address is None."""
        mgr, _ = fresh_manager
        row = {}  # all keys absent → empty strings → no parts

        result = mgr._parse_csv_row(row)

        assert result["address"] is None

    def test_parse_csv_row_defaults_recipient_type(self, fresh_manager):
        """recipient_type is always 'specialist' for CSV imports."""
        mgr, _ = fresh_manager

        result = mgr._parse_csv_row({})

        assert result["recipient_type"] == "specialist"


# ===========================================================================
# TestCheckDuplicate
# ===========================================================================

class TestCheckDuplicate:
    """Tests for _check_duplicate."""

    def test_check_duplicate_found(self, fresh_manager):
        """fetchone returning a row means duplicate."""
        mgr, mock_db = fresh_manager
        mock_db.fetchone.return_value = (5,)

        assert mgr._check_duplicate("John", "Smith", "Cardiology") is True

    def test_check_duplicate_not_found(self, fresh_manager):
        """fetchone returning None means no duplicate."""
        mgr, mock_db = fresh_manager
        mock_db.fetchone.return_value = None

        assert mgr._check_duplicate("Jane", "Brown", "GP") is False

    def test_check_duplicate_db_error(self, fresh_manager):
        """DB exception is caught and False is returned (safe default)."""
        mgr, mock_db = fresh_manager
        mock_db.fetchone.side_effect = Exception("oops")

        assert mgr._check_duplicate("A", "B", "C") is False


# ===========================================================================
# TestPreviewCsv
# ===========================================================================

class TestPreviewCsv:
    """Tests for preview_csv."""

    def test_preview_csv_returns_rows_and_count(self, tmp_path, fresh_manager):
        """Returns (preview_rows, total_count, column_names)."""
        mgr, _ = fresh_manager
        csv_file = tmp_path / "preview.csv"
        fieldnames = ["Last Name", "First Name", "Specialty"]
        with open(str(csv_file), "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for i in range(7):
                writer.writerow({"Last Name": f"Name{i}", "First Name": "X", "Specialty": "GP"})

        preview_rows, total_count, columns = mgr.preview_csv(str(csv_file), limit=5)

        assert total_count == 7
        assert len(preview_rows) == 5  # capped at limit
        assert "Last Name" in columns

    def test_preview_csv_error_returns_empty(self, fresh_manager):
        """A missing file returns empty preview, zero count, empty columns."""
        mgr, _ = fresh_manager

        preview_rows, total_count, columns = mgr.preview_csv("/no/such/file.csv")

        assert preview_rows == []
        assert total_count == 0
        assert columns == []


# ===========================================================================
# TestGetFormattedAddress
# ===========================================================================

class TestGetFormattedAddress:
    """Tests for get_formatted_address."""

    def test_get_formatted_address_all_parts(self, fresh_manager):
        """All four address components are joined with ', '."""
        mgr, _ = fresh_manager
        recipient = {
            "office_address": "99 King St",
            "city": "Ottawa",
            "province": "ON",
            "postal_code": "K1A 0A9",
        }

        result = mgr.get_formatted_address(recipient)

        assert result == "99 King St, Ottawa, ON, K1A 0A9"

    def test_get_formatted_address_partial_parts(self, fresh_manager):
        """Missing parts are omitted from the joined string."""
        mgr, _ = fresh_manager
        recipient = {"city": "Victoria", "province": "BC"}

        result = mgr.get_formatted_address(recipient)

        assert result == "Victoria, BC"

    def test_get_formatted_address_falls_back_to_address(self, fresh_manager):
        """When no office_address/city/province/postal_code, address field is used."""
        mgr, _ = fresh_manager
        recipient = {"address": "100 Legacy Ave, Toronto, ON"}

        result = mgr.get_formatted_address(recipient)

        assert result == "100 Legacy Ave, Toronto, ON"


# ===========================================================================
# TestRowToDict
# ===========================================================================

class TestRowToDict:
    """Tests for _row_to_dict."""

    def test_row_to_dict_15_columns(self, fresh_manager):
        """A 15-column (old schema) row is mapped to the base 15 keys."""
        mgr, _ = fresh_manager
        row = _make_row_15()

        result = mgr._row_to_dict(row)

        assert result["id"] == 1
        assert result["name"] == "Dr. Smith"
        assert result["recipient_type"] == "specialist"
        assert result["specialty"] == "Cardiology"
        assert result["facility"] == "Heart Clinic"
        assert result["address"] == "123 Main St"
        assert result["fax"] == "555-1111"
        assert result["phone"] == "555-2222"
        assert result["email"] == "smith@example.com"
        assert result["notes"] == "Some notes"
        assert result["last_used"] == "2024-01-01"
        assert result["use_count"] == 5
        assert result["is_favorite"] is True
        assert result["created_at"] == "2023-01-01"
        assert result["updated_at"] == "2024-01-01"
        # New-schema keys must NOT be present
        assert "first_name" not in result

    def test_row_to_dict_25_columns(self, fresh_manager):
        """A 25-column (new schema) row includes all extended fields."""
        mgr, _ = fresh_manager
        row = _make_row_25()

        result = mgr._row_to_dict(row)

        # Core fields
        assert result["id"] == 1
        assert result["name"] == "Dr. Smith"
        # Extended fields
        assert result["first_name"] == "John"
        assert result["last_name"] == "Smith"
        assert result["middle_name"] == "A"
        assert result["title"] == "Dr."
        assert result["payee_number"] == "PAY001"
        assert result["practitioner_number"] == "PRAC001"
        assert result["office_address"] == "100 Office Rd"
        assert result["city"] == "Calgary"
        assert result["province"] == "AB"
        assert result["postal_code"] == "T1X 1X1"

    def test_row_to_dict_empty_row(self, fresh_manager):
        """None / falsy row returns an empty dict."""
        mgr, _ = fresh_manager

        assert mgr._row_to_dict(None) == {}
        assert mgr._row_to_dict(()) == {}
        assert mgr._row_to_dict([]) == {}
