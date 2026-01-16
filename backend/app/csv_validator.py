"""
CSV validation utilities for checking row completeness and extracting data.

This module provides a CSVRowValidator class to validate CSV rows and extract
transaction data such as dates, amounts, and descriptions.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional


class CSVRowValidator:
    """
    Validates CSV rows based on the file's header structure.
    
    The validator is initialized with the CSV headers to optimize validation
    by knowing which columns contain date, amount, and description data.
    """

    def __init__(self, headers: List[str]):
        """
        Initialize the validator with CSV headers.
        
        Args:
            headers: List of column names from the CSV header row
        """
        # Store original headers as-is (csv.DictReader uses original names)
        self.headers = headers
        # Also create normalized versions for lookup
        self.normalized_headers = [h.strip() if h else "" for h in headers]
        
        # Find date column(s) - use original headers
        self.date_columns = [
            i for i, header in enumerate(self.headers)
            if header and "date" in header.lower()
        ]
        
        # Find amount column(s) - use original headers
        self.amount_columns = [
            i for i, header in enumerate(self.headers)
            if header and any(
                token in header.lower()
                for token in ["amount", "debit", "credit", "value", "charge"]
            )
        ]
        
        # Find description column(s) - any column that's not date or amount
        self.description_columns = [
            i for i, header in enumerate(self.headers)
            if header
            and "date" not in header.lower()
            and not any(
                token in header.lower()
                for token in ["amount", "debit", "credit", "value", "charge"]
            )
        ]

    def extract_transaction_date(self, row_data: Dict[str, str]) -> Optional[datetime]:
        """
        Extract a transaction date from the row data.
        
        Args:
            row_data: Dictionary of column name to value
            
        Returns:
            Parsed datetime object or None if no valid date found
        """
        if not row_data:
            return None

        date_formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%m-%d-%Y",
            "%d-%m-%Y",
            "%m/%d/%y",  # 2-digit year: 1/1/22
            "%d/%m/%y",  # 2-digit year: 1/1/22 (European format)
            "%m-%d-%y",  # 2-digit year: 1-1-22
            "%d-%m-%y",  # 2-digit year: 1-1-22 (European format)
        ]

        # Try date columns first (optimized)
        for col_idx in self.date_columns:
            if col_idx < len(self.headers):
                key = self.headers[col_idx]  # Use original header name
                value = row_data.get(key)
                if not value:
                    continue
                    
                candidate = str(value).strip()
                if not candidate:
                    continue

                # Remove ordinal suffixes like '1st', '2nd'
                candidate = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", candidate)

                for fmt in date_formats:
                    try:
                        return datetime.strptime(candidate, fmt)
                    except ValueError:
                        continue

                # Try ISO formats
                try:
                    return datetime.fromisoformat(candidate)
                except ValueError:
                    pass

        # Fallback: search all columns with "date" in the name
        for key, value in row_data.items():
            if "date" not in key.lower():
                continue

            candidate = str(value).strip()
            if not candidate:
                continue

            candidate = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", candidate)

            for fmt in date_formats:
                try:
                    return datetime.strptime(candidate, fmt)
                except ValueError:
                    continue

            try:
                return datetime.fromisoformat(candidate)
            except ValueError:
                pass

        return None

    def extract_amount(self, row_data: Dict[str, str]) -> Optional[float]:
        """
        Extract a transaction amount from the row data.
        
        Args:
            row_data: Dictionary of column name to value
            
        Returns:
            Parsed amount as float or None if no valid amount found
        """
        if not row_data:
            return None

        # Try amount columns first (optimized)
        for col_idx in self.amount_columns:
            if col_idx < len(self.headers):
                key = self.headers[col_idx]  # Use original header name
                raw_value = row_data.get(key)
                if raw_value in (None, ""):
                    continue

                amount = self._parse_amount_value(str(raw_value).strip(), key)
                if amount is not None:
                    return amount

        # Fallback: search all columns with amount-related keywords
        candidate_keys = [
            key
            for key in row_data.keys()
            if any(
                token in key.lower()
                for token in ["amount", "debit", "credit", "value", "charge"]
            )
        ]

        search_keys = candidate_keys if candidate_keys else row_data.keys()

        for key in search_keys:
            raw_value = row_data.get(key)
            if raw_value in (None, ""):
                continue

            amount = self._parse_amount_value(str(raw_value).strip(), key)
            if amount is not None:
                return amount

        return None

    def _parse_amount_value(self, value_str: str, key: str) -> Optional[float]:
        """
        Parse a single amount value string.
        
        Args:
            value_str: The amount string to parse
            key: The column name (for context)
            
        Returns:
            Parsed amount or None if invalid
        """
        if not value_str:
            return None

        is_negative = False
        if value_str.startswith("(") and value_str.endswith(")"):
            is_negative = True
            value_str = value_str[1:-1]

        value_str = (
            value_str.replace(",", "")
            .replace("$", "")
            .replace("£", "")
            .replace("€", "")
        )
        value_str = re.sub(r"[^0-9\.-]", "", value_str)

        if value_str in ("", "-", ".", "-."):
            return None

        try:
            amount = float(value_str)
            if is_negative:
                amount = -abs(amount)
            # Treat credit columns as negative (money coming in) unless explicitly marked
            key_lower = key.lower()
            if "credit" in key_lower and "debit" not in key_lower:
                amount = -abs(amount)
            if "debit" in key_lower and amount < 0:
                amount = abs(amount)
            return amount
        except ValueError:
            return None

    def has_description(self, row_data: Dict[str, str]) -> bool:
        """
        Check if the row has a valid description field.
        
        Args:
            row_data: Dictionary of column name to value
            
        Returns:
            True if at least one description field has a non-empty value
        """
        # Try description columns first (optimized)
        for col_idx in self.description_columns:
            if col_idx < len(self.headers):
                key = self.headers[col_idx]  # Use original header name
                value = row_data.get(key)
                value_str = str(value).strip() if value else ""
                if value_str and len(value_str) > 0:
                    return True

        # Fallback: search all non-date, non-amount columns
        for key, value in row_data.items():
            key_lower = key.lower()
            value_str = str(value).strip() if value else ""

            # Skip date and amount fields
            if "date" in key_lower:
                continue
            if any(
                token in key_lower
                for token in ["amount", "debit", "credit", "value", "charge"]
            ):
                continue

            # If we have a non-empty text field, consider it a description
            if value_str and len(value_str) > 0:
                return True

        return False

    def is_row_valid(self, row_data: Dict[str, str]) -> bool:
        """
        Check if a CSV row has all required fields populated.
        
        A row is considered valid if it has:
        - A valid date
        - A valid amount
        - A description (non-empty text field that's not date/amount)
        
        Args:
            row_data: Dictionary of column name to value
            
        Returns:
            True if the row is valid, False otherwise
        """
        if not row_data:
            return False

        # Check for date
        date = self.extract_transaction_date(row_data)
        if date is None:
            # Debug: log which date fields were found
            date_keys = [k for k in row_data.keys() if "date" in k.lower()]
            if date_keys:
                print(f"DEBUG: Date extraction failed. Date keys: {date_keys}, values: {[row_data.get(k) for k in date_keys]}")
            return False

        # Check for amount
        amount = self.extract_amount(row_data)
        if amount is None:
            # Debug: log which amount fields were found
            amount_keys = [k for k in row_data.keys() if any(token in k.lower() for token in ["amount", "debit", "credit", "value", "charge"])]
            if amount_keys:
                print(f"DEBUG: Amount extraction failed. Amount keys: {amount_keys}, values: {[row_data.get(k) for k in amount_keys]}")
            return False

        # Check for description
        if not self.has_description(row_data):
            # Debug: log available fields
            desc_keys = [k for k in row_data.keys() if "date" not in k.lower() and not any(token in k.lower() for token in ["amount", "debit", "credit", "value", "charge"])]
            print(f"DEBUG: Description check failed. Available desc keys: {desc_keys}, values: {[row_data.get(k) for k in desc_keys]}")
            return False

        return True


# Backward compatibility functions for existing code
def extract_transaction_date(row_data: Dict[str, str]) -> Optional[datetime]:
    """Legacy function - creates a temporary validator."""
    validator = CSVRowValidator(list(row_data.keys()) if row_data else [])
    return validator.extract_transaction_date(row_data)


def extract_amount(row_data: Dict[str, str]) -> Optional[float]:
    """Legacy function - creates a temporary validator."""
    validator = CSVRowValidator(list(row_data.keys()) if row_data else [])
    return validator.extract_amount(row_data)


def is_row_complete(row_data: Dict[str, str]) -> bool:
    """Legacy function - creates a temporary validator."""
    validator = CSVRowValidator(list(row_data.keys()) if row_data else [])
    return validator.is_row_valid(row_data)
