import pytest
from decimal import Decimal
from datetime import date

from src.classes import AccountName, Amount, Commodity, Posting, Transaction
from src.balance import calculate_balances_and_lots, BalanceSheet, AssetLots, Lot

def test_calculate_balances_and_lots():
    """Tests the calculation of account balances and asset lots."""
    # Create sample transactions
    transactions = [
        # Initial cash deposit
        Transaction(
            date=date(2024, 1, 1),
            payee="Initial deposit",
            postings=[
                Posting(account=AccountName(parts=["assets", "bank"]), amount=Amount(Decimal("1000.00"), Commodity("USD"))),
                Posting(account=AccountName(parts=["equity", "opening-balances"]), amount=Amount(Decimal("-1000.00"), Commodity("USD"))),
            ],
        ),
        # Asset acquisition
        Transaction(
            date=date(2024, 2, 1),
            payee="Buy 10 shares of FOO",
            postings=[
                Posting(account=AccountName(parts=["assets", "broker", "FOO", "20240201"]), amount=Amount(Decimal("10"), Commodity("FOO"))),
                Posting(account=AccountName(parts=["assets", "bank"]), amount=Amount(Decimal("-500.00"), Commodity("USD"))),
            ],
        ),
        # Another asset acquisition
        Transaction(
            date=date(2024, 3, 1),
            payee="Buy 5 shares of BAR",
            postings=[
                Posting(account=AccountName(parts=["assets", "broker", "BAR", "20240301"]), amount=Amount(Decimal("5"), Commodity("BAR"))),
                Posting(account=AccountName(parts=["assets", "bank"]), amount=Amount(Decimal("-200.00"), Commodity("USD"))),
            ],
        ),
    ]

    balance_sheet, asset_lots = calculate_balances_and_lots(transactions)

    # Verify BalanceSheet
    expected_balance_sheet: BalanceSheet = {
        AccountName(parts=["assets", "bank"]): {Commodity("USD"): Amount(Decimal("300.00"), Commodity("USD"))},
        AccountName(parts=["equity", "opening-balances"]): {Commodity("USD"): Amount(Decimal("-1000.00"), Commodity("USD"))},
        AccountName(parts=["assets", "broker", "FOO", "20240201"]): {Commodity("FOO"): Amount(Decimal("10"), Commodity("FOO"))},
        AccountName(parts=["assets", "broker", "BAR", "20240301"]): {Commodity("BAR"): Amount(Decimal("5"), Commodity("BAR"))},
    }

    assert balance_sheet == expected_balance_sheet

    # Verify AssetLots
    expected_asset_lots: AssetLots = {
        AccountName(parts=["assets", "broker", "FOO", "20240201"]): [
            Lot(
                acquisition_date="2024-02-01",
                quantity=Amount(Decimal("10"), Commodity("FOO")),
                cost_basis_per_unit=Amount(Decimal("50.00"), Commodity("USD")), # 500 / 10
                original_posting=transactions[1].postings[0]
            )
        ],
        AccountName(parts=["assets", "broker", "BAR", "20240301"]): [
            Lot(
                acquisition_date="2024-03-01",
                quantity=Amount(Decimal("5"), Commodity("BAR")),
                cost_basis_per_unit=Amount(Decimal("40.00"), Commodity("USD")), # 200 / 5
                original_posting=transactions[2].postings[0]
            )
        ],
    }

    # Compare asset_lots, ignoring the original_posting object identity
    assert set(asset_lots.keys()) == set(expected_asset_lots.keys())
    for account_name in asset_lots:
        assert len(asset_lots[account_name]) == len(expected_asset_lots[account_name])
        for i in range(len(asset_lots[account_name])):
            actual_lot = asset_lots[account_name][i]
            expected_lot = expected_asset_lots[account_name][i]
            assert actual_lot.acquisition_date == expected_lot.acquisition_date
            assert actual_lot.quantity == expected_lot.quantity
            assert actual_lot.cost_basis_per_unit == expected_lot.cost_basis_per_unit
            # Compare original_posting by content, not identity
            assert actual_lot.original_posting == expected_lot.original_posting
