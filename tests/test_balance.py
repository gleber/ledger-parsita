import pytest
import importlib # Import the importlib module
from decimal import Decimal
from datetime import date

# Import and then reload the src.classes module to ensure the latest version is used
from src import classes
importlib.reload(classes)
from src.classes import AccountName, Commodity, Amount, Cost, CostKind, Posting, Transaction
from src.balance import calculate_balances_and_lots, BalanceSheet, Lot, Account, Balance, CashBalance, AssetBalance
   

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
    # Balances for non-asset accounts should be from postings
    # Balances for asset accounts should be 0 as no lots are added in this test

    # expenses:food
    expenses_food_account = balance_sheet.get_account(AccountName(parts=["expenses", "food"]))
    expenses_food_balance = expenses_food_account.get_balance(Commodity("USD"))
    assert isinstance(expenses_food_balance, CashBalance)
    assert expenses_food_balance.total_amount == Amount(Decimal("50.00"), Commodity("USD"))

    # assets:bank
    assets_bank_account = balance_sheet.get_account(AccountName(parts=["assets", "bank"]))
    assets_bank_balance = assets_bank_account.get_balance(Commodity("USD"))
    assert isinstance(assets_bank_balance, CashBalance) # assets:bank is cash
    assert assets_bank_balance.total_amount == Amount(Decimal("-50.00") + Decimal("1500.00") - Decimal("200.00"), Commodity("USD"))
    # No lots for cash balance
    # assert len(assets_bank_balance.lots) == 0 # This assertion is no longer needed as CashBalance has no lots attribute

    # income:salary
    income_salary_account = balance_sheet.get_account(AccountName(parts=["income", "salary"]))
    income_salary_balance = income_salary_account.get_balance(Commodity("USD"))
    assert isinstance(income_salary_balance, CashBalance)
    assert income_salary_balance.total_amount == Amount(Decimal("-1500.00"), Commodity("USD"))

    # assets:savings
    assets_savings_account = balance_sheet.get_account(AccountName(parts=["assets", "savings"]))
    assets_savings_balance = assets_savings_account.get_balance(Commodity("USD"))
    assert isinstance(assets_savings_balance, CashBalance) # assets:savings is cash
    assert assets_savings_balance.total_amount == Amount(Decimal("200.00"), Commodity("USD"))
    # No lots for cash balance
    # assert len(assets_savings_balance.lots) == 0 # This assertion is no longer needed as CashBalance has no lots attribute

def test_asset_balance_add_lot_updates_balance():
    """Tests that adding a Lot to an AssetBalance updates total_amount and cost_basis_per_unit."""
    commodity = Commodity("TEST")
    balance = AssetBalance(commodity=commodity) # Use AssetBalance

    # Create sample Lots
    lot1 = Lot(
        acquisition_date="2024-05-04",
        quantity=Amount(Decimal("10"), commodity),
        cost_basis_per_unit=Amount(Decimal("100.00"), Commodity("USD")),
        original_posting=Posting(account=AccountName(parts=["assets", "broker", "TEST", "20240504"]), amount=Amount(Decimal("10"), commodity)) # Dummy posting
    )

    lot2 = Lot(
        acquisition_date="2024-05-05",
        quantity=Amount(Decimal("5"), commodity),
        cost_basis_per_unit=Amount(Decimal("110.00"), Commodity("USD")),
        original_posting=Posting(account=AccountName(parts=["assets", "broker", "TEST", "20240505"]), amount=Amount(Decimal("5"), commodity)) # Dummy posting
    )

    # Add lots to the balance (recalculation happens automatically in add_lot)
    balance.add_lot(lot1)

    # Verify total_amount and cost_basis_per_unit after adding lot1
    assert balance.total_amount == Amount(Decimal("10"), commodity)
    assert balance.cost_basis_per_unit == Amount(Decimal("100.00"), Commodity("USD"))
    assert len(balance.lots) == 1
    assert balance.lots[0] == lot1

    balance.add_lot(lot2)

    # Verify total_amount and cost_basis_per_unit after adding lot2 (incremental update)
    expected_total_quantity = Decimal("10") + Decimal("5")
    total_cost = (Decimal("10") * Decimal("100.00")) + (Decimal("5") * Decimal("110.00"))
    expected_cost_basis_per_unit = total_cost / expected_total_quantity

    assert balance.total_amount == Amount(expected_total_quantity, commodity)
    assert balance.cost_basis_per_unit == Amount(expected_cost_basis_per_unit, Commodity("USD"))
    assert len(balance.lots) == 2
    assert balance.lots[1] == lot2



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

    # assets:bank (CashBalance)
    assets_bank_account = balance_sheet.get_account(AccountName(parts=["assets", "bank"]))
    assets_bank_balance = assets_bank_account.get_balance(Commodity("USD"))
    assert isinstance(assets_bank_balance, CashBalance)
    assert assets_bank_balance.total_amount == Amount(Decimal("1000.00") - Decimal("500.00") - Decimal("200.00") - Decimal("400.00"), Commodity("USD"))

    # equity:opening-balances (CashBalance)
    equity_opening_account = balance_sheet.get_account(AccountName(parts=["equity", "opening-balances"]))
    equity_opening_balance = equity_opening_account.get_balance(Commodity("USD"))
    assert isinstance(equity_opening_balance, CashBalance)
    assert equity_opening_balance.total_amount == Amount(Decimal("-1000.00"), Commodity("USD"))

    # assets:broker:FOO:20240201 (AssetBalance)
    foo_account = balance_sheet.get_account(AccountName(parts=["assets", "broker", "FOO", "20240201"]))
    foo_balance = foo_account.get_balance(Commodity("FOO"))
    assert isinstance(foo_balance, AssetBalance)
    assert foo_balance.total_amount == Amount(Decimal("10"), Commodity("FOO"))
    assert foo_balance.cost_basis_per_unit == Amount(Decimal("50.00"), Commodity("USD"))
    assert len(foo_balance.lots) == 1
    assert foo_balance.lots[0].quantity == Amount(Decimal("10"), Commodity("FOO"))
    assert foo_balance.lots[0].cost_basis_per_unit == Amount(Decimal("50.00"), Commodity("USD"))

    # assets:broker:BAR:20240301 (AssetBalance)
    bar_account = balance_sheet.get_account(AccountName(parts=["assets", "broker", "BAR", "20240301"]))
    bar_balance = bar_account.get_balance(Commodity("BAR"))
    assert isinstance(bar_balance, AssetBalance)
    assert bar_balance.total_amount == Amount(Decimal("5"), Commodity("BAR"))
    assert bar_balance.cost_basis_per_unit == Amount(Decimal("40.00"), Commodity("USD"))
    assert len(bar_balance.lots) == 1
    assert bar_balance.lots[0].quantity == Amount(Decimal("5"), Commodity("BAR"))
    assert bar_balance.lots[0].cost_basis_per_unit == Amount(Decimal("40.00"), Commodity("USD"))

    # assets:broker:BAZ:20240401 (AssetBalance)
    baz_account = balance_sheet.get_account(AccountName(parts=["assets", "broker", "BAZ", "20240401"]))
    baz_balance = baz_account.get_balance(Commodity("BAZ"))
    assert isinstance(baz_balance, AssetBalance)
    assert baz_balance.total_amount == Amount(Decimal("20"), Commodity("BAZ"))
    assert baz_balance.cost_basis_per_unit == Amount(Decimal("20.00"), Commodity("USD"))
    assert len(baz_balance.lots) == 1
    assert baz_balance.lots[0].quantity == Amount(Decimal("20"), Commodity("BAZ"))
    assert baz_balance.lots[0].cost_basis_per_unit == Amount(Decimal("20.00"), Commodity("USD"))
