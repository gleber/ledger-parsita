import pytest
import importlib # Import the importlib module
from decimal import Decimal
from datetime import date
from pathlib import Path # Import Path

from src.classes import AccountName, Commodity, Amount, Cost, CostKind, Posting, Transaction
from src.balance import BalanceSheet, Lot, Account, Balance, CashBalance, AssetBalance # Updated import
from src.classes import Journal # Import Journal

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

    balance_sheet = BalanceSheet.from_transactions(transactions) # Updated function call

    # Verify BalanceSheet for undated accounts
    # Balances for non-asset accounts should be from postings
    # Balances for asset accounts should be 0 as no lots are added in this test

    # expenses:food
    expenses_food_account = balance_sheet.get_account(AccountName(parts=["expenses", "food"]))
    expenses_food_balance = expenses_food_account.get_own_balance(Commodity("USD"))
    assert isinstance(expenses_food_balance, CashBalance)
    assert expenses_food_balance.total_amount == Amount(Decimal("50.00"), Commodity("USD"))

    # assets:bank
    assets_bank_account = balance_sheet.get_account(AccountName(parts=["assets", "bank"]))
    assets_bank_balance = assets_bank_account.get_own_balance(Commodity("USD"))
    assert isinstance(assets_bank_balance, CashBalance) # assets:bank is cash
    assert assets_bank_balance.total_amount == Amount(Decimal("-50.00") + Decimal("1500.00") - Decimal("200.00"), Commodity("USD"))
    # No lots for cash balance
    # assert len(assets_bank_balance.lots) == 0 # This assertion is no longer needed as CashBalance has no lots attribute

    # income:salary
    income_salary_account = balance_sheet.get_account(AccountName(parts=["income", "salary"]))
    income_salary_balance = income_salary_account.get_own_balance(Commodity("USD"))
    assert isinstance(income_salary_balance, CashBalance)
    assert income_salary_balance.total_amount == Amount(Decimal("-1500.00"), Commodity("USD"))

    # assets:savings
    assets_savings_account = balance_sheet.get_account(AccountName(parts=["assets", "savings"]))
    assets_savings_balance = assets_savings_account.get_own_balance(Commodity("USD"))
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



def test_balance_sheet_building_with_assets(): # Renamed test function
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

    balance_sheet = BalanceSheet.from_transactions(transactions) # Updated function call

    # assets:bank (CashBalance)
    assets_bank_account = balance_sheet.get_account(AccountName(parts=["assets", "bank"]))
    assets_bank_balance = assets_bank_account.get_own_balance(Commodity("USD"))
    assert isinstance(assets_bank_balance, CashBalance)
    assert assets_bank_balance.total_amount == Amount(Decimal("1000.00") - Decimal("500.00") - Decimal("200.00") - Decimal("400.00"), Commodity("USD"))

    # equity:opening-balances (CashBalance)
    equity_opening_account = balance_sheet.get_account(AccountName(parts=["equity", "opening-balances"]))
    equity_opening_balance = equity_opening_account.get_own_balance(Commodity("USD"))
    assert isinstance(equity_opening_balance, CashBalance)
    assert equity_opening_balance.total_amount == Amount(Decimal("-1000.00"), Commodity("USD"))

    # assets:broker:FOO:20240201 (AssetBalance)
    foo_account = balance_sheet.get_account(AccountName(parts=["assets", "broker", "FOO", "20240201"]))
    foo_balance = foo_account.get_own_balance(Commodity("FOO"))
    assert isinstance(foo_balance, AssetBalance)
    assert foo_balance.total_amount == Amount(Decimal("10"), Commodity("FOO"))
    assert foo_balance.cost_basis_per_unit == Amount(Decimal("50.00"), Commodity("USD"))
    assert len(foo_balance.lots) == 1
    assert foo_balance.lots[0].quantity == Amount(Decimal("10"), Commodity("FOO"))
    assert foo_balance.lots[0].cost_basis_per_unit == Amount(Decimal("50.00"), Commodity("USD"))

    # assets:broker:BAR:20240301 (AssetBalance)
    bar_account = balance_sheet.get_account(AccountName(parts=["assets", "broker", "BAR", "20240301"]))
    bar_balance = bar_account.get_own_balance(Commodity("BAR"))
    assert isinstance(bar_balance, AssetBalance)
    assert bar_balance.total_amount == Amount(Decimal("5"), Commodity("BAR"))
    assert bar_balance.cost_basis_per_unit == Amount(Decimal("40.00"), Commodity("USD"))
    assert len(bar_balance.lots) == 1
    assert bar_balance.lots[0].quantity == Amount(Decimal("5"), Commodity("BAR"))
    assert bar_balance.lots[0].cost_basis_per_unit == Amount(Decimal("40.00"), Commodity("USD"))

    # assets:broker:BAZ:20240401 (AssetBalance)
    baz_account = balance_sheet.get_account(AccountName(parts=["assets", "broker", "BAZ", "20240401"]))
    baz_balance = baz_account.get_own_balance(Commodity("BAZ"))
    assert isinstance(baz_balance, AssetBalance)
    assert baz_balance.total_amount == Amount(Decimal("20"), Commodity("BAZ"))
    assert baz_balance.cost_basis_per_unit == Amount(Decimal("20.00"), Commodity("USD"))
    assert len(baz_balance.lots) == 1
    assert baz_balance.lots[0].quantity == Amount(Decimal("20"), Commodity("BAZ"))
    assert baz_balance.lots[0].cost_basis_per_unit == Amount(Decimal("20.00"), Commodity("USD"))


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
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap() # Updated call
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call

    # Verify the remaining quantity of the lot
    aapl_account = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230101"]))
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
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap() # Updated call
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call

    # Verify the remaining quantity of the lots
    aapl_account_lot1 = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230101"]))
    aapl_balance_lot1 = aapl_account_lot1.get_own_balance(Commodity("AAPL"))
    assert isinstance(aapl_balance_lot1, AssetBalance)
    assert len(aapl_balance_lot1.lots) == 1
    assert aapl_balance_lot1.lots[0].remaining_quantity == Decimal("0") # 10 initial - 10 matched

    aapl_account_lot2 = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230105"]))
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
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap() # Updated call
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call

    # Verify the remaining quantity of the lot
    aapl_account_lot1 = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230101"]))
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
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap() # Updated call
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call

    # Verify remaining quantities
    aapl_account = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230101"]))
    aapl_balance = aapl_account.get_own_balance(Commodity("AAPL"))
    assert isinstance(aapl_balance, AssetBalance)
    assert len(aapl_balance.lots) == 1
    assert aapl_balance.lots[0].remaining_quantity == Decimal("5") # 10 initial - 5 sold

    msft_account = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "MSFT", "20230102"]))
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
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap() # Updated call
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call

    # No capital gains should be calculated for non-asset closing postings
    income_account_name = AccountName(parts=["income", "capital_gains"])
    income_account = balance_sheet.get_account(income_account_name)
    # The account might not exist if no gains were calculated, so check if it exists first
    if income_account is not None:
        income_balance = income_account.get_own_balance(Commodity("USD"))
        assert income_balance.total_amount.quantity == Decimal("0")

    # Verify remaining quantity of the lot (should be unchanged)
    aapl_account = balance_sheet.get_account(AccountName(parts=["assets", "stocks", "AAPL", "20230101"]))
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
    journal = Journal.parse_from_content(journal_string, Path("a.journal")).unwrap() # Updated call
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call

    # Verify the remaining quantity of the lot
    btc_account = balance_sheet.get_account(AccountName(parts=["assets", "crypto", "BTC", "20230101"]))
    btc_balance = btc_account.get_own_balance(Commodity("BTC"))
    assert isinstance(btc_balance, AssetBalance)
    assert len(btc_balance.lots) == 1
    assert btc_balance.lots[0].remaining_quantity == Decimal("0.5") # 1 initial - 0.5 sold
