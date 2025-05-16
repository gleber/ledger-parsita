import pytest
from datetime import date
from decimal import Decimal
from src.classes import (
    Transaction,
    Posting,
    AccountName,
    Amount,
    Commodity,
    JournalEntry,
    Tag,
)
from src.journal import Journal
from src.filtering import (
    matches_query,
    filter_entries,
    AccountFilter,
    DateFilter,
    DescriptionFilter,
    AmountFilter,
    TagFilter,
    FilterQueryParsers,
    parse_query,
)
from parsita import ParseError
from returns.result import Failure
from returns.contrib.pytest import ReturnsAsserts


@pytest.fixture
def sample_entries():
    # Create some dummy transactions for testing
    return [
        JournalEntry(
            transaction=Transaction(
                date=date(2023, 1, 15),
                payee="Grocery Store",
                postings=[
                    Posting(
                        account=AccountName(["Expenses", "Food"]),
                        amount=Amount(Decimal("50.00"), Commodity("USD")),
                    ),
                    Posting(
                        account=AccountName(["Assets", "Cash"]),
                        amount=Amount(Decimal("-50.00"), Commodity("USD")),
                    ),
                ],
            )
        ),
        JournalEntry(
            transaction=Transaction(
                date=date(2023, 1, 20),
                payee="Salary",
                postings=[
                    Posting(
                        account=AccountName(["Assets", "Bank"]),
                        amount=Amount(Decimal("1000.00"), Commodity("USD")),
                    ),
                    Posting(
                        account=AccountName(["Income", "Salary"]),
                        amount=Amount(Decimal("-1000.00"), Commodity("USD")),
                    ),
                ],
            )
        ),
        JournalEntry(
            transaction=Transaction(
                date=date(2023, 2, 10),
                payee="Coffee Shop",
                postings=[
                    Posting(
                        account=AccountName(["Expenses", "Food", "Coffee"]),
                        amount=Amount(Decimal("5.50"), Commodity("USD")),
                        tags=[Tag("caffeine", None)],
                    ),
                    Posting(
                        account=AccountName(["Assets", "Cash"]),
                        amount=Amount(Decimal("-5.50"), Commodity("USD")),
                    ),
                ],
            )
        ),
        JournalEntry(
            transaction=Transaction(
                date=date(2023, 2, 15),
                payee="Bookstore",
                postings=[
                    Posting(
                        account=AccountName(["Expenses", "Books"]),
                        amount=Amount(Decimal("25.00"), Commodity("USD")),
                        tags=[Tag("genre", "fiction")],
                    ),
                    Posting(
                        account=AccountName(["Assets", "Bank"]),
                        amount=Amount(Decimal("-25.00"), Commodity("USD")),
                    ),
                ],
            )
        ),
    ]


def test_query_filter_account():
    parse_query("account:Expenses:Food").unwrap()

def test_filter_by_account(sample_entries):
    filtered = filter_entries(sample_entries, "account:Expenses:Food").unwrap()
    assert len(filtered) == 2
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Grocery Store"
    assert filtered[1].transaction
    assert filtered[1].transaction.payee == "Coffee Shop"

    filtered = filter_entries(sample_entries, "account:Assets:Bank").unwrap()
    assert len(filtered) == 2
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Salary"
    assert filtered[1].transaction
    assert filtered[1].transaction.payee == "Bookstore"


def test_filter_by_date(sample_entries):
    filtered = filter_entries(sample_entries, "date:2023-01-15").unwrap()
    assert len(filtered) == 1
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Grocery Store"

    filtered = filter_entries(sample_entries, "date:2023-01-01..2023-01-31").unwrap()
    assert len(filtered) == 2
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Grocery Store"
    assert filtered[1].transaction
    assert filtered[1].transaction.payee == "Salary"

    filtered = filter_entries(sample_entries, "date:2023-02-01..").unwrap()
    assert len(filtered) == 2
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Coffee Shop"
    assert filtered[1].transaction
    assert filtered[1].transaction.payee == "Bookstore"

    filtered = filter_entries(sample_entries, "date:..2023-01-31").unwrap()
    assert len(filtered) == 2
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Grocery Store"
    assert filtered[1].transaction
    assert filtered[1].transaction.payee == "Salary"


def test_filter_by_description(sample_entries):
    filtered = filter_entries(sample_entries, "desc:Store").unwrap()
    assert len(filtered) == 2
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Grocery Store"
    assert filtered[1].transaction
    assert filtered[1].transaction.payee == "Bookstore"

    filtered = filter_entries(sample_entries, "desc:shop").unwrap()
    assert len(filtered) == 1
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Coffee Shop"


def test_filter_by_amount(sample_entries):
    filtered = filter_entries(sample_entries, "amount:>100").unwrap()
    assert len(filtered) == 1
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Salary"

    filtered = filter_entries(sample_entries, "amount:<0").unwrap()
    assert len(filtered) == 4  # All transactions have a negative posting

    filtered = filter_entries(sample_entries, "amount:<=5.50").unwrap()
    assert len(filtered) == 4
    # All transactions have at least one posting with amount <= 5.50


def test_filter_by_tag(sample_entries):
    assert parse_query("tag:caffeine:").unwrap() == [
        TagFilter(name="caffeine", value=None)
    ]
    filtered = filter_entries(sample_entries, "tag:caffeine:").unwrap()
    assert len(filtered) == 1
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Coffee Shop"

    filtered = filter_entries(sample_entries, "tag:genre:fiction").unwrap()
    assert len(filtered) == 1
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Bookstore"

    filtered = filter_entries(sample_entries, "tag:nonexistent").unwrap()
    assert len(filtered) == 0


def test_combined_filters(sample_entries):
    filtered = filter_entries(
        sample_entries, "account:Expenses date:2023-01-01..2023-01-31"
    ).unwrap()
    assert len(filtered) == 1
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Grocery Store"

    filtered = filter_entries(sample_entries, "desc:Shop amount:<=10").unwrap()
    assert len(filtered) == 1
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Coffee Shop"


def test_filter_by_before_date(sample_entries):
    # before:YYYY-MM-DD
    filtered = filter_entries(sample_entries, "before:2023-01-20").unwrap()
    assert len(filtered) == 1
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Grocery Store"

    # before:YYYY-MM
    filtered = filter_entries(sample_entries, "before:2023-02").unwrap()
    assert len(filtered) == 2
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Grocery Store"
    assert filtered[1].transaction
    assert filtered[1].transaction.payee == "Salary"

    # before:YYYY
    filtered = filter_entries(sample_entries, "before:2024").unwrap()
    assert len(filtered) == 4 # All entries are before 2024

    filtered = filter_entries(sample_entries, "before:2023-01-15").unwrap()
    assert len(filtered) == 0 # No entries before 2023-01-15

def test_filter_by_after_date(sample_entries):
    # after:YYYY-MM-DD
    filtered = filter_entries(sample_entries, "after:2023-01-20").unwrap()
    assert len(filtered) == 2
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Coffee Shop"
    assert filtered[1].transaction
    assert filtered[1].transaction.date == date(2023, 2, 15)

    # after:YYYY-MM
    filtered = filter_entries(sample_entries, "after:2023-01").unwrap()
    assert len(filtered) == 2
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Coffee Shop"
    assert filtered[1].transaction
    assert filtered[1].transaction.payee == "Bookstore"

    # after:YYYY
    filtered = filter_entries(sample_entries, "after:2022").unwrap()
    assert len(filtered) == 4 # All entries are after 2022

    filtered = filter_entries(sample_entries, "after:2023-02-15").unwrap()
    assert len(filtered) == 0 # No entries after 2023-02-15

def test_filter_by_period(sample_entries):
    # period:YYYY-MM-DD
    filtered = filter_entries(sample_entries, "period:2023-01-15").unwrap()
    assert len(filtered) == 1
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Grocery Store"

    # period:YYYY-MM
    filtered = filter_entries(sample_entries, "period:2023-01").unwrap()
    assert len(filtered) == 2
    assert filtered[0].transaction
    assert filtered[0].transaction.payee == "Grocery Store"
    assert filtered[1].transaction
    assert filtered[1].transaction.payee == "Salary"

    # period:YYYY
    filtered = filter_entries(sample_entries, "period:2023").unwrap()
    assert len(filtered) == 4 # All entries are in 2023

    filtered = filter_entries(sample_entries, "period:2024").unwrap()
    assert len(filtered) == 0 # No entries in 2024

def test_invalid_query(sample_entries):
    result = filter_entries(sample_entries, "invalid:filter")
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), ParseError)

    result = filter_entries(sample_entries, "date:2023/01/01")  # Incorrect date format
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), ParseError)

    result = filter_entries(sample_entries, "amount:>>100")  # Invalid operator
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), ParseError)
