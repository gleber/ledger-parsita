import pytest
from datetime import date
from decimal import Decimal
import re

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
    Cost # Import Cost
)
from src.capital_gains import (
    find_open_transactions,
    find_close_transactions,
)
from src.balance import calculate_balances_and_lots, BalanceSheet # Import necessary functions and classes


# Helper function to create a simple journal for testing
def create_test_journal(transactions_data):
    journal = Journal(entries=[])
    for data in transactions_data:
        postings = []
        for posting_data in data["postings"]:
            amount = None
            if "amount" in posting_data and posting_data["amount"] is not None:
                amount_data = posting_data["amount"]
                if "quantity" in amount_data and "commodity" in amount_data:
                    amount = Amount(
                        quantity=Decimal(str(amount_data["quantity"])),
                        commodity=Commodity(name=amount_data["commodity"]),
                    )
            cost = None
            if "cost" in posting_data and posting_data["cost"] is not None:
                cost_data = posting_data["cost"]
                if "kind" in cost_data and "amount" in cost_data:
                    cost_amount_data = cost_data["amount"]
                    cost_amount = Amount(
                        quantity=Decimal(str(cost_amount_data["quantity"])),
                        commodity=Commodity(name=cost_amount_data["commodity"]),
                    )
                    # Create a Cost object instead of a tuple
                    cost = Cost(kind=CostKind(cost_data["kind"]), amount=cost_amount)

            postings.append(
                Posting(
                    account=AccountName(parts=posting_data["account"].split(":")),
                    amount=amount,
                    cost=cost
                )
            )
        journal.entries.append(
            JournalEntry.create(
                Transaction(
                    date=date.fromisoformat(data["date"]),
                    payee=data["payee"],
                    postings=postings,
                )
            )
        )
    return journal


def test_find_open_transactions():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL",
            "postings": [
                {
                    "account": "assets:stocks:AAPL",
                    "amount": {"quantity": Decimal("10"), "commodity": "AAPL"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-10"), "commodity": "AAPL"},
                },
            ],
        },
        {
            "date": "2023-01-02",
            "payee": "Buy Groceries",
            "postings": [
                {
                    "account": "expenses:food",
                    "amount": {"quantity": Decimal("50"), "commodity": "USD"},
                },
                {
                    "account": "assets:cash",
                    "amount": {"quantity": Decimal("-50"), "commodity": "USD"},
                },
            ],
        },
    ]
    journal = create_test_journal(transactions_data)
    open_txns = find_open_transactions(journal)

    # Expected open transaction is the first one
    assert len(open_txns) == 1
    assert open_txns[0].payee == "Open AAPL"


def test_find_close_transactions():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL",
            "postings": [
                {
                    "account": "assets:stocks:AAPL",
                    "amount": {"quantity": Decimal("10"), "commodity": "AAPL"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-10"), "commodity": "AAPL"},
                },
            ],
        },
        {
            "date": "2023-01-02",
            "payee": "Sell AAPL",
            "postings": [
                {
                    "account": "assets:stocks:AAPL",
                    "amount": {"quantity": Decimal("-5"), "commodity": "AAPL"},
                },
                {
                    "account": "assets:cash",
                    "amount": {"quantity": Decimal("1000"), "commodity": "USD"},
                },
                {
                    "account": "income:capital gains",
                    "amount": {"quantity": Decimal("-100"), "commodity": "USD"},
                },
            ],
        },
        {
            "date": "2023-01-03",
            "payee": "Buy Groceries",
            "postings": [
                {
                    "account": "expenses:food",
                    "amount": {"quantity": Decimal("50"), "commodity": "USD"},
                },
                {
                    "account": "assets:cash",
                    "amount": {"quantity": Decimal("-50"), "commodity": "USD"},
                },
            ],
        },
    ]
    journal = create_test_journal(transactions_data)
    close_txns = find_close_transactions(journal)

    # Expected close transaction is the second one
    assert len(close_txns) == 1
    assert close_txns[0].payee == "Sell AAPL"


def test_find_open_transactions_excludes_cash():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL",
            "postings": [
                {
                    "account": "assets:stocks:AAPL",
                    "amount": {"quantity": Decimal("10"), "commodity": "AAPL"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-10"), "commodity": "AAPL"},
                },
            ],
        },
        {
            "date": "2023-01-02",
            "payee": "Deposit USD",
            "postings": [
                {
                    "account": "assets:cash:USD",
                    "amount": {"quantity": Decimal("1000"), "commodity": "USD"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-1000"), "commodity": "USD"},
                },
            ],
        },
        {
            "date": "2023-01-03",
            "payee": "Deposit PLN",
            "postings": [
                {
                    "account": "assets:cash:PLN",
                    "amount": {"quantity": Decimal("500"), "commodity": "PLN"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-500"), "commodity": "PLN"},
                },
            ],
        },
    ]
    journal = create_test_journal(transactions_data)
    open_txns = find_open_transactions(journal)

    # Expected open transaction is the first one (AAPL), cash transactions should be excluded
    assert len(open_txns) == 1
    assert open_txns[0].payee == "Open AAPL"


def test_find_close_transactions_excludes_cash():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Sell AAPL",
            "postings": [
                {
                    "account": "assets:stocks:AAPL",
                    "amount": {"quantity": Decimal("-5"), "commodity": "AAPL"},
                },
                {
                    "account": "assets:cash",
                    "amount": {"quantity": Decimal("1000"), "commodity": "USD"},
                },
                {
                    "account": "income:capital gains",
                    "amount": {"quantity": Decimal("-100"), "commodity": "USD"},
                },
            ],
        },
        {
            "date": "2023-01-02",
            "payee": "Withdraw USD",
            "postings": [
                {
                    "account": "assets:cash:USD",
                    "amount": {"quantity": Decimal("-200"), "commodity": "USD"},
                },
                {
                    "account": "expenses:withdrawal",
                    "amount": {"quantity": Decimal("200"), "commodity": "USD"},
                },
            ],
        },
        {
            "date": "2023-01-03",
            "payee": "Withdraw PLN",
            "postings": [
                {
                    "account": "assets:cash:PLN",
                    "amount": {"quantity": Decimal("-100"), "commodity": "PLN"},
                },
                {
                    "account": "expenses:withdrawal",
                    "amount": {"quantity": Decimal("100"), "commodity": "PLN"},
                },
            ],
        },
    ]
    journal = create_test_journal(transactions_data)
    close_txns = find_close_transactions(journal)

    # Expected close transaction is the first one (AAPL), cash transactions should be excluded
    assert len(close_txns) == 1
    assert close_txns[0].payee == "Sell AAPL"
