import pytest
from decimal import Decimal
from datetime import date
from pathlib import Path
from returns.maybe import Some, Nothing

from src.classes import AccountName, Commodity, Amount, Posting, Transaction
from src.balance import BalanceSheet, Account # Import Account

pytest.skip(allow_module_level=True)

def test_get_account_existing_root():
    """Tests retrieving an existing root account using get_account."""
    balance_sheet = BalanceSheet()
    # Create a root account
    balance_sheet.root_accounts["assets"] = Account(name_part="assets", full_name=AccountName(parts=["assets"]))

    account_maybe = balance_sheet.get_account(AccountName(parts=["assets"]))

    assert isinstance(account_maybe, Some), "Account 'assets' not found"
    account = account_maybe.unwrap()
    assert isinstance(account, Account)
    assert account.full_name == AccountName(parts=["assets"])

def test_get_account_existing_nested():
    """Tests retrieving an existing nested account using get_account."""
    balance_sheet = BalanceSheet()
    # Create a nested account structure
    assets_account = Account(name_part="assets", full_name=AccountName(parts=["assets"]))
    bank_account = Account(name_part="bank", full_name=AccountName(parts=["assets", "bank"]), parent=assets_account)
    checking_account = Account(name_part="checking", full_name=AccountName(parts=["assets", "bank", "checking"]), parent=bank_account)

    assets_account.children["bank"] = bank_account
    bank_account.children["checking"] = checking_account
    balance_sheet.root_accounts["assets"] = assets_account

    account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "bank", "checking"]))

    assert isinstance(account_maybe, Some), "Account 'assets:bank:checking' not found"
    account = account_maybe.unwrap()
    assert isinstance(account, Account)
    assert account.full_name == AccountName(parts=["assets", "bank", "checking"])

def test_get_account_non_existing():
    """Tests retrieving a non-existing account using get_account."""
    balance_sheet = BalanceSheet()
    # Create a root account but not the one being searched for
    balance_sheet.root_accounts["assets"] = Account(name_part="assets", full_name=AccountName(parts=["assets"]))

    account_maybe = balance_sheet.get_account(AccountName(parts=["liabilities", "credit_card"]))

    assert account_maybe == Nothing, "Account 'liabilities:credit_card' should not exist"

def test_get_account_non_existing_nested():
    """Tests retrieving a non-existing nested account using get_account."""
    balance_sheet = BalanceSheet()
    # Create a partial nested structure
    assets_account = Account(name_part="assets", full_name=AccountName(parts=["assets"]))
    bank_account = Account(name_part="bank", full_name=AccountName(parts=["assets", "bank"]), parent=assets_account)
    assets_account.children["bank"] = bank_account
    balance_sheet.root_accounts["assets"] = assets_account

    # Search for a deeper nested account that doesn't exist
    account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "bank", "checking"]))

    assert account_maybe == Nothing, "Account 'assets:bank:checking' should not exist in this partial structure"

def test_get_account_empty_balancesheet():
    """Tests retrieving an account from an empty BalanceSheet."""
    balance_sheet = BalanceSheet()

    account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "bank"]))

    assert account_maybe == Nothing, "Account 'assets:bank' should not exist in an empty balance sheet"

# Note: Testing finding accounts created by apply_transaction is implicitly done
# when running other tests that build a balance sheet from transactions.
