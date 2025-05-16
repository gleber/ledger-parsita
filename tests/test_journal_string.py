from src.classes import Amount, Commodity, AccountName, Tag, Cost, CostKind, CommodityDirective, AccountDirective, Alias, MarketPrice, Include, Posting, Transaction, JournalEntry, Comment, Status
from src.journal import Journal
from decimal import Decimal
from datetime import date, datetime
import pytest

def test_amount_to_journal_string():
    amount = Amount(quantity=Decimal("100"), commodity=Commodity(name="USD"))
    assert amount.to_journal_string() == "100 USD"

def test_commodity_to_journal_string():
    commodity = Commodity(name="EUR")
    assert commodity.to_journal_string() == "EUR"
    commodity_with_special_chars = Commodity(name="E UR-.")
    assert commodity_with_special_chars.to_journal_string() == '"E UR-."'

def test_account_name_to_journal_string():
    account_name = AccountName(parts=["Assets", "Bank", "Checking"])
    assert account_name.to_journal_string() == "Assets:Bank:Checking"

def test_tag_to_journal_string():
    tag_without_value = Tag(name="cleared")
    assert tag_without_value.to_journal_string() == "cleared"
    tag_with_value = Tag(name="ref", value="12345")
    assert tag_with_value.to_journal_string() == "ref:12345"

def test_cost_to_journal_string():
    amount = Amount(quantity=Decimal("855"), commodity=Commodity(name="USD"))
    unit_cost = Cost(kind=CostKind.UnitCost, amount=amount)
    assert unit_cost.to_journal_string() == "@ 855 USD"
    total_cost = Cost(kind=CostKind.TotalCost, amount=amount)
    assert total_cost.to_journal_string() == "@@ 855 USD"

def test_commodity_directive_to_journal_string():
    commodity_directive_without_comment = CommodityDirective(commodity=Commodity(name="BTC"))
    assert commodity_directive_without_comment.to_journal_string() == "commodity BTC"
    commodity_directive_with_comment = CommodityDirective(commodity=Commodity(name="ETH"), comment=Comment(comment="Ethereum"))
    assert commodity_directive_with_comment.to_journal_string() == "commodity ETH ; Ethereum"

def test_account_directive_to_journal_string():
    account_directive_without_comment = AccountDirective(name=AccountName(parts=["Assets", "Cash"]))
    assert account_directive_without_comment.to_journal_string() == "account Assets:Cash"
    account_directive_with_comment = AccountDirective(name=AccountName(parts=["Expenses", "Food"]), comment=Comment(comment="Groceries and dining"))
    assert account_directive_with_comment.to_journal_string() == "account Expenses:Food ; Groceries and dining"

def test_alias_to_journal_string():
    alias = Alias(pattern="AMEX", target_account=AccountName(parts=["Liabilities", "Credit Cards", "American Express"]))
    assert alias.to_journal_string() == "alias AMEX = Liabilities:Credit Cards:American Express"

def test_market_price_to_journal_string():
    price_date = date(2023, 12, 29)
    commodity = Commodity(name="SOL")
    amount = Amount(quantity=Decimal("105.30"), commodity=Commodity(name="USD"))
    market_price_without_time_or_comment = MarketPrice(date=price_date, commodity=commodity, unit_price=amount)
    assert market_price_without_time_or_comment.to_journal_string() == "P 2023-12-29 SOL 105.30 USD"

    price_datetime = datetime(2023, 12, 29, 10, 30)
    market_price_with_time_and_comment = MarketPrice(date=price_date, commodity=commodity, unit_price=amount, comment=Comment(comment="Closing price"))
    assert market_price_with_time_and_comment.to_journal_string() == "P 2023-12-29 SOL 105.30 USD ; Closing price"

def test_include_to_journal_string():
    include = Include(filename="other.journal")
    assert include.to_journal_string() == "include other.journal"

def test_posting_to_journal_string_basic():
    posting = Posting(account=AccountName(parts=["Assets", "Cash"]), amount=Amount(quantity=Decimal("100"), commodity=Commodity(name="USD")))
    assert posting.to_journal_string() == "Assets:Cash  100 USD"

def test_posting_to_journal_string_with_cost():
    amount = Amount(quantity=Decimal("0.20000000"), commodity=Commodity(name="BTC"))
    cost_amount = Amount(quantity=Decimal("855"), commodity=Commodity(name="USD"))
    cost = Cost(kind=CostKind.UnitCost, amount=cost_amount)
    posting = Posting(account=AccountName(parts=["assets", "broker", "bitstamp"]), amount=amount, cost=cost)
    assert posting.to_journal_string() == "assets:broker:bitstamp  0.20000000 BTC @ 855 USD"

def test_posting_to_journal_string_with_balance():
    balance_amount = Amount(quantity=Decimal("0"), commodity=Commodity(name="SOL"))
    posting = Posting(account=AccountName(parts=["assets", "broker", "revolut"]), balance=balance_amount)
    assert posting.to_journal_string() == "assets:broker:revolut  = 0 SOL"

def test_posting_to_journal_string_with_comment():
    posting = Posting(account=AccountName(parts=["expenses", "broker", "bitstamp"]), amount=Amount(quantity=Decimal("15.00"), commodity=Commodity(name="USD")), comment=Comment(comment="Broker fee"))
    assert posting.to_journal_string() == "expenses:broker:bitstamp  15.00 USD ; Broker fee"

def test_posting_to_journal_string_with_status():
    posting = Posting(account=AccountName(parts=["assets", "broker", "bitstamp"]), amount=Amount(quantity=Decimal("1349.20"), commodity=Commodity(name="USD")), status="*")
    assert posting.to_journal_string() == "* assets:broker:bitstamp  1349.20 USD"

def test_posting_to_journal_string_with_tags():
    tags = [Tag(name="cleared"), Tag(name="ref", value="12345")]
    posting = Posting(account=AccountName(parts=["assets", "broker", "bitstamp"]), amount=Amount(quantity=Decimal("1349.20"), commodity=Commodity(name="USD")), tags=tags)
    assert posting.to_journal_string() == "assets:broker:bitstamp  1349.20 USD :cleared:ref:12345:"

def test_transaction_to_journal_string_basic():
    postings = [
        Posting(account=AccountName(parts=["assets", "broker", "bitstamp"]), amount=Amount(quantity=Decimal("1349.20"), commodity=Commodity(name="USD"))),
        Posting(account=AccountName(parts=["equity", "transfers"]), amount=Amount(quantity=Decimal("-1349.20"), commodity=Commodity(name="USD")))
    ]
    transaction = Transaction(date=date(2013, 12, 3), payee="Main Account Deposit", postings=postings)
    expected_output = """2013-12-03 Main Account Deposit
  assets:broker:bitstamp  1349.20 USD
  equity:transfers  -1349.20 USD"""
    assert transaction.to_journal_string() == expected_output

def test_transaction_to_journal_string_with_status_and_code():
    postings = [
        Posting(account=AccountName(parts=["assets", "broker", "bitstamp"]), amount=Amount(quantity=Decimal("0.20000000"), commodity=Commodity(name="BTC")), cost=Cost(kind=CostKind.UnitCost, amount=Amount(quantity=Decimal("855"), commodity=Commodity(name="USD")))),
        Posting(account=AccountName(parts=["assets", "broker", "bitstamp"]), amount=Amount(quantity=Decimal("-171.00"), commodity=Commodity(name="USD")))
    ]
    transaction = Transaction(date=date(2013, 12, 5), status=Status.Cleared, code="10350868", payee="Main Account Market Buy BTC", postings=postings)
    expected_output = """2013-12-05 * (10350868) Main Account Market Buy BTC
  assets:broker:bitstamp  0.20000000 BTC @ 855 USD
  assets:broker:bitstamp  -171.00 USD"""
    assert transaction.to_journal_string() == expected_output

def test_transaction_to_journal_string_with_comment():
    postings = [
        Posting(account=AccountName(parts=["assets", "broker", "bitstamp"]), amount=Amount(quantity=Decimal("-0.11400000"), commodity=Commodity(name="BTC"))),
        Posting(account=AccountName(parts=["equity", "transfers"]), amount=Amount(quantity=Decimal("0.11400000"), commodity=Commodity(name="BTC")))
    ]
    transaction = Transaction(date=date(2014, 1, 22), payee="Main Account Withdrawal", comment=Comment(comment="Withdrawal to cold storage"), postings=postings)
    expected_output = """2014-01-22 Main Account Withdrawal
  assets:broker:bitstamp  -0.11400000 BTC
  equity:transfers  0.11400000 BTC
  ; Withdrawal to cold storage"""
    assert transaction.to_journal_string() == expected_output

def test_journal_entry_to_journal_string():
    transaction = Transaction(date=date(2023, 1, 1), payee="Test Transaction")
    journal_entry_with_transaction = JournalEntry(transaction=transaction)
    assert journal_entry_with_transaction.to_journal_string() == transaction.to_journal_string()

    include = Include(filename="other.journal")
    journal_entry_with_include = JournalEntry(include=include)
    assert journal_entry_with_include.to_journal_string() == include.to_journal_string()

    commodity_directive = CommodityDirective(commodity=Commodity(name="XYZ"))
    journal_entry_with_commodity_directive = JournalEntry(commodity_directive=commodity_directive)
    assert journal_entry_with_commodity_directive.to_journal_string() == commodity_directive.to_journal_string()

    account_directive = AccountDirective(name=AccountName(parts=["Assets", "Test"]))
    journal_entry_with_account_directive = JournalEntry(account_directive=account_directive)
    assert journal_entry_with_account_directive.to_journal_string() == account_directive.to_journal_string()

    alias = Alias(pattern="ABC", target_account=AccountName(parts=["Expenses", "Test"]))
    journal_entry_with_alias = JournalEntry(alias=alias)
    assert journal_entry_with_alias.to_journal_string() == alias.to_journal_string()

    market_price = MarketPrice(date=date(2023, 1, 1), commodity=Commodity(name="TEST"), unit_price=Amount(quantity=Decimal("1"), commodity=Commodity(name="USD")))
    journal_entry_with_market_price = JournalEntry(market_price=market_price)
    assert journal_entry_with_market_price.to_journal_string() == market_price.to_journal_string()

def test_journal_to_journal_string():
    posting1 = Posting(account=AccountName(parts=["assets", "broker", "bitstamp"]), amount=Amount(quantity=Decimal("1349.20"), commodity=Commodity(name="USD")))
    posting2 = Posting(account=AccountName(parts=["equity", "transfers"]), amount=Amount(quantity=Decimal("-1349.20"), commodity=Commodity(name="USD")))
    transaction1 = Transaction(date=date(2013, 12, 3), payee="Main Account Deposit", postings=[posting1, posting2])
    journal_entry1 = JournalEntry(transaction=transaction1)

    posting3 = Posting(account=AccountName(parts=["assets", "broker", "bitstamp"]), amount=Amount(quantity=Decimal("0.20000000"), commodity=Commodity(name="BTC")), cost=Cost(kind=CostKind.UnitCost, amount=Amount(quantity=Decimal("855"), commodity=Commodity(name="USD"))))
    posting4 = Posting(account=AccountName(parts=["assets", "broker", "bitstamp"]), amount=Amount(quantity=Decimal("-171.00"), commodity=Commodity(name="USD")))
    transaction2 = Transaction(date=date(2013, 12, 5), status=Status.Cleared, code="10350868", payee="Main Account Market Buy BTC", postings=[posting3, posting4])
    journal_entry2 = JournalEntry(transaction=transaction2)

    include_directive = Include(filename="other.journal")
    journal_entry3 = JournalEntry(include=include_directive)

    journal = Journal(entries=[journal_entry1, journal_entry2, journal_entry3])

    expected_output = """2013-12-03 Main Account Deposit
  assets:broker:bitstamp  1349.20 USD
  equity:transfers  -1349.20 USD

2013-12-05 * (10350868) Main Account Market Buy BTC
  assets:broker:bitstamp  0.20000000 BTC @ 855 USD
  assets:broker:bitstamp  -171.00 USD

include other.journal"""
    assert journal.to_journal_string() == expected_output
