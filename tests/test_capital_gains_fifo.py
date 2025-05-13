import pytest
# from datetime import date # Not needed if using journal strings
from decimal import Decimal
from pathlib import Path
from returns.maybe import Some, Nothing
from returns.result import Success, Failure # Import Success and Failure
# import re # Not needed

from src.classes import (
    Journal,
    Transaction,
    Posting,
    AccountName,
    Amount,
    Commodity,
    SourceLocation,
    JournalEntry,
    CostKind,
    Cost,
    CapitalGainResult # Import CapitalGainResult
)

from src.balance import BalanceSheet, Lot, Account, Balance, CashBalance, AssetBalance # Updated import

# Moved and adapted tests from test_capital_gains_fifo.py

def test_calculate_balances_and_lots_simple_capital_gain():
    journal_string = """
2023-01-01 * Open AAPL Lot 1
    assets:stocks:AAPL:20230101  10 AAPL @@ 1500 USD
    equity:opening-balances     -10 AAPL
    assets:cash                -1500 USD

2023-01-15 * Sell AAPL
    assets:stocks:AAPL          -5 AAPL
    assets:cash                 1000 USD
    income:capital-gains        -100 USD ; This posting is ignored by the calculation logic now
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Verify the remaining quantity of the lot
    aapl_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230101"]))
    assert isinstance(aapl_account_maybe, Some), "AAPL lot 1 account not found"
    aapl_account = aapl_account_maybe.unwrap()
    aapl_balance = aapl_account.get_own_balance(Commodity("AAPL"))
    assert isinstance(aapl_balance, AssetBalance)
    assert len(aapl_balance.lots) == 1
    assert aapl_balance.lots[0].remaining_quantity == Decimal("5") # 10 initial - 5 sold


def test_calculate_balances_and_lots_multiple_opens_single_close():
    journal_string = """
2023-01-01 * Open AAPL Lot 1
    assets:stocks:AAPL:20230101  10 AAPL @@ 1500 USD
    equity:opening-balances     -10 AAPL
    assets:cash                -1500 USD

2023-01-05 * Open AAPL Lot 2
    assets:stocks:AAPL:20230105  15 AAPL @@ 2500 USD
    equity:opening-balances     -15 AAPL
    assets:cash                -2500 USD

2023-01-20 * Sell AAPL
    assets:stocks:AAPL          -12 AAPL
    assets:cash                 2000 USD
    income:capital-gains        -200 USD ; Ignored
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Verify the remaining quantity of the lots
    aapl_account_lot1_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230101"]))
    assert isinstance(aapl_account_lot1_maybe, Some), "AAPL lot 1 account not found"
    aapl_account_lot1 = aapl_account_lot1_maybe.unwrap()
    aapl_balance_lot1 = aapl_account_lot1.get_own_balance(Commodity("AAPL"))
    assert isinstance(aapl_balance_lot1, AssetBalance)
    assert len(aapl_balance_lot1.lots) == 1
    assert aapl_balance_lot1.lots[0].remaining_quantity == Decimal("0") # 10 initial - 10 matched

    aapl_account_lot2_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230105"]))
    assert isinstance(aapl_account_lot2_maybe, Some), "AAPL lot 2 account not found"
    aapl_account_lot2 = aapl_account_lot2_maybe.unwrap()
    aapl_balance_lot2 = aapl_account_lot2.get_own_balance(Commodity("AAPL"))
    assert isinstance(aapl_balance_lot2, AssetBalance)
    assert len(aapl_balance_lot2.lots) == 1
    assert aapl_balance_lot2.lots[0].remaining_quantity == Decimal("13") # 15 initial - 2 matched


def test_calculate_balances_and_lots_single_open_multiple_closes():
    journal_string = """
2023-01-01 * Open AAPL Lot 1
    assets:stocks:AAPL:20230101  20 AAPL @@ 3000 USD
    equity:opening-balances     -20 AAPL
    assets:cash                -3000 USD

2023-01-15 * Sell AAPL Part 1
    assets:stocks:AAPL          -5 AAPL
    assets:cash                 1000 USD
    income:capital-gains        -100 USD ; Ignored

2023-01-20 * Sell AAPL Part 2
    assets:stocks:AAPL          -8 AAPL
    assets:cash                 1500 USD
    income:capital-gains        -150 USD ; Ignored
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Verify the remaining quantity of the lot
    aapl_account_lot1_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230101"]))
    assert isinstance(aapl_account_lot1_maybe, Some), "AAPL lot 1 account not found"
    aapl_account_lot1 = aapl_account_lot1_maybe.unwrap()
    aapl_balance_lot1 = aapl_account_lot1.get_own_balance(Commodity("AAPL"))
    assert isinstance(aapl_balance_lot1, AssetBalance)
    assert len(aapl_balance_lot1.lots) == 1
    assert aapl_balance_lot1.lots[0].remaining_quantity == Decimal("7") # 20 initial - 5 sold - 8 sold


def test_calculate_balances_and_lots_multiple_assets():
    journal_string = """
2023-01-01 * Open AAPL
    assets:stocks:AAPL:20230101  10 AAPL @@ 1500 USD
    equity:opening-balances     -10 AAPL
    assets:cash                -1500 USD

2023-01-02 * Open MSFT
    assets:stocks:MSFT:20230102  15 MSFT @@ 2500 USD
    equity:opening-balances     -15 MSFT
    assets:cash                -2500 USD

2023-01-15 * Sell AAPL
    assets:stocks:AAPL          -5 AAPL
    assets:cash                 1000 USD
    income:capital-gains        -100 USD ; Ignored

2023-01-20 * Sell MSFT
    assets:stocks:MSFT          -8 MSFT
    assets:cash                 1500 USD
    income:capital-gains        -150 USD ; Ignored
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Verify remaining quantities
    aapl_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230101"]))
    assert isinstance(aapl_account_maybe, Some), "AAPL account not found"
    aapl_account = aapl_account_maybe.unwrap()
    aapl_balance = aapl_account.get_own_balance(Commodity("AAPL"))
    assert isinstance(aapl_balance, AssetBalance)
    assert len(aapl_balance.lots) == 1
    assert aapl_balance.lots[0].remaining_quantity == Decimal("5") # 10 initial - 5 sold

    msft_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "MSFT", "20230102"]))
    assert isinstance(msft_account_maybe, Some), "MSFT account not found"
    msft_account = msft_account_maybe.unwrap()
    msft_balance = msft_account.get_own_balance(Commodity("MSFT"))
    assert isinstance(msft_balance, AssetBalance)
    assert len(msft_balance.lots) == 1
    assert msft_balance.lots[0].remaining_quantity == Decimal("7") # 15 initial - 8 sold


def test_calculate_balances_and_lots_excludes_non_asset_closing_postings():
    journal_string = """
2023-01-01 * Open AAPL Lot 1
    assets:stocks:AAPL:20230101  10 AAPL @@ 1500 USD
    equity:opening-balances     -10 AAPL
    assets:cash                -1500 USD

2023-01-15 * Withdraw USD
    assets:cash:USD          -100 USD
    expenses:withdrawal       100 USD
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Verify remaining quantity of the lot (should be unchanged)
    aapl_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230101"]))
    assert isinstance(aapl_account_maybe, Some), "AAPL account not found"
    aapl_account = aapl_account_maybe.unwrap()
    aapl_balance = aapl_account.get_own_balance(Commodity("AAPL"))
    assert isinstance(aapl_balance, AssetBalance)
    assert len(aapl_balance.lots) == 1
    assert aapl_balance.lots[0].remaining_quantity == Decimal("10") # 10 initial - 0 sold


def test_calculate_balances_and_lots_handles_undated_open_accounts():
    journal_string = """
2023-01-01 * Open BTC Lot 1
    assets:crypto:BTC:20230101  1 BTC @@ 30000 USD
    equity:opening-balances     -1 BTC
    assets:cash                -30000 USD

2023-01-15 * Sell BTC
    assets:crypto:BTC          -0.5 BTC
    assets:cash                 20000 USD
    income:capital-gains        -5000 USD ; Ignored
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Verify the remaining quantity of the lot
    btc_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "crypto", "BTC", "20230101"]))
    assert isinstance(btc_account_maybe, Some), "BTC account not found"
    btc_account = btc_account_maybe.unwrap()
    btc_balance = btc_account.get_own_balance(Commodity("BTC"))
    assert isinstance(btc_balance, AssetBalance)
    assert len(btc_balance.lots) == 1
    assert btc_balance.lots[0].remaining_quantity == Decimal("0.5") # 1 initial - 0.5 sold


def test_calculate_balances_and_lots_partial_match_gain():
    journal_string = """
2023-01-01 * Open XYZ Lot 1
    assets:stocks:XYZ:20230101  10 XYZ @@ 1000 USD
    equity:opening-balances     -10 XYZ
    assets:cash                -1000 USD

2023-01-15 * Sell XYZ Partial
    assets:stocks:XYZ          -4 XYZ
    assets:cash                 600 USD
    income:capital-gains        -200 USD ; Ignored
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Verify the remaining quantity of the lot
    xyz_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "XYZ", "20230101"]))
    assert isinstance(xyz_account_maybe, Some), "XYZ account not found"
    xyz_account = xyz_account_maybe.unwrap()
    xyz_balance = xyz_account.get_own_balance(Commodity("XYZ"))
    assert isinstance(xyz_balance, AssetBalance)
    assert len(xyz_balance.lots) == 1
    assert xyz_balance.lots[0].remaining_quantity == Decimal("6") # 10 initial - 4 sold


def test_calculate_balances_and_lots_multiple_postings_same_commodity():
    journal_string = """
2023-01-01 * Open XYZ Lot 1
    assets:stocks:XYZ:20230101  10 XYZ @@ 1000 USD
    equity:opening-balances     -10 XYZ
    assets:cash                -1000 USD

2023-01-15 * Sell XYZ and Receive Funds
    assets:stocks:XYZ          -5 XYZ
    assets:cash                 800 USD
    income:dividends:XYZ        50 USD
    income:capital-gains       -350 USD ; Ignored
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Verify the remaining quantity of the lot
    xyz_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "XYZ", "20230101"]))
    assert isinstance(xyz_account_maybe, Some), "XYZ account not found"
    xyz_account = xyz_account_maybe.unwrap()
    xyz_balance = xyz_account.get_own_balance(Commodity("XYZ"))
    assert isinstance(xyz_balance, AssetBalance)
    assert len(xyz_balance.lots) == 1
    assert xyz_balance.lots[0].remaining_quantity == Decimal("5") # 10 initial - 5 sold


def test_calculate_balances_and_lots_multiple_cash_postings():
    journal_string = """
2023-01-01 * Open XYZ Lot 1
    assets:stocks:XYZ:20230101  10 XYZ @@ 1000 USD
    equity:opening-balances     -10 XYZ
    assets:cash                -1000 USD

2023-01-15 * Sell XYZ and Receive Funds in Two Accounts
    assets:stocks:XYZ          -5 XYZ
    assets:cash:broker1         400 USD
    assets:cash:broker2         450 USD
    income:capital-gains       -350 USD ; Ignored
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Verify the remaining quantity of the lot
    xyz_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "XYZ", "20230101"]))
    assert isinstance(xyz_account_maybe, Some), "XYZ account not found"
    xyz_account = xyz_account_maybe.unwrap()
    xyz_balance = xyz_account.get_own_balance(Commodity("XYZ"))
    assert isinstance(xyz_balance, AssetBalance)
    assert len(xyz_balance.lots) == 1
    assert xyz_balance.lots[0].remaining_quantity == Decimal("5") # 10 initial - 5 sold


def test_calculate_balances_and_lots_insufficient_lots():
    journal_string = """
2023-01-01 * Open XYZ Lot 1
    assets:stocks:XYZ:20230101  5 XYZ @@ 500 USD
    equity:opening-balances     -5 XYZ
    assets:cash                -500 USD

2023-01-15 * Sell XYZ More Than Owned
    assets:stocks:XYZ          -10 XYZ
    assets:cash                 1500 USD
    income:capital-gains       -1000 USD ; Ignored
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    
    result = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result, Failure), "Expected BalanceSheet.from_transactions to fail"
    errors = result.failure()
    assert len(errors) > 0, "Expected at least one error"
    
    actual_error = errors[0].original_error
    assert isinstance(actual_error, ValueError), f"Expected ValueError, got {type(actual_error)}"
    
    error_str = str(actual_error)
    assert "Not enough open lots found" in error_str
    assert "Remaining to match: 5" in error_str
    assert "Account Details (assets:stocks:XYZ for XYZ):" in error_str
    assert "Own: -10 XYZ" in error_str # Corrected assertion
    assert "Total: -5 XYZ" in error_str # Corrected assertion
    assert "Available Lots Considered:" in error_str
    assert "Acq. Date: 2023-01-01, Orig. Qty: 5 XYZ, Rem. Qty: 0, Cost/Unit: 100 USD" in error_str # Corrected Rem. Qty and formatting


def test_calculate_balances_and_lots_complex_fifo():
    journal_string = """
2023-01-01 * Buy ABC Lot 1
    assets:stocks:ABC:20230101  10 ABC @@ 1000 USD
    equity:opening-balances     -10 ABC
    assets:cash                -1000 USD

2023-01-05 * Buy ABC Lot 2
    assets:stocks:ABC:20230105  15 ABC @@ 2250 USD
    equity:opening-balances     -15 ABC
    assets:cash                -2250 USD

2023-01-10 * Buy ABC Lot 3
    assets:stocks:ABC:20230110  5 ABC @@ 1000 USD
    equity:opening-balances     -5 ABC
    assets:cash                -1000 USD

2023-01-15 * Sell ABC Part 1 (from Lot 1)
    assets:stocks:ABC          -8 ABC
    assets:cash                 1200 USD
    income:capital-gains        -400 USD ; Ignored

2023-01-20 * Sell ABC Part 2 (from Lot 1 and Lot 2)
    assets:stocks:ABC          -10 ABC
    assets:cash                 1800 USD
    income:capital-gains        -300 USD ; Ignored

2023-01-25 * Sell ABC Part 3 (from Lot 2 and Lot 3)
    assets:stocks:ABC          -7 ABC
    assets:cash                 1500 USD
    income:capital-gains        -200 USD ; Ignored
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Verify remaining quantities
    abc_account_lot1_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "ABC", "20230101"]))
    assert isinstance(abc_account_lot1_maybe, Some), "ABC lot 1 account not found"
    abc_account_lot1 = abc_account_lot1_maybe.unwrap()
    abc_balance_lot1 = abc_account_lot1.get_own_balance(Commodity("ABC"))
    assert isinstance(abc_balance_lot1, AssetBalance)
    assert len(abc_balance_lot1.lots) == 1
    assert abc_balance_lot1.lots[0].remaining_quantity == Decimal("0") # 10 initial - 8 sold - 2 sold

    abc_account_lot2_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "ABC", "20230105"]))
    assert isinstance(abc_account_lot2_maybe, Some), "ABC lot 2 account not found"
    abc_account_lot2 = abc_account_lot2_maybe.unwrap()
    abc_balance_lot2 = abc_account_lot2.get_own_balance(Commodity("ABC"))
    assert isinstance(abc_balance_lot2, AssetBalance)
    assert len(abc_balance_lot2.lots) == 1
    assert abc_balance_lot2.lots[0].remaining_quantity == Decimal("0") # 15 initial - 8 sold - 7 sold

    abc_account_lot3_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "ABC", "20230110"]))
    assert isinstance(abc_account_lot3_maybe, Some), "ABC lot 3 account not found"
    abc_account_lot3 = abc_account_lot3_maybe.unwrap()
    abc_balance_lot3 = abc_account_lot3.get_own_balance(Commodity("ABC"))
    assert isinstance(abc_balance_lot3, AssetBalance)
    assert len(abc_balance_lot3.lots) == 1
    assert abc_balance_lot3.lots[0].remaining_quantity == Decimal("5") # 5 initial - 0 sold
