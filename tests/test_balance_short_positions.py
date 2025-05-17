import pytest
from decimal import Decimal
from datetime import date

from src.common_types import PositionEffect, CommodityKind # CommodityKind is in common_types
from src.base_classes import AccountName, Amount, Commodity # Commodity is here
from src.classes import Posting, Transaction, Cost, CostKind, Tag
from src.balance import BalanceSheet, Lot, AssetBalance, Account
from returns.maybe import Some, Nothing
from returns.result import Success, Failure

def test_open_short_position_creates_short_lot():
    """Test that opening a short position correctly creates a short Lot."""
    transaction_date = date(2024, 3, 1)
    option_commodity = Commodity("TSLA260116P200") # kind is a property, not an init arg

    short_sale_posting = Posting(
        account=AccountName(["assets", "broker", "tsla"]),
        amount=Amount(Decimal("-1"), option_commodity), # Selling 1 put option
        cost=Cost(kind=CostKind.TotalCost, amount=Amount(Decimal("4344.00"), Commodity("USD"))), # Proceeds
        tags=[Tag(name="type", value="short")]
    )
    cash_posting = Posting(
        account=AccountName(["assets", "broker", "cash"]),
        amount=Amount(Decimal("4342.83"), Commodity("USD")) # Net cash received
    )
    fee_posting = Posting(
        account=AccountName(["expenses", "broker", "fees"]),
        amount=Amount(Decimal("1.17"), Commodity("USD"))
    )
    transaction = Transaction(
        date=transaction_date,
        payee="Sold TSLA Put",
        postings=[short_sale_posting, cash_posting, fee_posting]
    )

    # Manually set source_location for postings if your Lot.try_create_from_posting or other logic expects it
    # For this test, it might not be strictly necessary if not used by the direct logic path.

    balance_sheet = BalanceSheet()
    result = balance_sheet.apply_transaction(transaction)

    assert isinstance(result, Success)
    bs = result.unwrap()

    tsla_option_account_maybe = bs.get_account(AccountName(["assets", "broker", "tsla"]))
    assert isinstance(tsla_option_account_maybe, Some), "TSLA option account should exist"
    tsla_option_account = tsla_option_account_maybe.unwrap()

    assert option_commodity in tsla_option_account.own_balances
    option_balance = tsla_option_account.own_balances[option_commodity]
    assert isinstance(option_balance, AssetBalance)
    
    assert len(option_balance.lots) == 1
    created_lot = option_balance.lots[0]

    assert created_lot.is_short is True
    assert created_lot.quantity == Amount(Decimal("-1"), option_commodity)
    # Cost basis for short lot stores proceeds per unit
    assert created_lot.cost_basis_per_unit == Amount(Decimal("4344.00"), Commodity("USD"))
    assert created_lot.acquisition_date == str(transaction_date)
    assert created_lot.original_posting == short_sale_posting
    assert created_lot.remaining_quantity == Decimal("-1")

    # Check overall account balance for the option
    assert option_balance.total_amount == Amount(Decimal("-1"), option_commodity)

    # Check cash account
    cash_account_maybe = bs.get_account(AccountName(["assets", "broker", "cash"]))
    assert isinstance(cash_account_maybe, Some), "Cash account should exist"
    cash_account = cash_account_maybe.unwrap()
    assert cash_account.total_balances[Commodity("USD")] == Amount(Decimal("4342.83"), Commodity("USD"))

    # Check fee account
    fee_account_maybe = bs.get_account(AccountName(["expenses", "broker", "fees"]))
    assert isinstance(fee_account_maybe, Some), "Fee account should exist"
    fee_account = fee_account_maybe.unwrap()
    assert fee_account.total_balances[Commodity("USD")] == Amount(Decimal("1.17"), Commodity("USD"))


def test_close_short_position_at_a_loss():
    """Test closing a short position where the cost to cover is higher than initial proceeds."""
    option_cmd = Commodity("XYZ251231P10")
    usd_cmd = Commodity("USD")
    transaction_date_open = date(2024, 1, 10)
    transaction_date_close = date(2024, 2, 15)

    # 1. Open Short Position
    open_short_posting = Posting(
        account=AccountName(["assets", "broker", "xyz"]),
        amount=Amount(Decimal("-1"), option_cmd), # Sell 1 XYZ Put
        cost=Cost(kind=CostKind.TotalCost, amount=Amount(Decimal("100"), usd_cmd)), # Proceeds = $100
        tags=[Tag(name="type", value="short")]
    )
    open_cash_posting = Posting(
        account=AccountName(["assets", "broker", "cash"]),
        amount=Amount(Decimal("100"), usd_cmd)
    )
    open_transaction = Transaction(
        date=transaction_date_open,
        payee="Sold XYZ Put",
        postings=[open_short_posting, open_cash_posting]
    )

    # 2. Close Short Position (Buy to Cover)
    close_short_posting = Posting(
        account=AccountName(["assets", "broker", "xyz"]),
        amount=Amount(Decimal("1"), option_cmd), # Buy 1 XYZ Put to cover
        cost=Cost(kind=CostKind.TotalCost, amount=Amount(Decimal("120"), usd_cmd)) # Cost to cover = $120
        # No 'type:short' tag here, as it's a buy to cover.
        # The get_effect should identify this as CLOSE_SHORT based on positive quantity
        # against an existing short position.
    )
    close_cash_posting = Posting(
        account=AccountName(["assets", "broker", "cash"]),
        amount=Amount(Decimal("-120"), usd_cmd)
    )
    close_transaction = Transaction(
        date=transaction_date_close,
        payee="Bought to Cover XYZ Put",
        postings=[close_short_posting, close_cash_posting]
    )

    balance_sheet = BalanceSheet()
    res_open = balance_sheet.apply_transaction(open_transaction)
    assert isinstance(res_open, Success)
    
    res_close = balance_sheet.apply_transaction(close_transaction)
    assert isinstance(res_close, Success)
    bs = res_close.unwrap()

    # Verify capital gains
    assert len(bs.capital_gains_realized) == 1
    gain_result = bs.capital_gains_realized[0]

    assert gain_result.closing_posting == close_short_posting
    assert gain_result.opening_lot_original_posting == open_short_posting
    assert gain_result.matched_quantity == Amount(Decimal("1"), option_cmd)
    # For short closure: cost_basis is cost_to_cover, proceeds is initial_proceeds_from_short_sale
    assert gain_result.cost_basis == Amount(Decimal("120"), usd_cmd) # Cost to cover
    assert gain_result.proceeds == Amount(Decimal("100"), usd_cmd) # Initial proceeds
    assert gain_result.gain_loss == Amount(Decimal("-20"), usd_cmd) # Loss of $20
    assert gain_result.closing_date == transaction_date_close
    assert gain_result.acquisition_date == transaction_date_open # Date short was opened

    # Verify asset account (XYZ options)
    xyz_account_maybe = bs.get_account(AccountName(["assets", "broker", "xyz"]))
    assert isinstance(xyz_account_maybe, Some)
    xyz_account = xyz_account_maybe.unwrap()
    
    option_asset_balance = xyz_account.own_balances.get(option_cmd)
    assert isinstance(option_asset_balance, AssetBalance)
    assert option_asset_balance.total_amount == Amount(Decimal("0"), option_cmd) # Position should be flat
    
    # Check that the short lot was consumed
    assert len(option_asset_balance.lots) == 1 # Lot is kept for record
    closed_lot = option_asset_balance.lots[0]
    assert closed_lot.is_short is True
    assert closed_lot.remaining_quantity == Decimal("0") # Fully covered

    # Verify cash account
    cash_account_maybe = bs.get_account(AccountName(["assets", "broker", "cash"]))
    assert isinstance(cash_account_maybe, Some)
    cash_account = cash_account_maybe.unwrap()
    # Initial: +100 (from short sale), Then: -120 (to cover) = -20
    assert cash_account.total_balances[usd_cmd] == Amount(Decimal("-20"), usd_cmd)
