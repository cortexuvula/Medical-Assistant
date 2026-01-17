"""
Recipient Manager Module

Manages saved recipients for referral letters, providing CRUD operations,
CSV import functionality, and quick access to frequently used recipients.
"""

import csv
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from utils.structured_logging import get_logger

from database.db_pool import get_db_manager
from utils.error_handling import handle_errors, ErrorSeverity


logger = get_logger(__name__)


# Column definitions for queries (extended with new fields from migration 10)
RECIPIENT_COLUMNS = """id, name, recipient_type, specialty, facility, address,
    fax, phone, email, notes, last_used, use_count, is_favorite,
    created_at, updated_at, first_name, last_name, middle_name, title,
    payee_number, practitioner_number, office_address, city, province, postal_code"""


class RecipientManager:
    """Singleton manager for saved referral recipients."""

    _instance = None

    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(RecipientManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the recipient manager."""
        if self._initialized:
            return

        self.db_manager = get_db_manager()
        self._initialized = True
        logger.info("RecipientManager initialized")

    def get_all_recipients(self, recipient_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all saved recipients, optionally filtered by type.

        Args:
            recipient_type: Optional filter by recipient type (specialist, gp_backreferral, hospital, diagnostic)

        Returns:
            List of recipient dictionaries
        """
        try:
            if recipient_type:
                rows = self.db_manager.fetchall(
                    f"""SELECT {RECIPIENT_COLUMNS}
                       FROM saved_recipients
                       WHERE recipient_type = ?
                       ORDER BY is_favorite DESC, use_count DESC, last_used DESC NULLS LAST""",
                    (recipient_type,)
                )
            else:
                rows = self.db_manager.fetchall(
                    f"""SELECT {RECIPIENT_COLUMNS}
                       FROM saved_recipients
                       ORDER BY is_favorite DESC, use_count DESC, last_used DESC NULLS LAST"""
                )

            return [self._row_to_dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error fetching recipients: {e}")
            return []

    def get_recipient(self, recipient_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific recipient by ID.

        Args:
            recipient_id: The recipient ID

        Returns:
            Recipient dictionary or None if not found
        """
        try:
            row = self.db_manager.fetchone(
                f"""SELECT {RECIPIENT_COLUMNS}
                   FROM saved_recipients WHERE id = ?""",
                (recipient_id,)
            )
            return self._row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching recipient {recipient_id}: {e}")
            return None

    def save_recipient(self, recipient: Dict[str, Any]) -> Optional[int]:
        """Save a new recipient.

        Args:
            recipient: Dictionary with recipient details

        Returns:
            The new recipient ID, or None on failure
        """
        try:
            # Compute name from first/last if not provided
            name = recipient.get("name", "")
            if not name:
                parts = []
                if recipient.get("title"):
                    parts.append(recipient["title"])
                if recipient.get("first_name"):
                    parts.append(recipient["first_name"])
                if recipient.get("last_name"):
                    parts.append(recipient["last_name"])
                name = " ".join(parts) if parts else "Unknown"

            result = self.db_manager.execute(
                """INSERT INTO saved_recipients
                   (name, recipient_type, specialty, facility, address, fax, phone, email, notes,
                    first_name, last_name, middle_name, title, payee_number, practitioner_number,
                    office_address, city, province, postal_code)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    recipient.get("recipient_type", "specialist"),
                    recipient.get("specialty"),
                    recipient.get("facility"),
                    recipient.get("address"),
                    recipient.get("fax"),
                    recipient.get("phone"),
                    recipient.get("email"),
                    recipient.get("notes"),
                    recipient.get("first_name"),
                    recipient.get("last_name"),
                    recipient.get("middle_name"),
                    recipient.get("title"),
                    recipient.get("payee_number"),
                    recipient.get("practitioner_number"),
                    recipient.get("office_address"),
                    recipient.get("city"),
                    recipient.get("province"),
                    recipient.get("postal_code")
                )
            )
            logger.info(f"Saved new recipient: {name}")
            return result.lastrowid if result else None
        except Exception as e:
            logger.error(f"Error saving recipient: {e}")
            return None

    @handle_errors(ErrorSeverity.ERROR, error_message="Error updating recipient", return_type="bool")
    def update_recipient(self, recipient_id: int, recipient: Dict[str, Any]) -> bool:
        """Update an existing recipient.

        Args:
            recipient_id: The recipient ID to update
            recipient: Dictionary with updated details

        Returns:
            True if successful, False otherwise
        """
        # Compute name from first/last if not provided
        name = recipient.get("name", "")
        if not name:
            parts = []
            if recipient.get("title"):
                parts.append(recipient["title"])
            if recipient.get("first_name"):
                parts.append(recipient["first_name"])
            if recipient.get("last_name"):
                parts.append(recipient["last_name"])
            name = " ".join(parts) if parts else "Unknown"

        self.db_manager.execute(
            """UPDATE saved_recipients
               SET name = ?, recipient_type = ?, specialty = ?, facility = ?,
                   address = ?, fax = ?, phone = ?, email = ?, notes = ?,
                   first_name = ?, last_name = ?, middle_name = ?, title = ?,
                   payee_number = ?, practitioner_number = ?, office_address = ?,
                   city = ?, province = ?, postal_code = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                name,
                recipient.get("recipient_type", "specialist"),
                recipient.get("specialty"),
                recipient.get("facility"),
                recipient.get("address"),
                recipient.get("fax"),
                recipient.get("phone"),
                recipient.get("email"),
                recipient.get("notes"),
                recipient.get("first_name"),
                recipient.get("last_name"),
                recipient.get("middle_name"),
                recipient.get("title"),
                recipient.get("payee_number"),
                recipient.get("practitioner_number"),
                recipient.get("office_address"),
                recipient.get("city"),
                recipient.get("province"),
                recipient.get("postal_code"),
                recipient_id
            )
        )
        logger.info(f"Updated recipient {recipient_id}")
        return True

    @handle_errors(ErrorSeverity.ERROR, error_message="Error deleting recipient", return_type="bool")
    def delete_recipient(self, recipient_id: int) -> bool:
        """Delete a recipient.

        Args:
            recipient_id: The recipient ID to delete

        Returns:
            True if successful, False otherwise
        """
        self.db_manager.execute(
            "DELETE FROM saved_recipients WHERE id = ?",
            (recipient_id,)
        )
        logger.info(f"Deleted recipient {recipient_id}")
        return True

    @handle_errors(ErrorSeverity.WARNING, error_message="Error incrementing recipient usage", return_type="bool")
    def increment_usage(self, recipient_id: int) -> bool:
        """Increment the usage count and update last_used timestamp.

        Args:
            recipient_id: The recipient ID

        Returns:
            True if successful, False otherwise
        """
        self.db_manager.execute(
            """UPDATE saved_recipients
               SET use_count = use_count + 1,
                   last_used = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (recipient_id,)
        )
        return True

    @handle_errors(ErrorSeverity.WARNING, error_message="Error toggling recipient favorite", return_type="bool")
    def toggle_favorite(self, recipient_id: int) -> bool:
        """Toggle the favorite status of a recipient.

        Args:
            recipient_id: The recipient ID

        Returns:
            True if successful, False otherwise
        """
        self.db_manager.execute(
            """UPDATE saved_recipients
               SET is_favorite = NOT is_favorite,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (recipient_id,)
        )
        return True

    def get_recent_recipients(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the most recently used recipients.

        Args:
            limit: Maximum number of recipients to return

        Returns:
            List of recipient dictionaries
        """
        try:
            rows = self.db_manager.fetchall(
                f"""SELECT {RECIPIENT_COLUMNS}
                   FROM saved_recipients
                   WHERE last_used IS NOT NULL
                   ORDER BY last_used DESC
                   LIMIT ?""",
                (limit,)
            )
            return [self._row_to_dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error fetching recent recipients: {e}")
            return []

    def get_frequent_recipients(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the most frequently used recipients.

        Args:
            limit: Maximum number of recipients to return

        Returns:
            List of recipient dictionaries
        """
        try:
            rows = self.db_manager.fetchall(
                f"""SELECT {RECIPIENT_COLUMNS}
                   FROM saved_recipients
                   WHERE use_count > 0
                   ORDER BY use_count DESC
                   LIMIT ?""",
                (limit,)
            )
            return [self._row_to_dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error fetching frequent recipients: {e}")
            return []

    def get_favorites(self) -> List[Dict[str, Any]]:
        """Get all favorite recipients.

        Returns:
            List of favorite recipient dictionaries
        """
        try:
            rows = self.db_manager.fetchall(
                f"""SELECT {RECIPIENT_COLUMNS}
                   FROM saved_recipients
                   WHERE is_favorite = TRUE
                   ORDER BY name"""
            )
            return [self._row_to_dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error fetching favorites: {e}")
            return []

    def search_recipients(self, query: str) -> List[Dict[str, Any]]:
        """Search recipients by name, specialty, or facility using full-text search.

        Args:
            query: Search query string

        Returns:
            List of matching recipient dictionaries
        """
        try:
            # Use FTS for search
            rows = self.db_manager.fetchall(
                f"""SELECT sr.{RECIPIENT_COLUMNS.replace('id,', 'sr.id,').replace(', ', ', sr.')}
                   FROM saved_recipients sr
                   JOIN saved_recipients_fts fts ON sr.id = fts.rowid
                   WHERE saved_recipients_fts MATCH ?
                   ORDER BY sr.is_favorite DESC, sr.use_count DESC""",
                (query,)
            )
            return [self._row_to_dict(row) for row in rows] if rows else []
        except Exception as e:
            # Fall back to LIKE search if FTS fails
            logger.warning(f"FTS search failed, falling back to LIKE: {e}")
            try:
                like_query = f"%{query}%"
                rows = self.db_manager.fetchall(
                    f"""SELECT {RECIPIENT_COLUMNS}
                       FROM saved_recipients
                       WHERE name LIKE ? OR specialty LIKE ? OR facility LIKE ?
                             OR first_name LIKE ? OR last_name LIKE ? OR city LIKE ?
                       ORDER BY is_favorite DESC, use_count DESC""",
                    (like_query, like_query, like_query, like_query, like_query, like_query)
                )
                return [self._row_to_dict(row) for row in rows] if rows else []
            except Exception as e2:
                logger.error(f"Error searching recipients: {e2}")
                return []

    def get_recipients_by_specialty(self, specialty: str) -> List[Dict[str, Any]]:
        """Get all recipients with a specific specialty.

        Args:
            specialty: The specialty to filter by

        Returns:
            List of recipient dictionaries
        """
        try:
            rows = self.db_manager.fetchall(
                f"""SELECT {RECIPIENT_COLUMNS}
                   FROM saved_recipients
                   WHERE specialty = ?
                   ORDER BY is_favorite DESC, use_count DESC""",
                (specialty,)
            )
            return [self._row_to_dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error fetching recipients by specialty {specialty}: {e}")
            return []

    # =========================================================================
    # CSV Import Methods
    # =========================================================================

    def import_from_csv(self, file_path: str) -> Tuple[int, int, List[str]]:
        """Import contacts from a CSV file.

        CSV should have columns: Last Name, First Name, Middle Name, Payee Number,
        Practitioner Number, Title, Specialty, Phone Number, Fax Number,
        Office Name, Office Address, City, Province, Postal Code, Email

        Args:
            file_path: Path to the CSV file

        Returns:
            Tuple of (imported_count, skipped_count, error_messages)
        """
        imported = 0
        skipped = 0
        errors = []

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)

                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                    try:
                        recipient = self._parse_csv_row(row)

                        # Check for duplicate
                        if self._check_duplicate(
                            recipient.get("first_name", ""),
                            recipient.get("last_name", ""),
                            recipient.get("specialty", "")
                        ):
                            skipped += 1
                            continue

                        # Save the recipient
                        result = self.save_recipient(recipient)
                        if result:
                            imported += 1
                        else:
                            errors.append(f"Row {row_num}: Failed to save contact")

                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")

            logger.info(f"CSV import complete: {imported} imported, {skipped} skipped, {len(errors)} errors")

        except FileNotFoundError:
            errors.append(f"File not found: {file_path}")
        except Exception as e:
            errors.append(f"Error reading CSV file: {str(e)}")
            logger.error(f"CSV import error: {e}")

        return imported, skipped, errors

    def _parse_csv_row(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Convert a CSV row to a recipient dictionary.

        Args:
            row: CSV row dictionary from DictReader

        Returns:
            Recipient dictionary ready for saving
        """
        # Map CSV columns to database fields
        recipient = {
            "last_name": row.get("Last Name", "").strip(),
            "first_name": row.get("First Name", "").strip(),
            "middle_name": row.get("Middle Name", "").strip(),
            "payee_number": row.get("Payee Number", "").strip(),
            "practitioner_number": row.get("Practitioner Number", "").strip(),
            "title": row.get("Title", "").strip(),
            "specialty": row.get("Specialty", "").strip(),
            "phone": row.get("Phone Number", "").strip(),
            "fax": row.get("Fax Number", "").strip(),
            "facility": row.get("Office Name", "").strip(),
            "office_address": row.get("Office Address", "").strip(),
            "city": row.get("City", "").strip(),
            "province": row.get("Province", "").strip(),
            "postal_code": row.get("Postal Code", "").strip(),
            "email": row.get("Email", "").strip(),
            "recipient_type": "specialist",  # Default all imports to specialist
        }

        # Build full address from components
        address_parts = []
        if recipient["office_address"]:
            address_parts.append(recipient["office_address"])
        if recipient["city"]:
            address_parts.append(recipient["city"])
        if recipient["province"]:
            address_parts.append(recipient["province"])
        if recipient["postal_code"]:
            address_parts.append(recipient["postal_code"])
        recipient["address"] = ", ".join(address_parts) if address_parts else None

        # Name is computed in save_recipient from first/last/title

        return recipient

    def _check_duplicate(self, first_name: str, last_name: str, specialty: str) -> bool:
        """Check if a contact with the same name and specialty already exists.

        Args:
            first_name: First name to check
            last_name: Last name to check
            specialty: Specialty to check

        Returns:
            True if duplicate exists, False otherwise
        """
        try:
            row = self.db_manager.fetchone(
                """SELECT id FROM saved_recipients
                   WHERE first_name = ? AND last_name = ? AND specialty = ?""",
                (first_name, last_name, specialty)
            )
            return row is not None
        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return False

    def preview_csv(self, file_path: str, limit: int = 5) -> Tuple[List[Dict[str, str]], int, List[str]]:
        """Preview the contents of a CSV file before importing.

        Args:
            file_path: Path to the CSV file
            limit: Maximum rows to preview

        Returns:
            Tuple of (preview_rows, total_count, column_names)
        """
        preview_rows = []
        total_count = 0
        columns = []

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames or []

                for row in reader:
                    total_count += 1
                    if len(preview_rows) < limit:
                        preview_rows.append(row)

        except Exception as e:
            logger.error(f"Error previewing CSV: {e}")

        return preview_rows, total_count, columns

    def get_formatted_address(self, recipient: Dict[str, Any]) -> str:
        """Get a formatted address string from recipient details.

        Args:
            recipient: Recipient dictionary

        Returns:
            Formatted address string
        """
        parts = []
        if recipient.get("office_address"):
            parts.append(recipient["office_address"])
        if recipient.get("city"):
            parts.append(recipient["city"])
        if recipient.get("province"):
            parts.append(recipient["province"])
        if recipient.get("postal_code"):
            parts.append(recipient["postal_code"])
        return ", ".join(parts) if parts else recipient.get("address", "")

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert a database row to a dictionary.

        Args:
            row: Database row tuple

        Returns:
            Dictionary with recipient data
        """
        if not row:
            return {}

        # Handle both old (15 columns) and new (25 columns) schema
        result = {
            "id": row[0],
            "name": row[1],
            "recipient_type": row[2],
            "specialty": row[3],
            "facility": row[4],
            "address": row[5],
            "fax": row[6],
            "phone": row[7],
            "email": row[8],
            "notes": row[9],
            "last_used": row[10],
            "use_count": row[11],
            "is_favorite": bool(row[12]) if row[12] is not None else False,
            "created_at": row[13],
            "updated_at": row[14]
        }

        # Add new fields if present (after migration 10)
        if len(row) > 15:
            result.update({
                "first_name": row[15],
                "last_name": row[16],
                "middle_name": row[17],
                "title": row[18],
                "payee_number": row[19],
                "practitioner_number": row[20],
                "office_address": row[21],
                "city": row[22],
                "province": row[23],
                "postal_code": row[24] if len(row) > 24 else None
            })

        return result


# Singleton instance
_recipient_manager: Optional[RecipientManager] = None


def get_recipient_manager() -> RecipientManager:
    """Get the singleton RecipientManager instance.

    Returns:
        The RecipientManager singleton
    """
    global _recipient_manager
    if _recipient_manager is None:
        _recipient_manager = RecipientManager()
    return _recipient_manager


# Convenience alias
recipient_manager = get_recipient_manager()
