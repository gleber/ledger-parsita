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
)
from src.capital_gains import (
    find_open_transactions,
    find_close_transactions,
    find_open_transactions_with_dated_subaccounts,
    find_close_transactions_without_dated_subaccounts,
    match_fifo,
)


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
            postings.append(
                Posting(
                    account=AccountName(parts=posting_data["account"].split(":")),
                    amount=amount,
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


def test_find_open_transactions_with_dated_subaccounts():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL Dated",
            "postings": [
                {
                    "account": "assets:stocks:AAPL:20230101",
                    "amount": {"quantity": Decimal("10"), "commodity": "AAPL"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-10"), "commodity": "AAPL"},
                },
            ],
        },
        {
            "date": "2023-01-05",
            "payee": "Open MSFT Non-Dated",
            "postings": [
                {
                    "account": "assets:stocks:MSFT",
                    "amount": {"quantity": Decimal("15"), "commodity": "MSFT"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-15"), "commodity": "MSFT"},
                },
            ],
        },
        {
            "date": "2023-01-20",
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
    ]
    journal = create_test_journal(transactions_data)
    open_txns = find_open_transactions_with_dated_subaccounts(journal)

    # Expected open transaction with dated subaccount is the first one
    assert len(open_txns) == 1
    assert open_txns[0].payee == "Open AAPL Dated"


def test_find_close_transactions_without_dated_subaccounts():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL Dated",
            "postings": [
                {
                    "account": "assets:stocks:AAPL:20230101",
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
            "payee": "Sell MSFT Non-Dated",
            "postings": [
                {
                    "account": "assets:stocks:MSFT",
                    "amount": {"quantity": Decimal("-5"), "commodity": "MSFT"},
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
    close_txns = find_close_transactions_without_dated_subaccounts(journal)

    # Expected close transaction without dated subaccount is the second one
    assert len(close_txns) == 1
    assert close_txns[0].payee == "Sell MSFT Non-Dated"


def test_match_fifo_simple():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL Lot 1",
            "postings": [
                {
                    "account": "assets:stocks:AAPL:20230101",
                    "amount": {"quantity": Decimal("10"), "commodity": "AAPL"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-10"), "commodity": "AAPL"},
                },
            ],
        },
        {
            "date": "2023-01-15",
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
    ]
    journal = create_test_journal(transactions_data)
    match_results = match_fifo(journal)

    assert len(match_results) == 1
    match = match_results[0]
    assert match.matched_quantity == Decimal("5")
    assert (
        match.closing_posting.amount is not None
        and match.closing_posting.amount.quantity == Decimal("-5")
    )
    assert (
        match.opening_lot.posting.amount is not None
        and match.opening_lot.posting.amount.quantity == Decimal("10")
    )
    assert match.opening_lot.remaining_quantity == Decimal("5")  # Remaining in the lot


def test_match_fifo_multiple_opens_single_close():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL Lot 1",
            "postings": [
                {
                    "account": "assets:stocks:AAPL:20230101",
                    "amount": {"quantity": Decimal("10"), "commodity": "AAPL"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-10"), "commodity": "AAPL"},
                },
            ],
        },
        {
            "date": "2023-01-05",
            "payee": "Open AAPL Lot 2",
            "postings": [
                {
                    "account": "assets:stocks:AAPL:20230105",
                    "amount": {"quantity": Decimal("15"), "commodity": "AAPL"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-15"), "commodity": "AAPL"},
                },
            ],
        },
        {
            "date": "2023-01-20",
            "payee": "Sell AAPL",
            "postings": [
                {
                    "account": "assets:stocks:AAPL",
                    "amount": {"quantity": Decimal("-12"), "commodity": "AAPL"},
                },
                {
                    "account": "assets:cash",
                    "amount": {"quantity": Decimal("2000"), "commodity": "USD"},
                },
                {
                    "account": "income:capital gains",
                    "amount": {"quantity": Decimal("-200"), "commodity": "USD"},
                },
            ],
        },
    ]
    journal = create_test_journal(transactions_data)
    match_results = match_fifo(journal)

    assert len(match_results) == 2

    # First match should be with the oldest lot (Lot 1)
    match1 = match_results[0]
    assert match1.matched_quantity == Decimal("10")
    assert (
        match1.closing_posting.amount is not None
        and match1.closing_posting.amount.quantity == Decimal("-12")
    )
    assert (
        match1.opening_lot.posting.amount is not None
        and match1.opening_lot.posting.amount.quantity == Decimal("10")
    )
    assert match1.opening_lot.remaining_quantity == Decimal("0")

    # Second match should be with the next oldest lot (Lot 2)
    match2 = match_results[1]
    assert match2.matched_quantity == Decimal("2")
    assert (
        match2.closing_posting.amount is not None
        and match2.closing_posting.amount.quantity == Decimal("-12")
    )
    assert (
        match2.opening_lot.posting.amount is not None
        and match2.opening_lot.posting.amount.quantity == Decimal("15")
    )
    assert match2.opening_lot.remaining_quantity == Decimal("13")


def test_match_fifo_single_open_multiple_closes():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL Lot 1",
            "postings": [
                {
                    "account": "assets:stocks:AAPL:20230101",
                    "amount": {"quantity": Decimal("20"), "commodity": "AAPL"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-20"), "commodity": "AAPL"},
                },
            ],
        },
        {
            "date": "2023-01-15",
            "payee": "Sell AAPL Part 1",
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
            "date": "2023-01-20",
            "payee": "Sell AAPL Part 2",
            "postings": [
                {
                    "account": "assets:stocks:AAPL",
                    "amount": {"quantity": Decimal("-8"), "commodity": "AAPL"},
                },
                {
                    "account": "assets:cash",
                    "amount": {"quantity": Decimal("1500"), "commodity": "USD"},
                },
                {
                    "account": "income:capital gains",
                    "amount": {"quantity": Decimal("-150"), "commodity": "USD"},
                },
            ],
        },
    ]
    journal = create_test_journal(transactions_data)
    match_results = match_fifo(journal)

    assert len(match_results) == 2

    # Both matches should be with the single open lot
    match1 = match_results[0]
    assert match1.matched_quantity == Decimal("5")
    assert (
        match1.closing_posting.amount is not None
        and match1.closing_posting.amount.quantity == Decimal("-5")
    )
    assert (
        match1.opening_lot.posting.amount is not None
        and match1.opening_lot.posting.amount.quantity == Decimal("20")
    )
    assert match1.opening_lot.remaining_quantity == Decimal(
        "7"
    )  # Remaining after both sales

    match2 = match_results[1]
    assert match2.matched_quantity == Decimal("8")
    assert (
        match2.closing_posting.amount is not None
        and match2.closing_posting.amount.quantity == Decimal("-8")
    )
    assert (
        match2.opening_lot.posting.amount is not None
        and match2.opening_lot.posting.amount.quantity == Decimal("20")
    )
    assert match2.opening_lot.remaining_quantity == Decimal(
        "7"
    )  # Remaining after second sale


def test_match_fifo_multiple_assets():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL",
            "postings": [
                {
                    "account": "assets:stocks:AAPL:20230101",
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
            "payee": "Open MSFT",
            "postings": [
                {
                    "account": "assets:stocks:MSFT:20230102",
                    "amount": {"quantity": Decimal("15"), "commodity": "MSFT"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-15"), "commodity": "MSFT"},
                },
            ],
        },
        {
            "date": "2023-01-15",
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
            "date": "2023-01-20",
            "payee": "Sell MSFT",
            "postings": [
                {
                    "account": "assets:stocks:MSFT",
                    "amount": {"quantity": Decimal("-8"), "commodity": "MSFT"},
                },
                {
                    "account": "assets:cash",
                    "amount": {"quantity": Decimal("1500"), "commodity": "USD"},
                },
                {
                    "account": "income:capital gains",
                    "amount": {"quantity": Decimal("-150"), "commodity": "USD"},
                },
            ],
        },
    ]
    journal = create_test_journal(transactions_data)
    match_results = match_fifo(journal)

    assert len(match_results) == 2

    # Verify matches for AAPL
    aapl_match = next(
        (
            m
            for m in match_results
            if m.closing_posting.amount is not None
            and m.closing_posting.amount.commodity.name == "AAPL"
        ),
        None,
    )
    assert aapl_match is not None
    assert aapl_match.matched_quantity == Decimal("5")
    assert (
        aapl_match.opening_lot.posting.amount is not None
        and aapl_match.opening_lot.posting.amount.commodity.name == "AAPL"
    )

    # Verify matches for MSFT
    msft_match = next(
        (
            m
            for m in match_results
            if m.closing_posting.amount is not None
            and m.closing_posting.amount.commodity.name == "MSFT"
        ),
        None,
    )
    assert msft_match is not None
    assert msft_match.matched_quantity == Decimal("8")
    assert (
        msft_match.opening_lot.posting.amount is not None
        and msft_match.opening_lot.posting.amount.commodity.name == "MSFT"
    )


def test_match_fifo_excludes_non_dated_opens():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL Dated",
            "postings": [
                {
                    "account": "assets:stocks:AAPL:20230101",
                    "amount": {"quantity": Decimal("10"), "commodity": "AAPL"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-10"), "commodity": "AAPL"},
                },
            ],
        },
        {
            "date": "2023-01-05",
            "payee": "Open MSFT Non-Dated",
            "postings": [
                {
                    "account": "assets:stocks:MSFT",
                    "amount": {"quantity": Decimal("15"), "commodity": "MSFT"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-15"), "commodity": "MSFT"},
                },
            ],
        },
        {
            "date": "2023-01-20",
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
    ]
    journal = create_test_journal(transactions_data)
    match_results = match_fifo(journal)

    # Only the AAPL dated open should be considered for matching
    assert len(match_results) == 1
    match = match_results[0]
    assert match.matched_quantity == Decimal("5")
    assert (
        match.closing_posting.amount is not None
        and match.closing_posting.amount.commodity.name == "AAPL"
    )
    assert match.opening_lot.posting.account.isDatedSubaccount() is True


def test_match_fifo_excludes_dated_closes():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL Lot 1",
            "postings": [
                {
                    "account": "assets:stocks:AAPL:20230101",
                    "amount": {"quantity": Decimal("10"), "commodity": "AAPL"},
                },
                {
                    "account": "equity:opening balances",
                    "amount": {"quantity": Decimal("-10"), "commodity": "AAPL"},
                },
            ],
        },
        {
            "date": "2023-01-15",
            "payee": "Sell AAPL Dated",
            "postings": [
                {
                    "account": "assets:stocks:AAPL:20230101",
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
    ]
    journal = create_test_journal(transactions_data)
    match_results = match_fifo(journal)

    # Dated closes should not trigger matching
    assert len(match_results) == 0


def test_match_fifo_excludes_cash_transactions():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Open AAPL Lot 1",
            "postings": [
                {
                    "account": "assets:stocks:AAPL:20230101",
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
            "date": "2023-01-15",
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
            "date": "2023-01-20",
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
    match_results = match_fifo(journal)

    # Only the AAPL non-cash transactions should be considered for matching
    assert len(match_results) == 1
    match = match_results[0]
    assert match.matched_quantity == Decimal("5")
    assert (
        match.closing_posting.amount is not None
        and match.closing_posting.amount.commodity.name == "AAPL"
    )
    assert (
        match.opening_lot.posting.amount is not None
        and match.opening_lot.posting.amount.commodity.name == "AAPL"
    )


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


def test_find_close_transactions_without_dated_subaccounts_excludes_cash():
    transactions_data = [
        {
            "date": "2023-01-01",
            "payee": "Sell MSFT Non-Dated",
            "postings": [
                {
                    "account": "assets:stocks:MSFT",
                    "amount": {"quantity": Decimal("-5"), "commodity": "MSFT"},
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
    close_txns = find_close_transactions_without_dated_subaccounts(journal)

    # Expected close transaction without dated subaccount is the first one (MSFT), cash transactions should be excluded
    assert len(close_txns) == 1
    assert close_txns[0].payee == "Sell MSFT Non-Dated"
