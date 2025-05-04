import pytest
from decimal import Decimal
from datetime import date

from src.classes import AccountName, Commodity, Amount, Cost, CostKind, Posting, Transaction
from src.balance import calculate_balances_and_lots, BalanceSheet, Lot

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
        # Asset acquisition with implicit cost
        Transaction(
            date=date(2024, 4, 1),
            payee="Buy BAZ with implicit cost",
            postings=[
                Posting(account=AccountName(parts=["assets", "broker", "BAZ", "20240401"]), amount=Amount(Decimal("20"), Commodity(name="BAZ"))),
                Posting(account=AccountName(parts=["assets", "bank"]), amount=Amount(Decimal("-400.00"), Commodity(name="USD"))),
            ],
        ),
    ]

    balance_sheet = calculate_balances_and_lots(transactions)

    # Verify BalanceSheet structure and content
    expected_balances = {
        AccountName(parts=["assets", "bank"]): {Commodity("USD"): Amount(Decimal("300.00") - Decimal("400.00"), Commodity("USD"))},
        AccountName(parts=["equity", "opening-balances"]): {Commodity("USD"): Amount(Decimal("-1000.00"), Commodity("USD"))},
        AccountName(parts=["assets", "broker", "FOO", "20240201"]): {Commodity("FOO"): Amount(Decimal("10"), Commodity("FOO"))},
        AccountName(parts=["assets", "broker", "BAR", "20240301"]): {Commodity("BAR"): Amount(Decimal("5"), Commodity("BAR"))},
        AccountName(parts=["assets", "broker", "BAZ", "20240401"]): {Commodity("BAZ"): Amount(Decimal("20"), Commodity("BAZ"))},
    }

    assert set(balance_sheet.accounts.keys()) == set(expected_balances.keys())

    for account_name, expected_commodity_balances in expected_balances.items():
        account = balance_sheet.get_account(account_name)
        assert set(account.balances.keys()) == set(expected_commodity_balances.keys())
        for commodity, expected_amount in expected_commodity_balances.items():
            balance = account.get_balance(commodity)
            assert balance.total_amount == expected_amount

    # Verify AssetLots within the BalanceSheet
    expected_asset_lots_structure = {
        AccountName(parts=["assets", "broker", "FOO", "20240201"]): {
            Commodity("FOO"): [
                Lot(
                    acquisition_date="2024-02-01",
                    quantity=Amount(Decimal("10"), Commodity("FOO")),
                    cost_basis_per_unit=Amount(Decimal("50.00"), Commodity("USD")),
                    original_posting=transactions[1].postings[0]
                )
            ]
        },
        AccountName(parts=["assets", "broker", "BAR", "20240301"]): {
            Commodity("BAR"): [
                Lot(
                    acquisition_date="2024-03-01",
                    quantity=Amount(Decimal("5"), Commodity("BAR")),
                    cost_basis_per_unit=Amount(Decimal("40.00"), Commodity("USD")),
                    original_posting=transactions[2].postings[0]
                )
            ]
        },
        AccountName(parts=["assets", "broker", "BAZ", "20240401"]): {
            Commodity("BAZ"): [
                Lot(
                    acquisition_date="2024-04-01",
                    quantity=Amount(Decimal("20"), Commodity(name="BAZ")),
                    cost_basis_per_unit=Amount(Decimal("20.00"), Commodity(name="USD")),
                    original_posting=transactions[3].postings[0]
                )
            ]
        },
    }

    for account_name, expected_commodity_lots in expected_asset_lots_structure.items():
        account = balance_sheet.get_account(account_name)
        assert set(account.balances.keys()) == set(expected_commodity_lots.keys())
        for commodity, expected_lots in expected_commodity_lots.items():
            balance = account.get_balance(commodity)
            assert len(balance.lots) == len(expected_lots)
            for i in range(len(balance.lots)):
                actual_lot = balance.lots[i]
                expected_lot = expected_lots[i]
                assert actual_lot.acquisition_date == expected_lot.acquisition_date
                assert actual_lot.quantity == expected_lot.quantity
                assert actual_lot.cost_basis_per_unit == expected_lot.cost_basis_per_unit
                assert actual_lot.original_posting == expected_lot.original_posting

def test_calculate_balances_undated_accounts():
    """Tests the calculation of account balances for transactions with undated accounts."""
    transactions = [
        Transaction(
            date=date(2024, 1, 15),
            payee="Groceries",
            postings=[
                Posting(account=AccountName(parts=["expenses", "food"]), amount=Amount(Decimal("50.00"), Commodity("USD"))),
                Posting(account=AccountName(parts=["assets", "bank"]), amount=Amount(Decimal("-50.00"), Commodity("USD"))),
            ],
        ),
        Transaction(
            date=date(2024, 1, 20),
            payee="Salary",
            postings=[
                Posting(account=AccountName(parts=["assets", "bank"]), amount=Amount(Decimal("1500.00"), Commodity("USD"))),
                Posting(account=AccountName(parts=["income", "salary"]), amount=Amount(Decimal("-1500.00"), Commodity("USD"))),
            ],
        ),
        Transaction(
            date=date(2024, 1, 25),
            payee="Transfer",
            postings=[
                Posting(account=AccountName(parts=["assets", "savings"]), amount=Amount(Decimal("200.00"), Commodity("USD"))),
                Posting(account=AccountName(parts=["assets", "bank"]), amount=Amount(Decimal("-200.00"), Commodity("USD"))),
            ],
        ),
    ]

    balance_sheet = calculate_balances_and_lots(transactions)

    # Verify BalanceSheet for undated accounts
    expected_balances = {
        AccountName(parts=["expenses", "food"]): {Commodity("USD"): Amount(Decimal("50.00"), Commodity("USD"))},
        AccountName(parts=["assets", "bank"]): {Commodity("USD"): Amount(Decimal("-50.00") + Decimal("1500.00") - Decimal("200.00"), Commodity("USD"))},
        AccountName(parts=["income", "salary"]): {Commodity("USD"): Amount(Decimal("-1500.00"), Commodity("USD"))},
        AccountName(parts=["assets", "savings"]): {Commodity("USD"): Amount(Decimal("200.00"), Commodity("USD"))},
    }

    assert set(balance_sheet.accounts.keys()) == set(expected_balances.keys())

    for account_name, expected_commodity_balances in expected_balances.items():
        account = balance_sheet.get_account(account_name)
        assert set(account.balances.keys()) == set(expected_commodity_balances.keys())
        for commodity, expected_amount in expected_commodity_balances.items():
            balance = account.get_balance(commodity)
            assert balance.total_amount == expected_amount
            # For undated accounts, there should be no lots
            assert len(balance.lots) == 0
