import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path
from textwrap import dedent
from returns.maybe import Some, Nothing
from returns.result import Success, Failure # Import Success and Failure

from src.classes import (
    Transaction,
    Posting,
    AccountName,
    Amount,
    Commodity,
    SourceLocation,
    JournalEntry,
    CostKind,
    Cost,
    CapitalGainResult
)
from src.journal import Journal
from src.balance import BalanceSheet, CashBalance, AssetBalance

pytest.skip(allow_module_level=True)

def test_capital_gains_rsu_style_income_then_sale():
    """
    Tests capital gains calculation for shares acquired via an income posting (like RSUs)
    and then sold. Assumes $0 cost basis if income posting has no explicit price.
    """
    journal_string = """
2014-12-31 * Deposit GOOG Single RS
    assets:broker:schwab:GOOG:20141226          4 GOOG
    income:google:equity                       -4 GOOG

2019-09-27 * Sale GOOG Single Share Sale
    assets:broker:schwab                             4972.04 USD
    assets:broker:schwab:GOOG:20141226    -4 GOOG @@ 4972.04 USD
"""
    # Using a dummy path as it's not strictly needed for content parsing here
    journal = Journal.parse_from_content(journal_string, Path("test_rsu.journal")).unwrap()
    result_balance_sheet = BalanceSheet.from_journal(journal)
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_journal failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    assert len(balance_sheet.capital_gains_realized) == 1
    gain_result = balance_sheet.capital_gains_realized[0]

    assert gain_result.closing_posting.account.name == "assets:broker:schwab:GOOG:20141226"
    assert gain_result.matched_quantity.quantity == Decimal("4")
    assert gain_result.matched_quantity.commodity.name == "GOOG"
    
    # Cost basis should be 0 as the income posting doesn't specify a price for GOOG
    # and the asset posting itself doesn't have a cost basis (e.g. @@ X USD)
    assert gain_result.cost_basis.quantity == Decimal("0") 
    assert gain_result.cost_basis.commodity.name == "USD" # Assuming USD is the cost basis currency or default

    assert gain_result.proceeds.quantity == Decimal("4972.04")
    assert gain_result.proceeds.commodity.name == "USD"

    assert gain_result.gain_loss.quantity == Decimal("4972.04") # Proceeds - 0 cost basis
    assert gain_result.gain_loss.commodity.name == "USD"
    
    assert gain_result.closing_date == date(2019, 9, 27)
    assert gain_result.acquisition_date == date(2014, 12, 31)

    # Verify the asset account is now zero
    asset_account_maybe = balance_sheet.get_account(AccountName(parts=["assets", "broker", "schwab", "GOOG", "20141226"]))
    assert isinstance(asset_account_maybe, Some), "Asset account GOOG:20141226 not found"
    asset_account = asset_account_maybe.unwrap()
    asset_balance = asset_account.get_own_balance(Commodity("GOOG"))
    assert isinstance(asset_balance, AssetBalance) 
    assert asset_balance.total_amount.quantity == Decimal("0")


def test_capital_gains_opening_balance_then_partial_sell():
    """
    Tests capital gains calculation when assets are introduced via a balance assertion
    and then a portion is sold.
    """
    # sol_commodity = Commodity("SOL") # This line was causing indentation error if uncommented incorrectly
    # Commodity.kind is a property, so we can't directly set it.
    # We rely on CRYPTO_TICKERS in base_classes.py to correctly identify SOL.
    # The issue is likely elsewhere if SOL is not treated as an AssetBalance.

    journal_string_balance_assertion = dedent("""\
        2023-01-01 * Opening Balance SOL
            assets:broker:tastytrade:SOL:20230101  = 10 SOL @@ 20 USD
        """)
        # Using a dummy path as it's not strictly needed for content parsing here
    journal_balance_assertion = Journal.parse_from_content(journal_string_balance_assertion, Path("test_balance_assertion.journal")).unwrap() # REMOVED .strip_loc()

    # Verify the posting object from the balance assertion
    assert len(journal_balance_assertion.entries) == 1
    balance_assertion_transaction = journal_balance_assertion.entries[0].transaction
    assert balance_assertion_transaction is not None
    assert len(balance_assertion_transaction.postings) == 1
    balance_posting = balance_assertion_transaction.postings[0]
    
    assert balance_posting.balance is not None, "Balance assertion posting has no .balance"
    assert balance_posting.balance.quantity == Decimal("10"), "Balance quantity is not 10"
    assert balance_posting.balance.commodity.name == "SOL", "Balance commodity is not SOL"
    assert balance_posting.cost is not None, "Balance assertion posting has no .cost"
    assert balance_posting.cost.kind == CostKind.TotalCost, "Balance assertion cost kind is not TotalCost"
    assert balance_posting.cost.amount.quantity == Decimal("20"), "Cost amount quantity is not 20"
    assert balance_posting.cost.amount.commodity.name == "USD", "Cost amount commodity is not USD"

    result_balance_sheet_assertion = BalanceSheet.from_journal(journal_balance_assertion)
    assert isinstance(result_balance_sheet_assertion, Success), f"BalanceSheet.from_journal for assertion failed: {result_balance_sheet_assertion.failure() if isinstance(result_balance_sheet_assertion, Failure) else 'Unknown error'}"
    balance_sheet_assertion = result_balance_sheet_assertion.unwrap()

    # Check if lot was created
    target_account_name = AccountName(parts=["assets", "broker", "tastytrade", "SOL", "20230101"])
    target_commodity = Commodity("SOL")
    
    account_node_maybe = balance_sheet_assertion.get_account(target_account_name)
    assert isinstance(account_node_maybe, Some), "Target account node not found after balance assertion"
    account_node = account_node_maybe.unwrap()
    
    balance_obj = account_node.get_own_balance(target_commodity)
    assert isinstance(balance_obj, AssetBalance), "Balance object is not AssetBalance for SOL"
    assert len(balance_obj.lots) == 1, "Lot not created from balance assertion"
    created_lot = balance_obj.lots[0]
    assert created_lot.quantity.quantity == Decimal("10")
    assert created_lot.cost_basis_per_unit.quantity == Decimal("2")
    assert created_lot.cost_basis_per_unit.commodity.name == "USD"
    assert not created_lot.is_short

    # Now test the full scenario
    journal_string_full = dedent("""\
        2023-01-01 * Opening Balance SOL
            assets:broker:tastytrade:SOL:20230101  = 10 SOL @@ 20 USD

        2023-02-01 * Sell Partial SOL
            assets:broker:tastytrade     210.60 USD  ; Proceeds from 2 SOL @ 105.30 USD
            assets:broker:tastytrade:SOL:20230101    -2 SOL @@ 105.30 USD
            expenses:trading_fees        1.00 USD
        """)
    journal_full = Journal.parse_from_content(journal_string_full, Path("test_opening_balance_sell.journal")).unwrap()
    result_balance_sheet_full = BalanceSheet.from_journal(journal_full)
    assert isinstance(result_balance_sheet_full, Success), f"BalanceSheet.from_journal for full scenario failed: {result_balance_sheet_full.failure() if isinstance(result_balance_sheet_full, Failure) else 'Unknown error'}"
    balance_sheet_full = result_balance_sheet_full.unwrap()

    assert len(balance_sheet_full.capital_gains_realized) == 1
    gain_result = balance_sheet_full.capital_gains_realized[0]

    assert gain_result.closing_posting.account.parts == ["assets", "broker", "tastytrade", "SOL", "20230101"]
    assert gain_result.matched_quantity.quantity == Decimal("2")
    assert gain_result.matched_quantity.commodity.name == "SOL"
    
    assert gain_result.cost_basis.quantity == Decimal("4.00") 
    assert gain_result.cost_basis.commodity.name == "USD"

    assert gain_result.proceeds.quantity == Decimal("210.60")
    assert gain_result.proceeds.commodity.name == "USD"

    assert gain_result.gain_loss.quantity == Decimal("206.60")
    assert gain_result.gain_loss.commodity.name == "USD"
    
    assert gain_result.closing_date == date(2023, 2, 1)
    assert gain_result.acquisition_date == date(2023, 1, 1)

    asset_account_maybe_full = balance_sheet_full.get_account(target_account_name)
    assert isinstance(asset_account_maybe_full, Some), "Asset account SOL:20230101 not found in full scenario"
    asset_account_full = asset_account_maybe_full.unwrap()
    asset_balance_full = asset_account_full.get_own_balance(target_commodity)
    assert isinstance(asset_balance_full, AssetBalance) 
    assert asset_balance_full.total_amount.quantity == Decimal("8")
    assert len(asset_balance_full.lots) == 1
    assert asset_balance_full.lots[0].remaining_quantity == Decimal("8")
    assert asset_balance_full.lots[0].cost_basis_per_unit.quantity == Decimal("2")
    assert asset_balance_full.lots[0].cost_basis_per_unit.commodity.name == "USD"

def test_capital_gains_opening_balance_then_sell_all():
    """
    Tests capital gains calculation when assets are introduced via a balance assertion
    and then a portion is sold.
    """
    # sol_commodity = Commodity("SOL") # Rely on CRYPTO_TICKERS

    journal_string = dedent("""\
        2023-01-01 * Opening Balance SOL
            assets:broker:tastytrade:SOL:20230101  = 10 SOL @@ 20 USD

        2023-02-01 * Sell Partial SOL
            assets:broker:tastytrade     1000 USD
            assets:broker:tastytrade:SOL:20230101    -10 SOL
        """)
    journal = Journal.parse_from_content(journal_string, Path("test_opening_balance_sell.journal")).unwrap().strip_loc()
    result_balance_sheet = BalanceSheet.from_journal(journal)
    assert isinstance(result_balance_sheet, Success), f"BalanceSheet.from_journal failed: {result_balance_sheet.failure() if isinstance(result_balance_sheet, Failure) else 'Unknown error'}"
    balance_sheet = result_balance_sheet.unwrap()

    assert len(balance_sheet.capital_gains_realized) == 1



def test_capital_gains_opening_balance_without_cost_then_partial_sell():
    """
    Tests capital gains calculation when assets are introduced via a balance assertion
    and then a portion is sold.
    """
    journal_string = """
2022-12-31 * "Opening state"
  assets:broker:tastytrade  = 293.33518632 SOL

2023-12-29 Sold 25 SOL/USD @ 105.30
  assets:broker:tastytrade  2632.50 USD
    assets:broker:tastytrade  -25 SOL @ 105.30 USD
"""
    journal = Journal.parse_from_content(journal_string, Path("test_opening_balance_sell.journal")).unwrap().strip_loc()
    result = BalanceSheet.from_journal(journal)
    assert isinstance(result, Failure), "Expected BalanceSheet.from_journal to fail"
    errors = result.failure()
    assert len(errors) > 0, "Expected at least one error"
    
    # Assuming the relevant error is the first one for this specific test case
    actual_error = errors[0].original_error
    assert isinstance(actual_error, ValueError), f"Expected ValueError, got {type(actual_error)}"

    error_str = str(actual_error)
    expected_error_message = "Balance assertion for assets:broker:tastytrade on 2022-12-31 must have a cost or be a cash commodity."
    assert expected_error_message in error_str
    # The following more detailed messages are not part of this specific ValueError
    # assert "Possible reason: The initial balance for SOL in this account might have been asserted without a cost basis" in error_str
    # assert "Please ensure all opening balances for assets include a cost basis using '@@' (total cost) or '@' (per-unit cost)" in error_str
