import pytest
import importlib # Import the importlib module
from decimal import Decimal
from datetime import date
from pathlib import Path # Import Path
from returns.maybe import Some, Nothing
from returns.result import Success, Failure # Import Success and Failure

from src.classes import AccountName, Commodity, Amount, Cost, CostKind, Posting, Transaction
from src.balance import BalanceSheet, Lot, Account, Balance, CashBalance, AssetBalance # Updated import
from src.journal import Journal

pytest.skip(allow_module_level=True)

def test_calculate_balances_and_lots_partial_match_gain():
    """Tests capital gains calculation with a partial match of a lot (gain)."""
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
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap() # Updated call
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


def test_calculate_balances_and_lots_partial_match_loss():
    """Tests capital gains calculation with a partial match of a lot (loss)."""
    journal_string = """
2023-01-01 * Open ABC Lot 1
    assets:stocks:ABC:20230101  10 ABC @@ 1000 USD
    equity:opening-balances     -10 ABC
    assets:cash                -1000 USD

2023-01-15 * Sell ABC Partial
    assets:stocks:ABC          -4 ABC
    assets:cash                 300 USD
    expenses:capital-loss      -100 USD ; Ignored
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap() # Updated call
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Verify the remaining quantity of the lot
    abc_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "ABC", "20230101"]))
    assert isinstance(abc_account_maybe, Some), "ABC account not found"
    abc_account = abc_account_maybe.unwrap()
    abc_balance = abc_account.get_own_balance(Commodity("ABC"))
    assert isinstance(abc_balance, AssetBalance)
    assert len(abc_balance.lots) == 1
    assert abc_balance.lots[0].remaining_quantity == Decimal("6") # 10 initial - 4 sold


def test_calculate_balances_and_lots_multiple_postings_same_commodity():
    """Tests capital gains calculation with multiple postings of the same commodity in a transaction."""
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
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap() # Updated call
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
    """Tests capital gains calculation with multiple cash postings in a transaction."""
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
    """Tests capital gains calculation when selling more quantity than owned."""
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
    
    result = BalanceSheet.from_transactions(transactions_only)
    assert isinstance(result, Failure), "Expected BalanceSheet.from_transactions to fail"
    errors = result.failure()
    assert len(errors) > 0, "Expected at least one error"
    
    actual_error = errors[0].original_error 
    assert isinstance(actual_error, ValueError), f"Expected ValueError, got {type(actual_error)}"
    
    error_str = str(actual_error)
    assert "Not enough open lots found" in error_str
    assert "Remaining to match: 5" in error_str
    assert "Account Details (assets:stocks:XYZ for XYZ):" in error_str
    assert "Total: 5 XYZ" in error_str 
    assert "Available Lots Considered:" in error_str
    assert "Acq. Date: 2023-01-01, Orig. Qty: 5 XYZ, Rem. Qty: 0, Cost/Unit: 100 USD" in error_str


def test_crypto_transfer_no_cash_proceeds():
    """Tests that a crypto transfer without cash proceeds does not trigger a capital gains error."""
    journal_string = """
2020-01-01 * Opening Balance
    assets:broker:gemini:BTC          1 BTC @@ 10000 USD
    equity:opening-balances

2021-05-17 * Transfer BTC Gemini to Kraken
    assets:broker:kraken:BTC          0.5 BTC @ 10000 USD ; Cost basis hint
    assets:broker:gemini:BTC         -0.5 BTC
    expenses:txfees:gemini            10 USD ; Fee for transfer
    assets:cash:gemini               -10 USD
"""
    journal = Journal.parse_from_content(journal_string, Path("crypto_transfer.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only)
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    assert len(balance_sheet.capital_gains_realized) == 0

    gemini_btc_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "broker", "gemini", "BTC"]))
    assert isinstance(gemini_btc_account_maybe, Some), "Gemini BTC account not found"
    gemini_btc_account = gemini_btc_account_maybe.unwrap()
    gemini_btc_balance = gemini_btc_account.get_own_balance(Commodity("BTC"))
    assert isinstance(gemini_btc_balance, AssetBalance)
    assert gemini_btc_balance.total_amount.quantity == Decimal("0.5")

    kraken_btc_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "broker", "kraken", "BTC"]))
    assert isinstance(kraken_btc_account_maybe, Some), "Kraken BTC account not found"
    kraken_btc_account = kraken_btc_account_maybe.unwrap()
    kraken_btc_balance = kraken_btc_account.get_own_balance(Commodity("BTC"))
    assert isinstance(kraken_btc_balance, AssetBalance)
    assert kraken_btc_balance.total_amount.quantity == Decimal("0.5")
    assert len(kraken_btc_balance.lots) == 1
    assert kraken_btc_balance.lots[0].quantity.quantity == Decimal("0.5")
    assert kraken_btc_balance.lots[0].cost_basis_per_unit.quantity == Decimal("10000")


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
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only)
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    abc_account_lot1_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "ABC", "20230101"]))
    assert isinstance(abc_account_lot1_maybe, Some), "ABC lot 1 account not found"
    abc_account_lot1 = abc_account_lot1_maybe.unwrap()
    abc_balance_lot1 = abc_account_lot1.get_own_balance(Commodity("ABC"))
    assert isinstance(abc_balance_lot1, AssetBalance)
    assert len(abc_balance_lot1.lots) == 1
    assert abc_balance_lot1.lots[0].remaining_quantity == Decimal("0")

    abc_account_lot2_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "ABC", "20230105"]))
    assert isinstance(abc_account_lot2_maybe, Some), "ABC lot 2 account not found"
    abc_account_lot2 = abc_account_lot2_maybe.unwrap()
    abc_balance_lot2 = abc_account_lot2.get_own_balance(Commodity("ABC"))
    assert isinstance(abc_balance_lot2, AssetBalance)
    assert len(abc_balance_lot2.lots) == 1
    assert abc_balance_lot2.lots[0].remaining_quantity == Decimal("0")

    abc_account_lot3_maybe = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "ABC", "20230110"]))
    assert isinstance(abc_account_lot3_maybe, Some), "ABC lot 3 account not found"
    abc_account_lot3 = abc_account_lot3_maybe.unwrap()
    abc_balance_lot3 = abc_account_lot3.get_own_balance(Commodity("ABC"))
    assert isinstance(abc_balance_lot3, AssetBalance)
    assert len(abc_balance_lot3.lots) == 1
    assert abc_balance_lot3.lots[0].remaining_quantity == Decimal("5")

def test_two_step_balance_conversion():
    """Tests the conversion of a balance sheet to a different currency."""
    journal_string = """
2000-01-01 * Opening Balance
  assets:broker:tastytrade:NVTA            200.0 NVTA @@ 200.0 USD

2024-02-15 Symbol change:  Close 200.0 NVTA
  assets:broker:tastytrade:NVTA:20240215  -200.0 NVTA
  equity:conversion:tastytrade             200.0 NVTA

2024-02-15 Symbol change:  Open 200.0 NVTAQ
  assets:broker:tastytrade:NVTAQ:20240215  200.0 NVTAQ
  equity:conversion:tastytrade            -200.0 NVTAQ
"""
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap()
    balance_result = BalanceSheet.from_journal(journal)
    assert isinstance(balance_result, Success), f"BalanceSheet.from_journal failed: {balance_result.failure()}"
    balance = balance_result.unwrap()

    actual_flat_balance = list(balance.format_account_flat(display='both'))
    
    # Expected output needs to be carefully determined by running the code and inspecting
    # For now, using more robust checks for key elements
    
    # Check for assets:broker:tastytrade:NVTA (original lot, should be closed out or transferred)
    # The original lot is assets:broker:tastytrade:NVTA (dated 2000-01-01)
    # The closing transaction uses assets:broker:tastytrade:NVTA:20240215
    # These are different accounts. The original NVTA lot should still exist.
    
    expected_accounts_present = {
        "assets:broker:tastytrade:NVTA", # Original dated lot account
        "assets:broker:tastytrade:NVTA:20240215", # Account used in closing NVTA
        "assets:broker:tastytrade:NVTAQ:20240215", # Account for new NVTAQ
        "equity:conversion:tastytrade"
    }
    
    present_accounts = set()
    for line in actual_flat_balance:
        if not line.startswith("  "): # It's an account name line
            present_accounts.add(line.strip())
            
    assert expected_accounts_present.issubset(present_accounts), \
        f"Missing expected accounts. Expected: {expected_accounts_present}, Got: {present_accounts}, Full output: {actual_flat_balance}"

    # Check balances for key accounts
    # assets:broker:tastytrade:NVTA (original opening balance) should still have its lot
    # The test implies this account is NOT directly affected by the "Symbol change" transactions,
    # as those use dated subaccounts like NVTA:20240215.
    # So, the original NVTA lot should remain.
    
    # assets:broker:tastytrade:NVTA (original opening balance)
    # This account is where the initial lot is created.
    # The "Symbol change" transactions use different dated subaccounts.
    original_nvta_account_maybe = balance.get_account(AccountName(parts=["assets", "broker", "tastytrade", "NVTA"]))
    assert isinstance(original_nvta_account_maybe, Some), "Original assets:broker:tastytrade:NVTA account not found"
    original_nvta_account = original_nvta_account_maybe.unwrap()
    original_nvta_balance = original_nvta_account.get_own_balance(Commodity("NVTA"))
    assert isinstance(original_nvta_balance, AssetBalance)
    assert original_nvta_balance.total_amount == Amount(Decimal("200.0"), Commodity("NVTA"))
    assert len(original_nvta_balance.lots) == 1
    # Compare quantity and commodity attributes directly to avoid source_location issues
    assert original_nvta_balance.lots[0].quantity.quantity == Decimal("200.0")
    assert original_nvta_balance.lots[0].quantity.commodity.name == "NVTA"
    assert original_nvta_balance.lots[0].cost_basis_per_unit == Amount(Decimal("1.0"), Commodity("USD"))

    # assets:broker:tastytrade:NVTA:20240215 should be -200 NVTA
    nvta_20240215_account_maybe = balance.get_account(AccountName(parts=["assets", "broker", "tastytrade", "NVTA", "20240215"]))
    assert isinstance(nvta_20240215_account_maybe, Some), "assets:broker:tastytrade:NVTA:20240215 account not found"
    nvta_20240215_account = nvta_20240215_account_maybe.unwrap()
    nvta_20240215_balance = nvta_20240215_account.get_own_balance(Commodity("NVTA"))
    assert nvta_20240215_balance.total_amount == Amount(Decimal("-200.0"), Commodity("NVTA"))

    # assets:broker:tastytrade:NVTAQ:20240215 should be 200 NVTAQ
    nvtaq_20240215_account_maybe = balance.get_account(AccountName(parts=["assets", "broker", "tastytrade", "NVTAQ", "20240215"]))
    assert isinstance(nvtaq_20240215_account_maybe, Some), "assets:broker:tastytrade:NVTAQ:20240215 account not found"
    nvtaq_20240215_account = nvtaq_20240215_account_maybe.unwrap()
    nvtaq_20240215_balance = nvtaq_20240215_account.get_own_balance(Commodity("NVTAQ"))
    assert nvtaq_20240215_balance.total_amount == Amount(Decimal("200.0"), Commodity("NVTAQ"))
    
    # equity:conversion:tastytrade should have 200 NVTA and -200 NVTAQ
    equity_account_maybe = balance.get_account(AccountName(parts=["equity", "conversion", "tastytrade"]))
    assert isinstance(equity_account_maybe, Some), "equity:conversion:tastytrade account not found"
    equity_account = equity_account_maybe.unwrap()
    
    equity_nvta_balance = equity_account.get_own_balance(Commodity("NVTA"))
    assert equity_nvta_balance.total_amount == Amount(Decimal("200.0"), Commodity("NVTA"))
    
    equity_nvtaq_balance = equity_account.get_own_balance(Commodity("NVTAQ"))
    assert equity_nvtaq_balance.total_amount == Amount(Decimal("-200.0"), Commodity("NVTAQ"))
