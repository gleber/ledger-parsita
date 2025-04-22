from pathlib import Path
import unittest
import sys
import os
from datetime import date as date_class, time as time_class # Import time
from decimal import Decimal

from parsita import Success, Failure

# Add the parent directory of src to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.hledger_parser import HledgerParsers, parse_hledger_journal
from src.classes import (
    CommodityDirective,
    CostKind,
    Include,
    Journal,
    JournalEntry,
    Status,
    AccountName,
    Commodity,
    Amount,
    Cost,
    Tag,
    Posting,
    Transaction,
    MarketPrice,
    Comment, # Import Comment
)


class TestHledgerParsers(unittest.TestCase):

    def test_date_parser(self):
        result = HledgerParsers.date.parse("2013-12-03")
        self.assertEqual(result.unwrap(), date_class(2013, 12, 3))

    def test_date_parser_failure(self):
        result = HledgerParsers.date.parse("invalid-date")
        self.assertTrue(isinstance(result, Failure))
        # Assert that the string representation of the ParseError contains expected information
        # Access the failure message without unwrapping, which would raise an exception
        error_message = str(result.failure())
        self.assertIn("Expected", error_message)
        self.assertIn("date", error_message)

    def test_status_parser(self):
        result_cleared = HledgerParsers.status.parse("*")
        self.assertEqual(result_cleared.unwrap(), Status.Cleared)

        result_unmarked = HledgerParsers.status.parse("")
        self.assertEqual(result_unmarked.unwrap(), Status.Unmarked)

    def test_payee_parser(self):
        result = HledgerParsers.payee.parse("Main Account Deposit  USD")
        self.assertEqual(result.unwrap(), "Main Account Deposit  USD")

    def test_account_name_parser(self):
        result = HledgerParsers.account_name.parse("assets:broker:bitstamp")
        parsed_account_name = result.unwrap()
        self.assertEqual(parsed_account_name.parts, ["assets", "broker", "bitstamp"])

    def test_amount_value_parser(self):
        result = HledgerParsers.amount_value.parse("1,349.20")
        self.assertEqual(result.unwrap(), Decimal("1349.20"))

        result_negative = HledgerParsers.amount_value.parse("-171.00")
        self.assertEqual(result_negative.unwrap(), Decimal("-171.00"))

    def test_cost(self):
        result = HledgerParsers.cost.parse("@ 1 USD").unwrap()
        self.assertEqual(
            result.strip_loc(),
            Cost(
                kind=CostKind.UnitCost,
                amount=Amount(quantity=Decimal("1"), commodity=Commodity("USD")),
            ),
        )

    def test_cost_long(self):
        result = HledgerParsers.cost.parse("@ 19,881.00134 PseudoUSD").unwrap()
        self.assertEqual(
            result.strip_loc(),
            Cost(
                kind=CostKind.UnitCost,
                amount=Amount(
                    quantity=Decimal("19881.00134"), commodity=Commodity("PseudoUSD")
                ),
            ),
        )

    def test_currency_parser(self):
        result = HledgerParsers.currency.parse("USD")
        parsed_currency = result.unwrap()
        self.assertEqual(parsed_currency.name, "USD")
        self.assertIsNotNone(parsed_currency.source_location)
        self.assertEqual(parsed_currency.source_location.offset, 0)
        self.assertEqual(parsed_currency.source_location.length, len("USD"))
        self.assertEqual(parsed_currency.source_location.filename, "")

    def test_currency_parser_quoted(self):
        result = HledgerParsers.currency.parse('"TSLA260116c200"')
        parsed_currency = result.unwrap()
        self.assertEqual(parsed_currency.name, "TSLA260116c200")
        self.assertIsNotNone(parsed_currency.source_location)
        self.assertEqual(parsed_currency.source_location.offset, 0)
        self.assertEqual(
            parsed_currency.source_location.length, len('"TSLA260116c200"')
        )
        self.assertEqual(parsed_currency.source_location.filename, "")

    def test_currency_parser_quoted_with_spaces(self):
        result = HledgerParsers.currency.parse('"Some Commodity With Spaces"')
        parsed_currency = result.unwrap()
        self.assertEqual(parsed_currency.name, "Some Commodity With Spaces")
        self.assertIsNotNone(parsed_currency.source_location)
        self.assertEqual(parsed_currency.source_location.offset, 0)
        self.assertEqual(
            parsed_currency.source_location.length, len('"Some Commodity With Spaces"')
        )
        self.assertEqual(parsed_currency.source_location.filename, "")

    def test_amount_parser_failure(self):
        result = HledgerParsers.amount.parse("invalid amount")
        self.assertTrue(isinstance(result, Failure))
        # Access the failure message without unwrapping, which would raise an exception
        error_message = str(result.failure())
        self.assertIn("Expected", error_message)
        self.assertIn("amount", error_message)

    def test_amount_parser1(self):
        result_with_currency = HledgerParsers.amount.parse("349 USD")
        parsed_amount_with_currency = result_with_currency.unwrap()
        self.assertEqual(parsed_amount_with_currency.quantity, Decimal("349"))
        self.assertEqual(parsed_amount_with_currency.commodity.name, "USD")

    def test_amount_parser2(self):
        result_with_currency = HledgerParsers.amount.parse("1,349.20 USD")
        parsed_amount_with_currency = result_with_currency.unwrap()
        self.assertEqual(parsed_amount_with_currency.quantity, Decimal("1349.20"))
        self.assertEqual(parsed_amount_with_currency.commodity.name, "USD")

    def test_amount_parser3(self):
        result_without_currency = HledgerParsers.amount.parse("-171.00")
        parsed_amount_without_currency = result_without_currency.unwrap()
        self.assertEqual(parsed_amount_without_currency.quantity, Decimal("-171.00"))
        self.assertEqual(parsed_amount_without_currency.commodity.name, "")

    def test_price_cost_parser(self):
        result_at = HledgerParsers.cost.parse("@ 855 USD")
        parsed_price_at = result_at.unwrap()
        self.assertEqual(parsed_price_at.amount.quantity, Decimal("855"))
        self.assertEqual(parsed_price_at.amount.commodity.name, "USD")

        result_at_at = HledgerParsers.cost.parse("@@ 4,972.04 USD")
        parsed_price_at_at = result_at_at.unwrap()
        self.assertEqual(parsed_price_at_at.amount.quantity, Decimal("4972.04"))
        self.assertEqual(parsed_price_at_at.amount.commodity.name, "USD")

    def test_posting_parser_short(self):
        # Missing amount
        posting_text = "assets:broker:bitstamp"
        result = HledgerParsers.posting.parse(posting_text).unwrap()
        self.assertEqual(
            result.strip_loc(),
            Posting(account=AccountName(parts=["assets", "broker", "bitstamp"])),
        )

    def test_posting_parser(self):
        # Example posting from examples/all.txt: assets:broker:bitstamp       1,349.20 USD
        posting_text = "assets:broker:bitstamp  1,349.20 USD"
        result = HledgerParsers.posting.parse(posting_text)
        parsed_posting = result.unwrap()
        # The posting parser returns a tuple, need to access elements by index
        self.assertEqual(
            parsed_posting.account.strip_loc(),
            AccountName(parts=["assets", "broker", "bitstamp"]),
        )
        self.assertEqual(
            parsed_posting.amount.strip_loc(),
            Amount(quantity=Decimal("1349.20"), commodity=Commodity(name="USD")),
        )
        self.assertEqual(
            parsed_posting.strip_loc(),
            Posting(
                account=AccountName(parts=["assets", "broker", "bitstamp"]),
                amount=Amount(
                    quantity=Decimal("1349.20"), commodity=Commodity(name="USD")
                ),
            ),
        )
        self.assertIsNotNone(parsed_posting.source_location)
        self.assertEqual(parsed_posting.source_location.offset, 0)
        self.assertEqual(
            parsed_posting.source_location.length, len(posting_text)
        )  # +1 for the newline consumed by posting parser
        self.assertEqual(parsed_posting.source_location.filename, "")

    def test_posting_with_cost_parser(self):
        # Example posting with price: assets:broker:bitstamp      0.20000000 BTC @ 855 USD
        posting_text_with_price = "assets:broker:bitstamp      0.20000000 BTC @ 855 USD"
        result_with_price = HledgerParsers.posting.parse(
            posting_text_with_price
        ).unwrap()
        self.assertEqual(
            result_with_price.strip_loc(),
            Posting(
                account=AccountName(parts=["assets", "broker", "bitstamp"]),
                amount=Amount(
                    quantity=Decimal("0.20000000"), commodity=Commodity(name="BTC")
                ),
                cost=Cost(
                    kind=CostKind.UnitCost,
                    amount=Amount(
                        quantity=Decimal("855"), commodity=Commodity(name="USD")
                    ),
                ),
            ),
        )

        self.assertIsNotNone(result_with_price.source_location)
        self.assertEqual(result_with_price.source_location.offset, 0)
        self.assertEqual(
            result_with_price.source_location.length,
            len(posting_text_with_price),
        )  # +1 for the newline
        self.assertEqual(result_with_price.source_location.filename, "")

    def test_posting_with_comment(self):
        # Example posting with comment: ; equity:conversion -0.20000000 BTC
        posting_text_with_comment = "equity:conversion                                              -0.20000000 BTC  ; comment"
        result_with_comment = HledgerParsers.posting.parse(
            posting_text_with_comment
        ).unwrap()
        self.assertEqual(
            result_with_comment.strip_loc(),
            Posting(
                account=AccountName(parts=["equity", "conversion"]),
                amount=Amount(
                    quantity=Decimal("-0.20000000"), commodity=Commodity(name="BTC")
                ),
                comment=Comment(comment="comment"),
            ),
        )

        self.assertIsNotNone(result_with_comment.source_location)
        self.assertEqual(result_with_comment.source_location.offset, 0)
        self.assertEqual(
            result_with_comment.source_location.length,
            len(posting_text_with_comment),
        )  # +1 for the newline
        self.assertEqual(result_with_comment.source_location.filename, "")

    def test_posting_looong(self):
        posting_text_with_comment = (
            "assets:broker:celsius  -1.517186151241544473 BTC @ 19,881.00134 PseudoUSD"
        )
        result_with_comment = HledgerParsers.posting.parse(
            posting_text_with_comment
        ).unwrap()
        self.assertEqual(
            result_with_comment.strip_loc(),
            Posting(
                account=AccountName(parts=["assets", "broker", "celsius"]),
                amount=Amount(
                    quantity=Decimal("-1.517186151241544473"),
                    commodity=Commodity(name="BTC"),
                ),
                cost=Cost(
                    kind=CostKind.UnitCost,
                    amount=Amount(
                        quantity=Decimal("19881.00134"),
                        commodity=Commodity("PseudoUSD"),
                    ),
                ),
            ),
        )

    def test_transaction_parser_failure(self):
        # Missing postings
        transaction_text = "2013-12-03 * Main Account Deposit  USD"
        result = HledgerParsers.transaction.parse(transaction_text)
        self.assertTrue(isinstance(result, Failure))
        # Access the failure message without unwrapping, which would raise an exception
        error_message = str(result.failure())
        self.assertIn("Expected", error_message)
        # The error message might change depending on the parser state,
        # so let's check for a more general indicator of failure at the end of input
        self.assertIn("end of source", error_message)

    def test_transaction_parser(self):
        # Example transaction from examples/all.txt
        transaction_text = """2013-12-03 * Main Account Deposit  USD
    assets:broker:bitstamp       1,349.20 USD
    equity:transfers            -1,349.20 USD
    assets:broker:bitstamp         -15.00 USD
    expenses:broker:bitstamp        15.00 USD"""
        result = HledgerParsers.transaction.parse(transaction_text)
        parsed_transaction = result.unwrap()
        self.assertEqual(parsed_transaction.date, date_class(2013, 12, 3))
        self.assertEqual(parsed_transaction.status, Status.Cleared)
        self.assertEqual(parsed_transaction.payee, "Main Account Deposit  USD")
        self.assertEqual(len(parsed_transaction.postings), 4)

        # Check source location for the transaction
        self.assertIsNotNone(parsed_transaction.source_location)
        self.assertEqual(parsed_transaction.source_location.offset, 0)
        self.assertEqual(
            parsed_transaction.source_location.length, len(transaction_text)
        )
        self.assertEqual(parsed_transaction.source_location.filename, "")

        # Check source location for the first posting
        first_posting = parsed_transaction.postings[0]
        self.assertIsNotNone(first_posting.source_location)
        # Calculate expected offset and length for the first posting
        first_posting_text = "assets:broker:bitstamp       1,349.20 USD"
        expected_offset_first_posting = transaction_text.find(first_posting_text)
        self.assertEqual(
            first_posting.source_location.offset, expected_offset_first_posting
        )
        self.assertEqual(first_posting.source_location.length, len(first_posting_text))
        self.assertEqual(first_posting.source_location.filename, "")

        # Check source location for the second posting
        second_posting = parsed_transaction.postings[1]
        self.assertIsNotNone(second_posting.source_location)
        # Calculate expected offset and length for the second posting
        second_posting_text = "equity:transfers            -1,349.20 USD"
        expected_offset_second_posting = transaction_text.find(second_posting_text)
        self.assertEqual(
            second_posting.source_location.offset, expected_offset_second_posting
        )
        self.assertEqual(
            second_posting.source_location.length, len(second_posting_text)
        )
        self.assertEqual(second_posting.source_location.filename, "")

        # Check source location for the third posting
        third_posting = parsed_transaction.postings[2]
        self.assertIsNotNone(third_posting.source_location)
        # Calculate expected offset and length for the third posting
        third_posting_text = "assets:broker:bitstamp         -15.00 USD"
        expected_offset_third_posting = transaction_text.find(third_posting_text)
        self.assertEqual(
            third_posting.source_location.offset, expected_offset_third_posting
        )
        self.assertEqual(third_posting.source_location.length, len(third_posting_text))
        self.assertEqual(third_posting.source_location.filename, "")

        # Check source location for the fourth posting
        fourth_posting = parsed_transaction.postings[3]
        self.assertIsNotNone(fourth_posting.source_location)
        # Calculate expected offset and length for the fourth posting
        fourth_posting_text = "expenses:broker:bitstamp        15.00 USD"
        expected_offset_fourth_posting = transaction_text.find(fourth_posting_text)
        self.assertEqual(
            fourth_posting.source_location.offset, expected_offset_fourth_posting
        )
        self.assertEqual(
            fourth_posting.source_location.length, len(fourth_posting_text)
        )  # Last posting doesn't have a newline consumed by the parser
        self.assertEqual(fourth_posting.source_location.filename, "")

    def test_transaction_parser_whitespaces(self):
        # Example transaction from examples/all.txt
        transaction_text = """2013-12-03 * Main Account Deposit  USD
    assets:broker:bitstamp       1,349.20 USD
    equity:transfers            -1,349.20 USD  
    assets:broker:bitstamp         -15.00 USD	
    expenses:broker:bitstamp        15.00 USD    """
        result = HledgerParsers.transaction.parse(transaction_text)
        parsed_transaction = result.unwrap()

    def test_transaction_parser_unmarked(self):
        # Example transaction from examples/all.txt
        transaction_text = """2013-12-03 test
    assets:broker:bitstamp       1 USD
    equity:transfers"""
        result = HledgerParsers.transaction.parse(transaction_text)
        parsed_transaction = result.unwrap()

    def test_transaction_parser_exclamation(self):
        # Example transaction from examples/all.txt
        transaction_text = """2013-12-03 ! test
    assets:broker:bitstamp       1 USD
    equity:transfers"""
        result = HledgerParsers.transaction.parse(transaction_text)
        parsed_transaction = result.unwrap()

    def test_empty_journal_parser(self):
        journal_text = ""
        result = HledgerParsers.journal.parse(journal_text)
        parsed_journal = result.unwrap()
        self.assertEqual(parsed_journal, Journal())

    def test_journal_parser_one_transactions(self):
        journal_text = """2024-01-01 * Transaction One
    assets:account1    100 USD
    expenses:category   -100 USD
"""
        result = HledgerParsers.journal.parse(journal_text)
        parsed_journal = result.unwrap()
        self.assertEqual(len(parsed_journal), 1)

    def test_journal_parser_two_transactions(self):
        journal_text = """
2024-01-01 * Transaction One
    assets:account1    100 USD
    expenses:category   -100 USD

    

2024-01-02 ! Transaction Two
    assets:account2    200 EUR
    income:source     -200 EUR
    
"""
        result = HledgerParsers.journal.parse(journal_text)
        parsed_journal = result.unwrap()
        self.assertEqual(len(parsed_journal), 2)

    def test_transaction_parser_with_code(self):
        transaction_text = """2024-01-01 * (CODE123) Transaction with Code
    assets:account1    100 USD
    expenses:category   -100 USD"""
        result = HledgerParsers.transaction.parse(transaction_text)
        parsed_transaction = result.unwrap()
        self.assertEqual(parsed_transaction.code, "CODE123")

    def test_balance_assertion_parser(self):
        balance_text = "assets:broker:revolut        =    0 SOL"
        result = HledgerParsers.posting.parse(balance_text)
        posting = result.unwrap()
        self.assertIsInstance(posting.account, AccountName)
        self.assertEqual(posting.account.parts, ["assets", "broker", "revolut"])

        self.assertIsNone(posting.amount)
        self.assertEqual(
            posting.balance.strip_loc(),
            Amount(quantity=Decimal("0"), commodity=Commodity("SOL")),
        )

    def test_pure_balance_assertion_algo(self):
        balance_text = "= 2557.2145917 ALGO"
        result = HledgerParsers.balance.parse(balance_text)
        posting = result.unwrap()

    def test_balance_assertion_algo(self):
        balance_text = "assets:broker:binance  = 2557.2145917 ALGO"
        result = HledgerParsers.posting.parse(balance_text)
        posting = result.unwrap()

    def test_all_journal(self):
        example_journal_fn = "examples/all.txt"
        result = HledgerParsers.journal.parse(Path(example_journal_fn).read_text())
        parsed_journal = result.unwrap()

    def test_journal_parser_two_transactions(self):
        journal_text = """
include foo.bar    
"""
        result = HledgerParsers.journal.parse(journal_text)
        parsed_journal = result.unwrap().strip_loc()
        self.assertEqual(len(parsed_journal), 1)
        self.assertIsInstance(parsed_journal.entries[0], JournalEntry)
        self.assertIsNotNone(parsed_journal.entries[0].include)
        self.assertEqual(parsed_journal.entries[0].include, Include(filename="foo.bar"))

    # @unittest.skip("Skip this test, until all other tests are successful")
    def test_recursive_journal(self):
        result = parse_hledger_journal("examples/taxes/all.journal").strip_loc()
        self.assertEqual(len(result.entries), 13)
        self.assertEqual(
            result.entries[0].include.filename, "directives.journal"
        )

    def test_commodity_directive_simple(self):
        directive_text = "commodity USD"
        result = HledgerParsers.commodity_directive.parse(directive_text).unwrap()
        self.assertEqual(
            result.strip_loc(),
            CommodityDirective(commodity=Commodity(name="USD"), comment=None),
        )
        self.assertIsNotNone(result.source_location)
        self.assertEqual(result.source_location.offset, 0)
        self.assertEqual(result.source_location.length, len(directive_text))
        self.assertEqual(result.source_location.filename, "")

    def test_commodity_directive_with_comment(self):
        directive_text = "commodity EUR ; format 1.000,00 EUR"
        result = HledgerParsers.commodity_directive.parse(directive_text).unwrap()
        self.assertEqual(
            result.strip_loc(),
            CommodityDirective(
                commodity=Commodity(name="EUR"), comment=Comment(comment="format 1.000,00 EUR")
            ),
        )
        self.assertIsNotNone(result.source_location)
        self.assertEqual(result.source_location.offset, 0)
        self.assertEqual(result.source_location.length, len(directive_text))
        self.assertEqual(result.source_location.filename, "")

    def test_journal_with_commodity_directive(self):
        journal_text = """
commodity USD

2024-01-01 * Transaction One
    assets:account1    100 USD
    expenses:category   -100 USD

include other.journal
"""
        result = HledgerParsers.journal.parse(journal_text).unwrap().strip_loc()
        self.assertEqual(len(result.entries), 3)
        self.assertIsInstance(result.entries[0], JournalEntry)
        self.assertIsNotNone(result.entries[0].commodity_directive)
        self.assertEqual(
            result.entries[0].commodity_directive,
            CommodityDirective(commodity=Commodity(name="USD"), comment=None),
        )
        self.assertIsInstance(result.entries[1], JournalEntry)
        self.assertIsNotNone(result.entries[1].transaction)
        self.assertIsInstance(result.entries[2], JournalEntry)
        self.assertIsNotNone(result.entries[2].include)
        self.assertEqual(result.entries[2].include, Include(filename="other.journal"))

    def test_parse_account_directive(self):
        journal_content = """
account assets:checking
account expenses:food ; Lunch
"""
        journal = HledgerParsers.journal.parse(journal_content).unwrap().strip_loc()
        self.assertEqual(len(journal.entries), 2)

        entry1 = journal.entries[0]
        self.assertIsInstance(entry1, JournalEntry)
        self.assertIsNotNone(entry1.account_directive)
        self.assertEqual(entry1.account_directive.name.parts, ["assets", "checking"])
        self.assertIsNone(entry1.account_directive.comment)

        entry2 = journal.entries[1]
        self.assertIsInstance(entry2, JournalEntry)
        self.assertIsNotNone(entry2.account_directive)
        self.assertEqual(entry2.account_directive.name.parts, ["expenses", "food"])
        self.assertEqual(entry2.account_directive.comment, Comment(comment="Lunch"))

    def test_parse_alias_directive(self):
        journal_content = """
alias assets:broker:schwab* = assets:broker:schwab
"""
        journal = HledgerParsers.journal.parse(journal_content).unwrap().strip_loc()
        self.assertEqual(len(journal.entries), 1)

        entry = journal.entries[0]
        self.assertIsInstance(entry, JournalEntry)
        self.assertIsNotNone(entry.alias)
        self.assertEqual(entry.alias.pattern, "assets:broker:schwab*")
        self.assertEqual(entry.alias.target_account.parts, ["assets", "broker", "schwab"])

    def test_price_directive_parser_no_time(self):
        directive_text = "P 2013-12-02 USD 3.0965 PLN"
        result = HledgerParsers.price_directive.parse(directive_text).unwrap()
        self.assertEqual(
            result.strip_loc(),
            MarketPrice(
                date=date_class(2013, 12, 2),
                time=None,
                commodity=Commodity(name="USD"),
                unit_price=Amount(quantity=Decimal("3.0965"), commodity=Commodity(name="PLN")),
                comment=None,
            ),
        )
        self.assertIsNotNone(result.source_location)
        self.assertEqual(result.source_location.offset, 0)
        self.assertEqual(result.source_location.length, len(directive_text))
        self.assertEqual(result.source_location.filename, "")

    def test_price_directive_parser_with_time(self):
        directive_text = "P 2004-06-21 02:18:02 AAPL 32.91 USD"
        result = HledgerParsers.price_directive.parse(directive_text).unwrap()
        self.assertEqual(
            result.strip_loc(),
            MarketPrice(
                date=date_class(2004, 6, 21),
                time=time_class(2, 18, 2),
                commodity=Commodity(name="AAPL"),
                unit_price=Amount(quantity=Decimal("32.91"), commodity=Commodity(name="USD")),
                comment=None,
            ),
        )
        self.assertIsNotNone(result.source_location)
        self.assertEqual(result.source_location.offset, 0)
        self.assertEqual(result.source_location.length, len(directive_text))
        self.assertEqual(result.source_location.filename, "")

    def test_price_directive_parser_with_comment(self):
        directive_text = "P 2022-01-01 $ 2 C ; estimate"
        result = HledgerParsers.price_directive.parse(directive_text).unwrap()
        self.assertEqual(
            result.strip_loc(),
            MarketPrice(
                date=date_class(2022, 1, 1),
                time=None,
                commodity=Commodity(name="$"),
                unit_price=Amount(quantity=Decimal("2"), commodity=Commodity(name="C")),
                comment=Comment(comment="estimate"),
            ),
        )

    def test_journal_with_price_directive(self):
        journal_text = """
P 2013-12-02 USD 3.0965 PLN

2024-01-01 * Transaction One
    assets:account1    100 USD
    expenses:category   -100 USD
"""
        result = HledgerParsers.journal.parse(journal_text).unwrap().strip_loc()
        self.assertEqual(len(result.entries), 2)
        self.assertIsInstance(result.entries[0], JournalEntry)
        self.assertIsNotNone(result.entries[0].market_price)
        self.assertEqual(
            result.entries[0].market_price,
            MarketPrice(
                date=date_class(2013, 12, 2),
                time=None,
                commodity=Commodity(name="USD"),
                unit_price=Amount(quantity=Decimal("3.0965"), commodity=Commodity(name="PLN")),
                comment=None,
            ),
        )
        self.assertIsInstance(result.entries[1], JournalEntry)
        self.assertIsNotNone(result.entries[1].transaction)


if __name__ == "__main__":
    unittest.main(failfast=True)
