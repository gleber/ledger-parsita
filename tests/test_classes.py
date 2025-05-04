from decimal import Decimal
from datetime import date
from src.classes import AccountName, Commodity, Amount, Cost, CostKind, Posting, Transaction
import pytest

def test_account_name_creation():
    account = AccountName(parts=["assets", "stocks", "AAPL"])
    assert str(account) == "assets:stocks:AAPL"
    assert account.name == "assets:stocks:AAPL"

def test_account_name_parent():
    account = AccountName(parts=["assets", "stocks", "AAPL"])
    parent = account.parent
    assert parent is not None
    assert str(parent) == "assets:stocks"

    grandparent = parent.parent if parent else None
    assert grandparent is not None
    assert str(grandparent) == "assets"

    great_grandparent = grandparent.parent if grandparent else None
    assert great_grandparent is None

def test_is_asset_method():
    asset_account = AccountName(parts=["assets", "stocks", "AAPL"])
    expense_account = AccountName(parts=["expenses", "food"])
    income_account = AccountName(parts=["income", "salary"])
    liability_account = AccountName(parts=["liabilities", "credit card"])
    equity_account = AccountName(parts=["equity", "opening balances"])

    assert asset_account.isAsset()
    assert not expense_account.isAsset()
    assert not income_account.isAsset()
    assert not liability_account.isAsset()
    assert not equity_account.isAsset()

def test_is_dated_subaccount_method():
    dated_account = AccountName(parts=["assets", "stocks", "AAPL", "20230101"])
    non_dated_asset_account = AccountName(parts=["assets", "stocks", "MSFT"])
    expense_account = AccountName(parts=["expenses", "food"])

    assert dated_account.isDatedSubaccount()
    assert not non_dated_asset_account.isDatedSubaccount()
    assert not expense_account.isDatedSubaccount()

def test_commodity_is_cash_method():
    usd = Commodity(name="USD")
    pln = Commodity(name="PLN")
    aapl = Commodity(name="AAPL")

    assert usd.isCash()
    assert pln.isCash()
    assert not aapl.isCash()

def test_commodity_is_stock_method():
    aapl = Commodity(name="AAPL")
    goog = Commodity(name="GOOG")
    brka = Commodity(name="BRK.A") # Stock with a period - my simple regex won't catch this yet
    btc = Commodity(name="BTC")
    usd = Commodity(name="USD")
    option = Commodity(name="TSLA260116C200")

    assert aapl.isStock()
    assert goog.isStock()
    assert brka.isStock()
    assert not btc.isStock()
    assert not usd.isStock()
    assert not option.isStock()

def test_commodity_is_crypto_method():
    btc = Commodity(name="BTC")
    eth = Commodity(name="ETH")
    aapl = Commodity(name="AAPL")
    usd = Commodity(name="USD")

    assert btc.isCrypto()
    assert eth.isCrypto()
    assert not aapl.isCrypto()
    assert not usd.isCrypto()

def test_commodity_is_option_method():
    option1 = Commodity(name="TSLA260116C200")
    option2 = Commodity(name="AAPL230721P150")
    aapl = Commodity(name="AAPL")
    btc = Commodity(name="BTC")

    assert option1.isOption()
    assert option2.isOption()
    assert not aapl.isOption()
    assert not btc.isOption()

def test_transaction_get_posting_cost_explicit_unit_cost():
    # Transaction with explicit unit cost
    transaction = Transaction(
        date=date(2022, 1, 1),
        payee="Buy EUR",
        postings=[
            Posting(account=AccountName(parts=["assets", "dollars"]), amount=Amount(Decimal("-135"), Commodity(name="USD"))),
            Posting(account=AccountName(parts=["assets", "euros"]), amount=Amount(Decimal("100"), Commodity(name="EUR")), cost=Cost(kind=CostKind.UnitCost, amount=Amount(Decimal("1.35"), Commodity(name="USD")))),
        ],
    )
    target_posting = transaction.postings[1] # The EUR posting
    cost = transaction.get_posting_cost(target_posting)
    assert cost is not None
    assert cost.kind == CostKind.UnitCost
    assert cost.amount == Amount(Decimal("1.35"), Commodity(name="USD"))

def test_transaction_get_posting_cost_explicit_total_cost():
    # Transaction with explicit total cost
    transaction = Transaction(
        date=date(2022, 1, 1),
        payee="Buy EUR",
        postings=[
            Posting(account=AccountName(parts=["assets", "dollars"]), amount=Amount(Decimal("-135"), Commodity(name="USD"))),
            Posting(account=AccountName(parts=["assets", "euros"]), amount=Amount(Decimal("100"), Commodity(name="EUR")), cost=Cost(kind=CostKind.TotalCost, amount=Amount(Decimal("135"), Commodity(name="USD")))),
        ],
    )
    target_posting = transaction.postings[1] # The EUR posting
    cost = transaction.get_posting_cost(target_posting)
    assert cost is not None
    assert cost.kind == CostKind.TotalCost
    assert cost.amount == Amount(Decimal("135"), Commodity(name="USD"))

def test_transaction_get_posting_cost_inferred_total_cost():
    # Transaction with implicit cost (Variant 3)
    transaction = Transaction(
        date=date(2022, 1, 1),
        payee="Buy EUR",
        postings=[
            Posting(account=AccountName(parts=["assets", "dollars"]), amount=Amount(Decimal("-135"), Commodity(name="USD"))),
            Posting(account=AccountName(parts=["assets", "euros"]), amount=Amount(Decimal("100"), Commodity(name="EUR"))),
        ],
    )
    target_posting = transaction.postings[1] # The EUR posting
    cost = transaction.get_posting_cost(target_posting)
    assert cost is not None
    assert cost.kind == CostKind.TotalCost
    assert cost.amount == Amount(Decimal("135"), Commodity(name="USD"))

    target_posting_other = transaction.postings[0] # The USD posting
    cost_other = transaction.get_posting_cost(target_posting_other)
    assert cost_other is not None
    assert cost_other.kind == CostKind.TotalCost
    assert cost_other.amount == Amount(Decimal("100"), Commodity(name="EUR"))


def test_transaction_get_posting_cost_no_cost():
    # Transaction with no cost and not eligible for inference
    transaction = Transaction(
        date=date(2022, 1, 1),
        payee="Salary",
        postings=[
            Posting(account=AccountName(parts=["assets", "bank"]), amount=Amount(Decimal("1000"), Commodity(name="USD"))),
            Posting(account=AccountName(parts=["income", "salary"]), amount=Amount(Decimal("-1000"), Commodity(name="USD"))),
            Posting(account=AccountName(parts=["expenses", "tax"]), amount=Amount(Decimal("200"), Commodity(name="USD"))), # More than two postings
        ],
    )
    target_posting = transaction.postings[0] # The bank posting
    cost = transaction.get_posting_cost(target_posting)
    assert cost is None

    # Transaction with two postings but same commodity
    transaction_same_commodity = Transaction(
        date=date(2022, 1, 1),
        payee="Transfer",
        postings=[
            Posting(account=AccountName(parts=["assets", "bank"]), amount=Amount(Decimal("-100"), Commodity(name="USD"))),
            Posting(account=AccountName(parts=["assets", "cash"]), amount=Amount(Decimal("100"), Commodity(name="USD"))),
        ],
    )
    target_posting_same_commodity = transaction_same_commodity.postings[0]
    cost_same_commodity = transaction_same_commodity.get_posting_cost(target_posting_same_commodity)
    assert cost_same_commodity is None
