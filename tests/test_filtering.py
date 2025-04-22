import unittest
from datetime import date
from decimal import Decimal
from src.classes import Transaction, Posting, AccountName, Amount, JournalEntry, Journal
from src.filtering import (
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


class TestFiltering(unittest.TestCase):

    def setUp(self):
        # Create some dummy transactions for testing
        self.entries = [
            JournalEntry(
                transaction=Transaction(
                    date=date(2023, 1, 15),
                    payee="Grocery Store",
                    postings=[
                        Posting(
                            account=AccountName(["Expenses", "Food"]),
                            amount=Amount(Decimal("50.00"), "USD"),
                        ),
                        Posting(
                            account=AccountName(["Assets", "Cash"]),
                            amount=Amount(Decimal("-50.00"), "USD"),
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
                            amount=Amount(Decimal("1000.00"), "USD"),
                        ),
                        Posting(
                            account=AccountName(["Income", "Salary"]),
                            amount=Amount(Decimal("-1000.00"), "USD"),
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
                            amount=Amount(Decimal("5.50"), "USD"),
                            tags=[TagFilter("caffeine", None)],
                        ),
                        Posting(
                            account=AccountName(["Assets", "Cash"]),
                            amount=Amount(Decimal("-5.50"), "USD"),
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
                            amount=Amount(Decimal("25.00"), "USD"),
                            tags=[TagFilter("genre", "fiction")],
                        ),
                        Posting(
                            account=AccountName(["Assets", "Bank"]),
                            amount=Amount(Decimal("-25.00"), "USD"),
                        ),
                    ],
                )
            ),
        ]

    def test_query_filter_account(self):
        parse_query("account:Expenses:Food").unwrap()

    def test_filter_by_account(self):
        filtered = filter_entries(self.entries, "account:Expenses:Food")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0].payee, "Grocery Store")
        self.assertEqual(filtered[1].payee, "Coffee Shop")

        filtered = filter_entries(self.entries, "account:Assets:Bank")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0].payee, "Salary")
        self.assertEqual(filtered[1].payee, "Bookstore")

    @unittest.skip("")
    def test_filter_by_date(self):
        filtered = filter_entries(self.entries, "date:2023-01-15")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].payee, "Grocery Store")

        filtered = filter_entries(self.entries, "date:2023-01-01..2023-01-31")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0].payee, "Grocery Store")
        self.assertEqual(filtered[1].payee, "Salary")

        filtered = filter_entries(self.entries, "date:2023-02-01..")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0].payee, "Coffee Shop")
        self.assertEqual(filtered[1].payee, "Bookstore")

        filtered = filter_entries(self.entries, "date:..2023-01-31")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0].payee, "Grocery Store")
        self.assertEqual(filtered[1].payee, "Salary")

    @unittest.skip("")
    def test_filter_by_description(self):
        filtered = filter_entries(self.entries, "desc:Store")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].payee, "Grocery Store")

        filtered = filter_entries(self.entries, "desc:shop")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].payee, "Coffee Shop")

    @unittest.skip("")
    def test_filter_by_amount(self):
        filtered = filter_entries(self.entries, "amount:>100")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].payee, "Salary")

        filtered = filter_entries(self.entries, "amount:<0")
        self.assertEqual(len(filtered), 4)  # All transactions have a negative posting

        filtered = filter_entries(self.entries, "amount:<=5.50")
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0].payee, "Grocery Store")  # -50.00 <= 5.50
        self.assertEqual(
            filtered[1].payee, "Coffee Shop"
        )  # 5.50 <= 5.50 and -5.50 <= 5.50

    @unittest.skip("")
    def test_filter_by_tag(self):
        filtered = filter_entries(self.entries, "tag:caffeine")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].payee, "Coffee Shop")

        filtered = filter_entries(self.entries, "tag:genre:fiction")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].payee, "Bookstore")

        filtered = filter_entries(self.entries, "tag:nonexistent")
        self.assertEqual(len(filtered), 0)

    @unittest.skip("")
    def test_combined_filters(self):
        filtered = filter_entries(
            self.entries, "account:Expenses date:2023-01-01..2023-01-31"
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].payee, "Grocery Store")

        filtered = filter_entries(self.entries, "desc:Shop amount:<=10")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].payee, "Coffee Shop")

    @unittest.skip("")
    def test_invalid_query(self):
        with self.assertRaises(ParseError):
            filter_entries(self.entries, "invalid:filter")

        with self.assertRaises(ParseError):
            filter_entries(
                self.entries, "date:2023/01/01"
            )  # Incorrect date format

        with self.assertRaises(ParseError):
            filter_entries(self.entries, "amount:>>100")  # Invalid operator


if __name__ == "__main__":
    unittest.main()
