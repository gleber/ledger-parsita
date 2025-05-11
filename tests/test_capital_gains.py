import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path

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
    CapitalGainResult
)
from src.balance import BalanceSheet, CashBalance, AssetBalance


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
    balance_sheet = BalanceSheet.from_journal(journal)

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
    asset_account = balance_sheet.get_account(AccountName(parts=["assets", "broker", "schwab", "GOOG", "20141226"]))
    assert asset_account is not None
    asset_balance = asset_account.get_own_balance(Commodity("GOOG"))
    assert isinstance(asset_balance, AssetBalance) 
    assert asset_balance.total_amount.quantity == Decimal("0")


def test_capital_gains_opening_balance_then_partial_sell():
    """
    Tests capital gains calculation when assets are introduced via a balance assertion
    and then a portion is sold.
    """
    journal_string = """
2023-01-01 * Opening Balance SOL
    assets:broker:tastytrade:SOL:20230101  = 10 SOL @@ 20 USD

2023-02-01 * Sell Partial SOL
    assets:broker:tastytrade     210.60 USD  ; Proceeds from 2 SOL @ 105.30 USD
    assets:broker:tastytrade:SOL:20230101    -2 SOL @@ 105.30 USD
    expenses:trading_fees        1.00 USD
"""
    # Using a dummy path as it's not strictly needed for content parsing here
    # The .unwrap() call will raise an error if parsing fails.
    journal = Journal.parse_from_content(journal_string, Path("test_opening_balance_sell.journal")).unwrap()
    balance_sheet = BalanceSheet.from_journal(journal)

    assert len(balance_sheet.capital_gains_realized) == 1
    gain_result = balance_sheet.capital_gains_realized[0]

    assert gain_result.closing_posting.account.parts == ["assets", "broker", "tastytrade", "SOL", "20230101"]
    assert gain_result.matched_quantity.quantity == Decimal("2")
    assert gain_result.matched_quantity.commodity.name == "SOL"
    
    # Cost basis: 10 SOL @@ 20 USD means 1 SOL costs 2 USD. For 2 SOL, cost is 2 * 2 = 4 USD.
    assert gain_result.cost_basis.quantity == Decimal("4.00") 
    assert gain_result.cost_basis.commodity.name == "USD"

    # Proceeds: 2 SOL * 105.30 USD/SOL = 210.60 USD
    assert gain_result.proceeds.quantity == Decimal("210.60")
    assert gain_result.proceeds.commodity.name == "USD"

    # Gain/Loss: 210.60 USD (proceeds) - 4.00 USD (cost basis) = 206.60 USD
    assert gain_result.gain_loss.quantity == Decimal("206.60")
    assert gain_result.gain_loss.commodity.name == "USD"
    
    assert gain_result.closing_date == date(2023, 2, 1)
    assert gain_result.acquisition_date == date(2023, 1, 1) # From dated subaccount (year directive + date in account)

    # Verify the remaining asset account balance
    asset_account = balance_sheet.get_account(AccountName(parts=["assets", "broker", "tastytrade", "SOL", "20230101"])) # This is correct
    assert asset_account is not None
    asset_balance = asset_account.get_own_balance(Commodity("SOL"))
    assert isinstance(asset_balance, AssetBalance) 
    assert asset_balance.total_amount.quantity == Decimal("8") # 10 initial - 2 sold = 8 remaining
    # Check remaining lots
    assert len(asset_balance.lots) == 1
    assert asset_balance.lots[0].remaining_quantity == Decimal("8") # Check remaining_quantity
    assert asset_balance.lots[0].cost_basis_per_unit.quantity == Decimal("2") # Cost per unit was 2 USD/SOL
    assert asset_balance.lots[0].cost_basis_per_unit.commodity.name == "USD"


def test_capital_gains_opening_balance_then_partial_sell_all():
    """
    Tests capital gains calculation when assets are introduced via a balance assertion
    and then a portion is sold.
    """
    journal_string = """
2023-01-01 * Opening Balance SOL
    assets:broker:tastytrade:SOL:20230101  = 10 SOL @@ 20 USD

2023-02-01 * Sell Partial SOL
    assets:broker:tastytrade     1000 USD
    assets:broker:tastytrade:SOL:20230101    -10 SOL
"""
    journal = Journal.parse_from_content(journal_string, Path("test_opening_balance_sell.journal")).unwrap().strip_loc()
    balance_sheet = BalanceSheet.from_journal(journal)

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
    with pytest.raises(ValueError) as excinfo:
        BalanceSheet.from_journal(journal)

    assert "No lots found for assets:broker:tastytrade:SOL to match sale" in str(excinfo.value)
    assert "Possible reason: The initial balance for SOL in this account might have been asserted without a cost basis" in str(excinfo.value)
    assert "Please ensure all opening balances for assets include a cost basis using '@@' (total cost) or '@' (per-unit cost)" in str(excinfo.value)
