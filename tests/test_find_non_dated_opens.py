import pytest
from click.testing import CliRunner
from src.main import cli, is_opening_position, is_non_dated_account, find_non_dated_opening_transactions
from src.classes import Posting, AccountName, Amount, Commodity, Journal, JournalEntry, Transaction, SourceLocation
from pathlib import Path
from decimal import Decimal
from datetime import date
from parsita import ParseError # Import ParseError

def test_is_opening_position():
    """Tests the is_opening_position function."""
    # Test case 1: Assets account with positive quantity
    posting1 = Posting(account=AccountName(parts=["assets", "stock"]), amount=Amount(quantity=Decimal("10"), commodity=Commodity(name="AAPL")))
    assert is_opening_position(posting1) is True

    # Test case 2: Assets account with negative quantity (sell)
    posting2 = Posting(account=AccountName(parts=["assets", "stock"]), amount=Amount(quantity=Decimal("-5"), commodity=Commodity(name="AAPL")))
    assert is_opening_position(posting2) is False

    # Test case 3: Expenses account with positive quantity
    posting3 = Posting(account=AccountName(parts=["expenses", "food"]), amount=Amount(quantity=Decimal("50"), commodity=Commodity(name="USD")))
    assert is_opening_position(posting3) is False

    # Test case 4: Assets account with no amount
    posting4 = Posting(account=AccountName(parts=["assets", "cash"]), amount=None)
    assert is_opening_position(posting4) is False

def test_is_non_dated_account():
    """Tests the is_non_dated_account function."""
    # Test case 1: Non-dated account
    account_name1 = "assets:broker:stock:AAPL"
    assert is_non_dated_account(account_name1) is True

    # Test case 2: Dated account (YYYYMMDD)
    account_name2 = "assets:broker:stock:GOOG:20230110"
    assert is_non_dated_account(account_name2) is False

    # Test case 3: Account with similar but not matching suffix
    account_name3 = "assets:broker:stock:MSFT:2023-01-10"
    assert is_non_dated_account(account_name3) is True

    # Test case 4: Non-assets account
    account_name4 = "expenses:food"
    assert is_non_dated_account(account_name4) is True

def test_find_non_dated_opening_transactions():
    """Tests the find_non_dated_opening_transactions function."""
    # Create mock Journal and JournalEntry objects
    # Transaction 1: Non-dated opening position (should be found)
    posting1_1 = Posting(account=AccountName(parts=["assets", "broker", "stock", "AAPL"]), amount=Amount(quantity=Decimal("10"), commodity=Commodity(name="AAPL")))
    posting1_2 = Posting(account=AccountName(parts=["assets", "cash"]), amount=Amount(quantity=Decimal("-1000"), commodity=Commodity(name="USD")))
    transaction1 = Transaction(date=date(2023, 1, 5), payee="Buy Stock", postings=[posting1_1, posting1_2], source_location=SourceLocation(filename=Path("test.journal"), offset=5, length=10))
    entry1 = JournalEntry(transaction=transaction1)

    # Transaction 2: Dated opening position (should not be found)
    posting2_1 = Posting(account=AccountName(parts=["assets", "broker", "stock", "GOOG", "20230110"]), amount=Amount(quantity=Decimal("5"), commodity=Commodity(name="GOOG")))
    posting2_2 = Posting(account=AccountName(parts=["assets", "cash"]), amount=Amount(quantity=Decimal("-500"), commodity=Commodity(name="USD")))
    transaction2 = Transaction(date=date(2023, 1, 10), payee="Buy Stock Dated", postings=[posting2_1, posting2_2], source_location=SourceLocation(filename=Path("test.journal"), offset=12, length=10))
    entry2 = JournalEntry(transaction=transaction2)

    # Transaction 3: Non-dated opening position (should be found)
    posting3_1 = Posting(account=AccountName(parts=["assets", "broker", "crypto", "BTC"]), amount=Amount(quantity=Decimal("0.5"), commodity=Commodity(name="BTC")))
    posting3_2 = Posting(account=AccountName(parts=["assets", "cash"]), amount=Amount(quantity=Decimal("-200"), commodity=Commodity(name="USD")))
    transaction3 = Transaction(date=date(2023, 1, 15), payee="Another Non-Dated Buy", postings=[posting3_1, posting3_2], source_location=SourceLocation(filename=Path("test.journal"), offset=19, length=10))
    entry3 = JournalEntry(transaction=transaction3)

    # Transaction 4: Expense transaction (should not be found)
    posting4_1 = Posting(account=AccountName(parts=["expenses", "food"]), amount=Amount(quantity=Decimal("50"), commodity=Commodity(name="USD")))
    posting4_2 = Posting(account=AccountName(parts=["assets", "cash"]), amount=Amount(quantity=Decimal("-50"), commodity=Commodity(name="USD")))
    transaction4 = Transaction(date=date(2023, 1, 20), payee="Expense Transaction", postings=[posting4_1, posting4_2], source_location=SourceLocation(filename=Path("test.journal"), offset=26, length=10))
    entry4 = JournalEntry(transaction=transaction4)

    # Transaction 5: Sell transaction (should not be found)
    posting5_1 = Posting(account=AccountName(parts=["assets", "broker", "stock", "GOOG", "20230110"]), amount=Amount(quantity=Decimal("-5"), commodity=Commodity(name="GOOG")))
    posting5_2 = Posting(account=AccountName(parts=["assets", "cash"]), amount=Amount(quantity=Decimal("600"), commodity=Commodity(name="USD")))
    transaction5 = Transaction(date=date(2023, 1, 25), payee="Sell Stock Dated", postings=[posting5_1, posting5_2], source_location=SourceLocation(filename=Path("test.journal"), offset=33, length=10))
    entry5 = JournalEntry(transaction=transaction5)

    # Journal with all entries
    journal = Journal(entries=[entry1, entry2, entry3, entry4, entry5])

    # Find non-dated opening transactions
    found_transactions = find_non_dated_opening_transactions(journal)

    # Assert that the correct transactions were found
    assert len(found_transactions) == 2
    assert transaction1 in found_transactions
    assert transaction3 in found_transactions
    assert transaction2 not in found_transactions
    assert transaction4 not in found_transactions
    assert transaction5 not in found_transactions


def test_find_non_dated_opens(tmp_path):
    """Tests the find-non-dated-opens command with a journal file."""
    journal_content = """
2023/01/01 Opening Balance
    assets:cash                 1000 USD
    equity:opening-balances

2023/01/05 Buy Stock
    assets:broker:stock:AAPL     10 AAPL
    assets:cash               -1000 USD

2023/01/10 Buy Stock Dated
    assets:broker:stock:GOOG:20230110     5 GOOG
    assets:cash                       -500 USD

2023/01/15 Another Non-Dated Buy
    assets:broker:crypto:BTC     0.5 BTC
    assets:cash                 -200 USD

2023/01/20 Expense Transaction
    expenses:food                 50 USD
    assets:cash                  -50 USD

2023/01/25 Sell Stock Dated
    assets:broker:stock:GOOG:20230110    -5 GOOG
    assets:cash                       +600 USD
    income:capital-gains
"""
    journal_file = tmp_path / "test_journal.journal"
    journal_file.write_text(journal_content)

    runner = CliRunner()
    result = runner.invoke(cli, ["find-non-dated-opens", str(journal_file)])

    assert result.exit_code == 0
    assert "Transactions opening positions with non-dated subaccounts:" in result.stdout
    assert "2023-01-05 Buy Stock (Line 6)" in result.stdout
    assert "2023-01-15 Another Non-Dated Buy (Line 14)" in result.stdout
    assert "2023-01-10 Buy Stock Dated" not in result.stdout # Ensure dated accounts are not included
    assert "2023-01-20 Expense Transaction" not in result.stdout # Ensure non-asset transactions are not included
    assert "2023-01-25 Sell Stock Dated" not in result.stdout # Ensure sell transactions are not included

def test_find_non_dated_opens_no_matches(tmp_path):
    """Tests the find-non-dated-opens command with no matching transactions."""
    journal_content = """
2023/01/01 Opening Balance
    assets:cash                 1000 USD
    equity:opening-balances

2023/01/10 Buy Stock Dated
    assets:broker:stock:GOOG:20230110     5 GOOG
    assets:cash                       -500 USD

2023/01/20 Expense Transaction
    expenses:food                 50 USD
    assets:cash                  -50 USD

2023/01/25 Sell Stock Dated
    assets:broker:stock:GOOG:20230110    -5 GOOG
    assets:cash                       +600 USD
    income:capital-gains
"""
    journal_file = tmp_path / "test_journal_no_matches.journal"
    journal_file.write_text(journal_content)

    runner = CliRunner()
    result = runner.invoke(cli, ["find-non-dated-opens", str(journal_file)])

    assert result.exit_code == 0
    assert "No transactions found opening positions with non-dated subaccounts." in result.stdout
    assert "Transactions opening positions with non-dated subaccounts:" not in result.stdout # Ensure the header is not printed

def test_find_non_dated_opens_parse_error(tmp_path):
    """Tests the find-non-dated-opens command with a journal file containing a parse error."""
    journal_content = """
2023/01/01 Opening Balance
    assets:cash                 1000 USD
    equity:opening-balances

Invalid Transaction
    assets:broker:stock:AAPL     10 AAPL
    assets:cash               -1000 USD
"""
    journal_file = tmp_path / "test_journal_parse_error.journal"
    journal_file.write_text(journal_content)

    runner = CliRunner()
    result = runner.invoke(cli, ["find-non-dated-opens", str(journal_file)])

    assert result.exit_code != 0 # Expect a non-zero exit code for errors
    assert "Error parsing journal file:" in result.stdout
    assert "ParseError" in result.stdout # Ensure ParseError is mentioned in the output
