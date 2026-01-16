"""
Tests for CSV validator functionality.

These tests are based on real CSV file formats found in the budget directory.
"""

import pytest
from datetime import datetime
from app.csv_validator import CSVRowValidator


class TestCSVRowValidator:
    """Test cases for CSVRowValidator class."""

    def test_chase_format_headers(self):
        """Test validator initialization with Chase CSV format."""
        headers = [
            "Transaction Date",
            "Post Date",
            "Description",
            "Category",
            "Type",
            "Amount",
            "Memo",
        ]
        validator = CSVRowValidator(headers)

        assert len(validator.date_columns) == 2  # Transaction Date, Post Date
        assert len(validator.amount_columns) == 1  # Amount
        assert len(validator.description_columns) == 4  # Description, Category, Type, Memo

    def test_usaa_checking_format_headers(self):
        """Test validator initialization with USAA checking format."""
        headers = [
            "Date",
            "Description",
            "Original Description",
            "Category",
            "Amount",
            "Status",
        ]
        validator = CSVRowValidator(headers)

        assert len(validator.date_columns) == 1  # Date
        assert len(validator.amount_columns) == 1  # Amount
        assert len(validator.description_columns) == 4  # Description, Original Description, Category, Status

    def test_chase_valid_row(self):
        """Test validation of a valid Chase CSV row."""
        headers = [
            "Transaction Date",
            "Post Date",
            "Description",
            "Category",
            "Type",
            "Amount",
            "Memo",
        ]
        validator = CSVRowValidator(headers)

        row = {
            "Transaction Date": "12/30/2024",
            "Post Date": "12/31/2024",
            "Description": "RESTAURANTE ILIOS",
            "Category": "Food & Drink",
            "Type": "Sale",
            "Amount": "-36.87",
            "Memo": "",
        }

        assert validator.is_row_valid(row) is True
        assert validator.extract_transaction_date(row) is not None
        assert validator.extract_amount(row) == -36.87
        assert validator.has_description(row) is True

    def test_usaa_checking_valid_row(self):
        """Test validation of a valid USAA checking row."""
        headers = [
            "Date",
            "Description",
            "Original Description",
            "Category",
            "Amount",
            "Status",
        ]
        validator = CSVRowValidator(headers)

        row = {
            "Date": "2024-12-31",
            "Description": "PennyMac",
            "Original Description": "PENNYMAC         ONLINE PMT ***********8POS",
            "Category": "Mortgage & Rent",
            "Amount": "-3884.19",
            "Status": "Posted",
        }

        assert validator.is_row_valid(row) is True
        assert validator.extract_transaction_date(row) is not None
        assert validator.extract_amount(row) == -3884.19
        assert validator.has_description(row) is True

    def test_usaa_cc_valid_row(self):
        """Test validation of a valid USAA credit card row."""
        headers = [
            "Date",
            "Description",
            "Original Description",
            "Category",
            "Amount",
            "Status",
        ]
        validator = CSVRowValidator(headers)

        row = {
            "Date": "2024-12-22",
            "Description": "Credit Card Payment",
            "Original Description": "0108892468               AUTOPAYLANG*!01",
            "Category": "Credit Card Payment",
            "Amount": "-641.78",
            "Status": "Posted",
        }

        assert validator.is_row_valid(row) is True
        assert validator.extract_amount(row) == -641.78

    def test_row_missing_date(self):
        """Test that row without valid date is rejected."""
        headers = ["Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        row = {
            "Date": "",  # Empty date
            "Description": "Test transaction",
            "Amount": "100.00",
        }

        assert validator.is_row_valid(row) is False
        assert validator.extract_transaction_date(row) is None

    def test_row_missing_amount(self):
        """Test that row without valid amount is rejected."""
        headers = ["Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        row = {
            "Date": "2024-12-31",
            "Description": "Test transaction",
            "Amount": "",  # Empty amount
        }

        assert validator.is_row_valid(row) is False
        assert validator.extract_amount(row) is None

    def test_row_missing_description(self):
        """Test that row without description is rejected."""
        headers = ["Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        row = {
            "Date": "2024-12-31",
            "Description": "",  # Empty description
            "Amount": "100.00",
        }

        assert validator.is_row_valid(row) is False
        assert validator.has_description(row) is False

    def test_date_formats(self):
        """Test various date formats are recognized."""
        headers = ["Transaction Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        date_formats = [
            ("2024-12-31", "%Y-%m-%d"),
            ("12/31/2024", "%m/%d/%Y"),
            ("31/12/2024", "%d/%m/%Y"),
            ("12-31-2024", "%m-%d-%Y"),
        ]

        for date_str, expected_format in date_formats:
            row = {
                "Transaction Date": date_str,
                "Description": "Test",
                "Amount": "100.00",
            }
            date = validator.extract_transaction_date(row)
            assert date is not None, f"Failed to parse date: {date_str}"

    def test_amount_formats(self):
        """Test various amount formats are recognized."""
        headers = ["Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        test_cases = [
            ("100.00", 100.00),
            ("-100.00", -100.00),
            ("1,000.00", 1000.00),
            ("$100.00", 100.00),
            ("(100.00)", -100.00),  # Parentheses notation
            ("€100.00", 100.00),
            ("£100.00", 100.00),
        ]

        for amount_str, expected in test_cases:
            row = {
                "Date": "2024-12-31",
                "Description": "Test",
                "Amount": amount_str,
            }
            amount = validator.extract_amount(row)
            assert amount == expected, f"Failed to parse amount: {amount_str}, got {amount}"

    def test_credit_debit_columns(self):
        """Test that credit/debit columns are handled correctly."""
        headers = ["Date", "Description", "Debit", "Credit"]
        validator = CSVRowValidator(headers)

        # Debit should be positive
        row_debit = {
            "Date": "2024-12-31",
            "Description": "Test",
            "Debit": "100.00",
            "Credit": "",
        }
        assert validator.extract_amount(row_debit) == 100.00

        # Credit should be negative
        row_credit = {
            "Date": "2024-12-31",
            "Description": "Test",
            "Debit": "",
            "Credit": "100.00",
        }
        assert validator.extract_amount(row_credit) == -100.00

    def test_empty_row(self):
        """Test that empty row is rejected."""
        headers = ["Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        row = {}
        assert validator.is_row_valid(row) is False

    def test_row_with_all_empty_fields(self):
        """Test that row with all empty fields is rejected."""
        headers = ["Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        row = {
            "Date": "",
            "Description": "",
            "Amount": "",
        }
        assert validator.is_row_valid(row) is False

    def test_row_with_partial_data(self):
        """Test that row with only some fields is rejected."""
        headers = ["Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        # Has date and description but no amount
        row = {
            "Date": "2024-12-31",
            "Description": "Test",
            "Amount": "",
        }
        assert validator.is_row_valid(row) is False

        # Has date and amount but no description
        row = {
            "Date": "2024-12-31",
            "Description": "",
            "Amount": "100.00",
        }
        assert validator.is_row_valid(row) is False

    def test_transferwise_format(self):
        """Test validation with TransferWise/Wise CSV format."""
        headers = [
            "TransferWise ID",
            "Date",
            "Amount",
            "Currency",
            "Description",
            "Payment Reference",
            "Running Balance",
        ]
        validator = CSVRowValidator(headers)

        row = {
            "TransferWise ID": "TRANSFER-1319977971",
            "Date": "02-12-2024",
            "Amount": "1000.00",
            "Currency": "USD",
            "Description": "Received money from USAA CHK-INTRNT",
            "Payment Reference": "TRANSFER",
            "Running Balance": "2059.14",
        }

        assert validator.is_row_valid(row) is True
        assert validator.extract_amount(row) == 1000.00
        assert validator.has_description(row) is True

    def test_negative_amounts(self):
        """Test that negative amounts are handled correctly."""
        headers = ["Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        row = {
            "Date": "2024-12-31",
            "Description": "Expense",
            "Amount": "-152.34",
        }

        amount = validator.extract_amount(row)
        assert amount == -152.34
        assert validator.is_row_valid(row) is True

    def test_positive_amounts(self):
        """Test that positive amounts are handled correctly."""
        headers = ["Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        row = {
            "Date": "2024-12-31",
            "Description": "Income",
            "Amount": "3699.50",
        }

        amount = validator.extract_amount(row)
        assert amount == 3699.50
        assert validator.is_row_valid(row) is True

    def test_description_in_different_columns(self):
        """Test that description can be in different columns."""
        headers = ["Date", "Description", "Original Description", "Amount"]
        validator = CSVRowValidator(headers)

        # Description in "Description" column
        row1 = {
            "Date": "2024-12-31",
            "Description": "Test Description",
            "Original Description": "",
            "Amount": "100.00",
        }
        assert validator.has_description(row1) is True

        # Description in "Original Description" column
        row2 = {
            "Date": "2024-12-31",
            "Description": "",
            "Original Description": "Original Test Description",
            "Amount": "100.00",
        }
        assert validator.has_description(row2) is True

    def test_multiple_date_columns(self):
        """Test that validator uses first valid date column."""
        headers = ["Transaction Date", "Post Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        row = {
            "Transaction Date": "12/30/2024",
            "Post Date": "12/31/2024",
            "Description": "Test",
            "Amount": "100.00",
        }

        date = validator.extract_transaction_date(row)
        assert date is not None
        # Should use Transaction Date (first date column)
        assert date.month == 12
        assert date.day == 30
        assert date.year == 2024

    def test_invalid_date_format(self):
        """Test that invalid date formats are rejected."""
        headers = ["Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        row = {
            "Date": "Invalid Date",
            "Description": "Test",
            "Amount": "100.00",
        }

        assert validator.extract_transaction_date(row) is None
        assert validator.is_row_valid(row) is False

    def test_invalid_amount_format(self):
        """Test that invalid amount formats are rejected."""
        headers = ["Date", "Description", "Amount"]
        validator = CSVRowValidator(headers)

        row = {
            "Date": "2024-12-31",
            "Description": "Test",
            "Amount": "Not a number",
        }

        assert validator.extract_amount(row) is None
        assert validator.is_row_valid(row) is False

