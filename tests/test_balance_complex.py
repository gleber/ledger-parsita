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
    
    # Assuming the relevant error is the first one for this specific test case
    # In a more complex scenario with multiple potential errors, might need to iterate/filter
    actual_error = errors[0].original_error 
    assert isinstance(actual_error, ValueError), f"Expected ValueError, got {type(actual_error)}"
    
    error_str = str(actual_error)
    assert "Not enough open lots found" in error_str
    assert "Remaining to match: 5" in error_str
    assert "Account Details (assets:stocks:XYZ for XYZ):" in error_str
    # The error message reflects the state *before* the problematic posting's own quantity is applied to the specific account node for display in the error.
    # It shows the total lots available from sub-accounts.
    assert "Total: 5 XYZ" in error_str 
    # The "Own: -10 XYZ" and "Total: -5 XYZ" might appear if the error message formatting changes to show post-attempted-application state.
    # For now, the current error message format focuses on available lots.
    assert "Available Lots Considered:" in error_str
    # The Rem. Qty in the lot details will be 0 because the matching happens before this error is raised for the *overall* transaction.
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
    
    # This should not raise a ValueError
    result_balance_sheet = BalanceSheet.from_transactions(transactions_only)
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_transactions failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    # Assert that no capital gains were realized from this transfer
    assert len(balance_sheet.capital_gains_realized) == 0

    # Verify BTC balances
    gemini_btc_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "broker", "gemini", "BTC"]))
    assert isinstance(gemini_btc_account_maybe, Some), "Gemini BTC account not found"
    gemini_btc_account = gemini_btc_account_maybe.unwrap()
    gemini_btc_balance = gemini_btc_account.get_own_balance(Commodity("BTC"))
    assert isinstance(gemini_btc_balance, AssetBalance)
    assert gemini_btc_balance.total_amount.quantity == Decimal("0.5") # 1 - 0.5

    kraken_btc_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "broker", "kraken", "BTC"]))
    assert isinstance(kraken_btc_account_maybe, Some), "Kraken BTC account not found"
    kraken_btc_account = kraken_btc_account_maybe.unwrap()
    kraken_btc_balance = kraken_btc_account.get_own_balance(Commodity("BTC"))
    assert isinstance(kraken_btc_balance, AssetBalance)
    assert kraken_btc_balance.total_amount.quantity == Decimal("0.5")
    # Optionally, check if lot information was transferred (currently not implemented, so lots would be new)
    assert len(kraken_btc_balance.lots) == 1 # A new lot is created for the receiving side
    assert kraken_btc_balance.lots[0].quantity.quantity == Decimal("0.5")
    assert kraken_btc_balance.lots[0].cost_basis_per_unit.quantity == Decimal("10000") # From cost hint


def test_calculate_balances_and_lots_complex_fifo():
    """Tests complex FIFO capital gains calculation with multiple buys and sells."""
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

    ; Total acquired: 10 + 15 + 5 = 30 ABC
    ; Total cost basis: 1000 + 2250 + 1000 = 4250 USD

2023-01-15 * Sell ABC Part 1 (from Lot 1)
    assets:stocks:ABC          -8 ABC
    assets:cash                 1200 USD
    income:capital-gains        -400 USD ; Ignored
    ; Sold 8 from Lot 1 (10 initial). Remaining in Lot 1: 2.
    ; Proceeds per unit: 1200 / 8 = 150 USD
    ; Cost basis per unit (Lot 1): 1000 / 10 = 100 USD
    ; Gain/Loss: (150 * 8) - (100 * 8) = 1200 - 800 = 400 USD gain

2023-01-20 * Sell ABC Part 2 (from Lot 1 and Lot 2)
    assets:stocks:ABC          -10 ABC
    assets:cash                 1800 USD
    income:capital-gains        -300 USD ; Ignored
    ; Sold 10. Match 2 from Lot 1 (2 remaining). Match 8 from Lot 2 (15 initial). Remaining in Lot 2: 7.
    ; Proceeds per unit: 1800 / 10 = 180 USD
    ; Cost basis per unit (Lot 1): 100 USD
    ; Cost basis per unit (Lot 2): 2250 / 15 = 150 USD
    ; Gain/Loss (Lot 1 portion): (180 * 2) - (100 * 2) = 360 - 200 = 160 USD gain
    ; Gain/Loss (Lot 2 portion): (180 * 8) - (150 * 8) = 1440 - 1200 = 240 USD gain
    ; Total gain for Sale 2: 160 + 240 = 400 USD gain

2023-01-25 * Sell ABC Part 3 (from Lot 2 and Lot 3)
    assets:stocks:ABC          -7 ABC
    assets:cash                 1500 USD
    income:capital-gains        -200 USD ; Ignored
    ; Sold 7. Match 7 from Lot 2 (7 remaining). Remaining in Lot 2: 0.
    ; Proceeds per unit: 1500 / 7 = 214.28... USD
    ; Cost basis per unit (Lot 2): 150 USD
    ; Gain/Loss (Lot 2 portion): (214.28... * 7) - (150 * 7) = 1500 - 1050 = 450 USD gain
    ; Total gain for Sale 3: 450 USD gain

    ; Total realized gain: 400 + 400 + 450 = 1250 USD
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
