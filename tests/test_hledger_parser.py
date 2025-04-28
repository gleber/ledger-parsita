from pathlib import Path
import pytest
from datetime import date as date_class, time as time_class
from decimal import Decimal

from parsita import Success, Failure, ParseError

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
    Comment,
)


def test_date_parser():
    result = HledgerParsers.date.parse("2013-12-03")
    assert result.unwrap() == date_class(2013, 12, 3)

def test_date_parser_failure():
    result = HledgerParsers.date.parse("invalid-date")
    assert isinstance(result, Failure)
    error_message = str(result.failure())
    assert "Expected" in error_message
    assert "date" in error_message

def test_status_parser():
    result_cleared = HledgerParsers.status.parse("*")
    assert result_cleared.unwrap() == Status.Cleared

    result_unmarked = HledgerParsers.status.parse("")
    assert result_unmarked.unwrap() == Status.Unmarked

def test_payee_parser():
    result = HledgerParsers.payee.parse("Main Account Deposit  USD")
    assert result.unwrap() == "Main Account Deposit  USD"

def test_account_name_parser():
    result = HledgerParsers.account_name.parse("assets:broker:bitstamp")
    parsed_account_name = result.unwrap()
    assert parsed_account_name.parts == ["assets", "broker", "bitstamp"]

def test_amount_value_parser():
    result = HledgerParsers.amount_value.parse("1,349.20")
    assert result.unwrap() == Decimal("1349.20")

    result_negative = HledgerParsers.amount_value.parse("-171.00")
    assert result_negative.unwrap() == Decimal("-171.00")

def test_cost():
    result = HledgerParsers.cost.parse("@ 1 USD").unwrap()
    assert result.strip_loc() == Cost(
        kind=CostKind.UnitCost,
        amount=Amount(quantity=Decimal("1"), commodity=Commodity("USD")),
    )

def test_cost_long():
    result = HledgerParsers.cost.parse("@ 19,881.00134 PseudoUSD").unwrap()
    assert result.strip_loc() == Cost(
        kind=CostKind.UnitCost,
        amount=Amount(
            quantity=Decimal("19881.00134"), commodity=Commodity("PseudoUSD")
        ),
    )

def test_currency_parser():
    result = HledgerParsers.currency.parse("USD")
    parsed_currency = result.unwrap()
    assert parsed_currency.name == "USD"
    assert parsed_currency.source_location is not None
    assert parsed_currency.source_location.offset == 0
    assert parsed_currency.source_location.length == len("USD")

def test_currency_parser_quoted():
    result = HledgerParsers.currency.parse('"TSLA260116c200"')
    parsed_currency = result.unwrap()
    assert parsed_currency.name == "TSLA260116c200"
    assert parsed_currency.source_location is not None
    assert parsed_currency.source_location.offset == 0
    assert parsed_currency.source_location.length == len('"TSLA260116c200"')

def test_currency_parser_quoted_with_spaces():
    result = HledgerParsers.currency.parse('"Some Commodity With Spaces"')
    parsed_currency = result.unwrap()
    assert parsed_currency.name == "Some Commodity With Spaces"
    assert parsed_currency.source_location is not None
    assert parsed_currency.source_location.offset == 0
    assert parsed_currency.source_location.length == len('"Some Commodity With Spaces"')

def test_amount_parser_failure():
    result = HledgerParsers.amount.parse("invalid amount")
    assert isinstance(result, Failure)
    error_message = str(result.failure())
    assert "Expected" in error_message
    assert "amount" in error_message

def test_amount_parser1():
    result_with_currency = HledgerParsers.amount.parse("349 USD")
    parsed_amount_with_currency = result_with_currency.unwrap()
    assert parsed_amount_with_currency.quantity == Decimal("349")
    assert parsed_amount_with_currency.commodity.name == "USD"

def test_amount_parser2():
    result_with_currency = HledgerParsers.amount.parse("1,349.20 USD")
    parsed_amount_with_currency = result_with_currency.unwrap()
    assert parsed_amount_with_currency.quantity == Decimal("1349.20")
    assert parsed_amount_with_currency.commodity.name == "USD"

def test_amount_parser3():
    result_without_currency = HledgerParsers.amount.parse("-171.00")
    parsed_amount_without_currency = result_without_currency.unwrap()
    assert parsed_amount_without_currency.quantity == Decimal("-171.00")
    assert parsed_amount_without_currency.commodity.name == ""

def test_price_cost_parser():
    result_at = HledgerParsers.cost.parse("@ 855 USD")
    parsed_price_at = result_at.unwrap()
    assert parsed_price_at.amount.quantity == Decimal("855")
    assert parsed_price_at.amount.commodity.name == "USD"

    result_at_at = HledgerParsers.cost.parse("@@ 4,972.04 USD")
    parsed_price_at_at = result_at_at.unwrap()
    assert parsed_price_at_at.amount.quantity == Decimal("4972.04")
    assert parsed_price_at_at.amount.commodity.name == "USD"

def test_posting_parser_short():
    posting_text = "assets:broker:bitstamp"
    result = HledgerParsers.posting.parse(posting_text).unwrap()
    assert result.strip_loc() == Posting(account=AccountName(parts=["assets", "broker", "bitstamp"]))

def test_posting_parser():
    posting_text = "assets:broker:bitstamp  1,349.20 USD"
    result = HledgerParsers.posting.parse(posting_text)
    parsed_posting = result.unwrap()
    assert parsed_posting.account.strip_loc() == AccountName(parts=["assets", "broker", "bitstamp"])
    assert parsed_posting.amount is not None
    assert parsed_posting.amount.strip_loc() == Amount(quantity=Decimal("1349.20"), commodity=Commodity(name="USD"))
    assert parsed_posting.strip_loc() == Posting(
        account=AccountName(parts=["assets", "broker", "bitstamp"]),
        amount=Amount(quantity=Decimal("1349.20"), commodity=Commodity(name="USD")),
    )
    assert parsed_posting.source_location is not None
    assert parsed_posting.source_location.offset == 0
    assert parsed_posting.source_location.length == len(posting_text)

def test_posting_with_cost_parser():
    posting_text_with_price = "assets:broker:bitstamp      0.20000000 BTC @ 855 USD"
    result_with_price = HledgerParsers.posting.parse(posting_text_with_price).unwrap()
    assert result_with_price.strip_loc() == Posting(
        account=AccountName(parts=["assets", "broker", "bitstamp"]),
        amount=Amount(quantity=Decimal("0.20000000"), commodity=Commodity(name="BTC")),
        cost=Cost(
            kind=CostKind.UnitCost,
            amount=Amount(quantity=Decimal("855"), commodity=Commodity(name="USD")),
        ),
    )
    assert result_with_price.source_location is not None
    assert result_with_price.source_location.offset == 0
    assert result_with_price.source_location.length == len(posting_text_with_price)

def test_posting_with_comment():
    posting_text_with_comment = "equity:conversion                                              -0.20000000 BTC  ; comment"
    result_with_comment = HledgerParsers.posting.parse(posting_text_with_comment).unwrap()
    assert result_with_comment.strip_loc() == Posting(
        account=AccountName(parts=["equity", "conversion"]),
        amount=Amount(quantity=Decimal("-0.20000000"), commodity=Commodity(name="BTC")),
        comment=Comment(comment="comment"),
    )
    assert result_with_comment.source_location is not None
    assert result_with_comment.source_location.offset == 0
    assert result_with_comment.source_location.length == len(posting_text_with_comment)

def test_posting_looong():
    posting_text_with_comment = (
        "assets:broker:celsius  -1.517186151241544473 BTC @ 19,881.00134 PseudoUSD"
    )
    result_with_comment = HledgerParsers.posting.parse(posting_text_with_comment).unwrap()
    assert result_with_comment.strip_loc() == Posting(
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
    )

def test_transaction_parser_failure():
    transaction_text = "2013-12-03 * Main Account Deposit  USD"
    result = HledgerParsers.transaction.parse(transaction_text)
    assert isinstance(result, Failure)
    error_message = str(result.failure())
    assert "Expected" in error_message
    assert "end of source" in error_message

def test_transaction_parser():
    transaction_text = """2013-12-03 * Main Account Deposit  USD
    assets:broker:bitstamp       1,349.20 USD
    equity:transfers            -1,349.20 USD
    assets:broker:bitstamp         -15.00 USD
    expenses:broker:bitstamp        15.00 USD"""
    result = HledgerParsers.transaction.parse(transaction_text)
    parsed_transaction = result.unwrap()
    assert parsed_transaction.date == date_class(2013, 12, 3)
    assert parsed_transaction.status == Status.Cleared
    assert parsed_transaction.payee == "Main Account Deposit  USD"
    assert len(parsed_transaction.postings) == 4

    assert parsed_transaction.source_location is not None
    assert parsed_transaction.source_location.offset == 0
    assert parsed_transaction.source_location.length == len(transaction_text)

    first_posting = parsed_transaction.postings[0]
    assert first_posting.source_location is not None
    first_posting_text = "assets:broker:bitstamp       1,349.20 USD"
    expected_offset_first_posting = transaction_text.find(first_posting_text)
    assert first_posting.source_location.offset == expected_offset_first_posting
    assert first_posting.source_location.length == len(first_posting_text)

    second_posting = parsed_transaction.postings[1]
    assert second_posting.source_location is not None
    second_posting_text = "equity:transfers            -1,349.20 USD"
    expected_offset_second_posting = transaction_text.find(second_posting_text)
    assert second_posting.source_location.offset == expected_offset_second_posting
    assert second_posting.source_location.length == len(second_posting_text)

    third_posting = parsed_transaction.postings[2]
    assert third_posting.source_location is not None
    third_posting_text = "assets:broker:bitstamp         -15.00 USD"
    expected_offset_third_posting = transaction_text.find(third_posting_text)
    assert third_posting.source_location.offset == expected_offset_third_posting
    assert third_posting.source_location.length == len(third_posting_text)

    fourth_posting = parsed_transaction.postings[3]
    assert fourth_posting.source_location is not None
    fourth_posting_text = "expenses:broker:bitstamp        15.00 USD"
    expected_offset_fourth_posting = transaction_text.find(fourth_posting_text)
    assert fourth_posting.source_location.offset == expected_offset_fourth_posting
    assert fourth_posting.source_location.length == len(fourth_posting_text)

def test_transaction_parser_whitespaces():
    transaction_text = """2013-12-03 * Main Account Deposit  USD
    assets:broker:bitstamp       1,349.20 USD
    equity:transfers            -1,349.20 USD  
    assets:broker:bitstamp         -15.00 USD	
    expenses:broker:bitstamp        15.00 USD    """
    result = HledgerParsers.transaction.parse(transaction_text)
    result.unwrap() # Just check if it parses without error

def test_transaction_parser_unmarked():
    transaction_text = """2013-12-03 test
    assets:broker:bitstamp       1 USD
    equity:transfers"""
    result = HledgerParsers.transaction.parse(transaction_text)
    result.unwrap() # Just check if it parses without error

def test_transaction_parser_exclamation():
    transaction_text = """2013-12-03 ! test
    assets:broker:bitstamp       1 USD
    equity:transfers"""
    result = HledgerParsers.transaction.parse(transaction_text)
    result.unwrap() # Just check if it parses without error

def test_empty_journal_parser():
    journal_text = ""
    result = HledgerParsers.journal.parse(journal_text)
    parsed_journal = result.unwrap().strip_loc()
    assert parsed_journal == Journal()

def test_journal_parser_one_transactions():
    journal_text = """2024-01-01 * Transaction One
    assets:account1    100 USD
    expenses:category   -100 USD
"""
    result = HledgerParsers.journal.parse(journal_text)
    parsed_journal = result.unwrap()
    assert len(parsed_journal) == 1

def test_journal_parser_two_transactions():
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
    assert len(parsed_journal) == 2

def test_transaction_parser_with_code():
    transaction_text = """2024-01-01 * (CODE123) Transaction with Code
    assets:account1    100 USD
    expenses:category   -100 USD"""
    result = HledgerParsers.transaction.parse(transaction_text)
    parsed_transaction = result.unwrap()
    assert parsed_transaction.code == "CODE123"

def test_balance_assertion_parser():
    balance_text = "assets:broker:revolut        =    0 SOL"
    result = HledgerParsers.posting.parse(balance_text)
    posting = result.unwrap()
    assert isinstance(posting.account, AccountName)
    assert posting.account.parts == ["assets", "broker", "revolut"]
    assert posting.amount is None
    assert posting.balance is not None
    assert posting.balance.strip_loc() == Amount(quantity=Decimal("0"), commodity=Commodity("SOL"))

def test_pure_balance_assertion_algo():
    balance_text = "= 2557.2145917 ALGO"
    result = HledgerParsers.balance.parse(balance_text)
    result.unwrap() # Just check if it parses without error

def test_balance_assertion_algo():
    balance_text = "assets:broker:binance  = 2557.2145917 ALGO"
    result = HledgerParsers.posting.parse(balance_text)
    result.unwrap() # Just check if it parses without error

def test_all_journal():
    example_journal_fn = "examples/all.txt"
    result = HledgerParsers.journal.parse(Path(example_journal_fn).read_text())
    result.unwrap() # Just check if it parses without error

def test_journal_parser_include():
    journal_text = """
include foo.bar    
"""
    result = HledgerParsers.journal.parse(journal_text)
    parsed_journal = result.unwrap().strip_loc()
    assert len(parsed_journal) == 1
    assert isinstance(parsed_journal.entries[0], JournalEntry)
    assert parsed_journal.entries[0].include is not None
    assert parsed_journal.entries[0].include == Include(filename="foo.bar")

@pytest.mark.skipif(not Path("examples/taxes/all/journal").exists(), reason="personal data")
def test_recursive_journal():
    result = parse_hledger_journal("examples/taxes/all.journal").strip_loc()
    assert len(result.entries) == 13
    assert result.entries[0].include is not None
    assert result.entries[0].include.filename == "directives.journal"

def test_commodity_directive_simple():
    directive_text = "commodity USD"
    result = HledgerParsers.commodity_directive.parse(directive_text).unwrap()
    assert result.strip_loc() == CommodityDirective(commodity=Commodity(name="USD"), comment=None)
    assert result.source_location is not None
    assert result.source_location.offset == 0
    assert result.source_location.length == len(directive_text)
    assert result.source_location.filename == Path("")

def test_commodity_directive_with_comment():
    directive_text = "commodity EUR ; format 1.000,00 EUR"
    result = HledgerParsers.commodity_directive.parse(directive_text).unwrap()
    assert result.strip_loc() == CommodityDirective(
        commodity=Commodity(name="EUR"), comment=Comment(comment="format 1.000,00 EUR")
    )
    assert result.source_location is not None
    assert result.source_location.offset == 0
    assert result.source_location.length == len(directive_text)

def test_journal_with_commodity_directive():
    journal_text = """
commodity USD

2024-01-01 * Transaction One
    assets:account1    100 USD
    expenses:category   -100 USD

include other.journal
"""
    result = HledgerParsers.journal.parse(journal_text).unwrap().strip_loc()
    assert len(result.entries) == 3
    assert isinstance(result.entries[0], JournalEntry)
    assert result.entries[0].commodity_directive is not None
    assert result.entries[0].commodity_directive == CommodityDirective(commodity=Commodity(name="USD"), comment=None)
    assert isinstance(result.entries[1], JournalEntry)
    assert result.entries[1].transaction is not None
    assert isinstance(result.entries[2], JournalEntry)
    assert result.entries[2].include is not None
    assert result.entries[2].include == Include(filename="other.journal")

def test_parse_account_directive():
    journal_content = """
account assets:checking
account expenses:food ; Lunch
"""
    journal = HledgerParsers.journal.parse(journal_content).unwrap().strip_loc()
    assert len(journal.entries) == 2

    entry1 = journal.entries[0]
    assert isinstance(entry1, JournalEntry)
    assert entry1.account_directive is not None
    assert entry1.account_directive.name.parts == ["assets", "checking"]
    assert entry1.account_directive.comment is None

    entry2 = journal.entries[1]
    assert isinstance(entry2, JournalEntry)
    assert entry2.account_directive is not None
    assert entry2.account_directive.name.parts == ["expenses", "food"]
    assert entry2.account_directive.comment == Comment(comment="Lunch")

def test_parse_alias_directive():
    journal_content = """
alias assets:broker:schwab* = assets:broker:schwab
"""
    journal = HledgerParsers.journal.parse(journal_content).unwrap().strip_loc()
    assert len(journal.entries) == 1

    entry = journal.entries[0]
    assert isinstance(entry, JournalEntry)
    assert entry.alias is not None
    assert entry.alias.pattern == "assets:broker:schwab*"
    assert entry.alias.target_account.parts == ["assets", "broker", "schwab"]

def test_price_directive_parser_no_time():
    directive_text = "P 2013-12-02 USD 3.0965 PLN"
    result = HledgerParsers.price_directive.parse(directive_text).unwrap()
    assert result.strip_loc() == MarketPrice(
        date=date_class(2013, 12, 2),
        commodity=Commodity(name="USD"),
        unit_price=Amount(quantity=Decimal("3.0965"), commodity=Commodity(name="PLN")),
        comment=None,
    )
    assert result.source_location is not None
    assert result.source_location.offset == 0
    assert result.source_location.length == len(directive_text)

def test_price_directive_parser_with_time():
    directive_text = "P 2004-06-21 02:18:02 AAPL 32.91 USD"
    result = HledgerParsers.price_directive.parse(directive_text).unwrap()
    assert result.strip_loc() == MarketPrice(
        date=date_class(2004, 6, 21),
        commodity=Commodity(name="AAPL"),
        unit_price=Amount(quantity=Decimal("32.91"), commodity=Commodity(name="USD")),
        comment=None,
    )
    assert result.source_location is not None
    assert result.source_location.offset == 0
    assert result.source_location.length == len(directive_text)

def test_price_directive_parser_with_comment():
    directive_text = "P 2022-01-01 $ 2 C ; estimate"
    result = HledgerParsers.price_directive.parse(directive_text).unwrap()
    assert result.strip_loc() == MarketPrice(
        date=date_class(2022, 1, 1),
        commodity=Commodity(name="$"),
        unit_price=Amount(quantity=Decimal("2"), commodity=Commodity(name="C")),
        comment=Comment(comment="estimate"),
    )

def test_journal_with_price_directive():
    journal_text = """
P 2013-12-02 USD 3.0965 PLN

2024-01-01 * Transaction One
    assets:account1    100 USD
    expenses:category   -100 USD
"""
    result = HledgerParsers.journal.parse(journal_text).unwrap().strip_loc()
    assert len(result.entries) == 2
    assert isinstance(result.entries[0], JournalEntry)
    assert result.entries[0].market_price is not None
    assert result.entries[0].market_price == MarketPrice(
        date=date_class(2013, 12, 2),
        commodity=Commodity(name="USD"),
        unit_price=Amount(quantity=Decimal("3.0965"), commodity=Commodity(name="PLN")),
        comment=None,
    )
    assert isinstance(result.entries[1], JournalEntry)
    assert result.entries[1].transaction is not None

def test_journal_and_entities_have_source_location():
    journal_text = """
2024-01-01 * Simple Transaction
    assets:checking    100 USD
    expenses:food       -100 USD

P 2024-01-01 USD 1.0 EUR
"""
    journal = HledgerParsers.journal.parse(journal_text).unwrap()

    assert journal.source_location is not None

    for entry in journal.entries:
        assert entry.source_location is not None
        if entry.transaction:
            assert entry.transaction.source_location is not None
            for posting in entry.transaction.postings:
                assert posting.source_location is not None
                assert posting.account.source_location is not None
                if posting.amount:
                    assert posting.amount.source_location is not None
                    assert posting.amount.commodity.source_location is not None
                if posting.cost:
                    assert posting.cost.source_location is not None
                    assert posting.cost.amount.source_location is not None
                    assert posting.cost.amount.commodity.source_location is not None
                if posting.balance:
                    assert posting.balance.source_location is not None
                    assert posting.balance.commodity.source_location is not None
                if posting.comment:
                    assert posting.comment.source_location is not None
        if entry.commodity_directive:
            assert entry.commodity_directive.source_location is not None
            assert entry.commodity_directive.commodity.source_location is not None
            if entry.commodity_directive.comment:
                assert entry.commodity_directive.comment.source_location is not None
        if entry.account_directive:
            assert entry.account_directive.source_location is not None
            assert entry.account_directive.name.source_location is not None
            if entry.account_directive.comment:
                assert entry.account_directive.comment.source_location is not None
        if entry.alias:
            assert entry.alias.source_location is not None
            assert entry.alias.target_account.source_location is not None
        if entry.market_price:
            assert entry.market_price.source_location is not None
            assert entry.market_price.commodity.source_location is not None
            assert entry.market_price.unit_price.source_location is not None
            assert entry.market_price.unit_price.commodity.source_location is not None
            if entry.market_price.comment:
                assert entry.market_price.comment.source_location is not None
        if entry.include:
            assert entry.include.source_location is not None
