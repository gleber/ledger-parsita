from decimal import Decimal
from datetime import date
from src.classes import (
    AccountName, Commodity, Amount, Cost, CostKind, Posting, Transaction,
    MissingDateError, MissingDescriptionError, InsufficientPostingsError, InvalidPostingError,
    ImbalanceError, AmbiguousElidedAmountError, UnresolvedElidedAmountError,
    NoCommoditiesElidedError, MultipleCommoditiesRemainingError
)
from returns.result import Success, Failure # Import Success and Failure
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

def test_commodity_is_crypto_method():
    btc = Commodity(name="BTC")
    eth = Commodity(name="ETH")
    aapl = Commodity(name="AAPL")
    usd = Commodity(name="USD")

    assert btc.isCrypto()
    assert eth.isCrypto()
    assert not aapl.isCrypto()
    assert not usd.isCrypto()

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

# Tests for Transaction.validate_internal_consistency
def test_transaction_validate_internal_consistency_valid():
    valid_transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Valid Transaction",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "food"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
        ]
    )
    result = valid_transaction.validate_internal_consistency()
    assert isinstance(result, Success)

def test_transaction_validate_internal_consistency_invalid_date():
    invalid_transaction = Transaction(
        date=None, # type: ignore
        payee="Invalid Date",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "food"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
        ]
    )
    result = invalid_transaction.validate_internal_consistency()
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), MissingDateError)

def test_transaction_validate_internal_consistency_missing_payee():
    invalid_transaction = Transaction(
        date=date(2023,1,1),
        payee="", # Empty payee
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "food"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
        ]
    )
    result = invalid_transaction.validate_internal_consistency()
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), MissingDescriptionError)

def test_transaction_validate_internal_consistency_insufficient_postings():
    invalid_transaction = Transaction(
        date=date(2023,1,1),
        payee="One Posting",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount=Amount(Decimal("100"), Commodity("USD"))),
        ]
    )
    result = invalid_transaction.validate_internal_consistency()
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InsufficientPostingsError)

def test_transaction_validate_internal_consistency_invalid_posting_account():
    invalid_transaction = Transaction(
        date=date(2023,1,1),
        payee="Invalid Posting Account",
        postings=[
            Posting(account=None, amount=Amount(Decimal("100"), Commodity("USD"))), # type: ignore
            Posting(account=AccountName(["expenses", "food"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
        ]
    )
    result = invalid_transaction.validate_internal_consistency()
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InvalidPostingError)
    assert "invalid account type" in str(result.failure()).lower()


def test_transaction_validate_internal_consistency_invalid_posting_amount_type():
    invalid_transaction = Transaction(
        date=date(2023,1,1),
        payee="Invalid Posting Amount Type",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount="not an amount"), # type: ignore
            Posting(account=AccountName(["expenses", "food"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
        ]
    )
    result = invalid_transaction.validate_internal_consistency()
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InvalidPostingError)
    assert "invalid amount type" in str(result.failure()).lower()

def test_transaction_validate_internal_consistency_invalid_posting_amount_quantity():
    invalid_transaction = Transaction(
        date=date(2023,1,1),
        payee="Invalid Posting Amount Quantity",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount=Amount("not a decimal", Commodity("USD"))), # type: ignore
            Posting(account=AccountName(["expenses", "food"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
        ]
    )
    result = invalid_transaction.validate_internal_consistency()
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InvalidPostingError)
    assert "quantity is not a decimal" in str(result.failure()).lower()

def test_transaction_validate_internal_consistency_invalid_posting_amount_commodity():
    invalid_transaction = Transaction(
        date=date(2023,1,1),
        payee="Invalid Posting Amount Commodity",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount=Amount(Decimal("100"), "not a commodity")), # type: ignore
            Posting(account=AccountName(["expenses", "food"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
        ]
    )
    result = invalid_transaction.validate_internal_consistency()
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InvalidPostingError)
    assert "commodity is not a commodity" in str(result.failure()).lower()


# Tests for Transaction.is_balanced
def test_transaction_is_balanced_simple_two_postings():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Balanced",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "food"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
        ]
    )
    result = transaction.is_balanced()
    assert isinstance(result, Success)

def test_transaction_is_balanced_imbalanced_two_postings():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Imbalanced",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "food"]), amount=Amount(Decimal("-99"), Commodity("USD"))),
        ]
    )
    result = transaction.is_balanced()
    assert isinstance(result, Failure)
    failure_val = result.failure()
    assert isinstance(failure_val, ImbalanceError)
    assert failure_val.commodity == Commodity("USD")
    assert failure_val.balance_sum == Decimal("1")

def test_transaction_is_balanced_one_elided_amount_infers_correctly():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Elided Balanced",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "food"])), # Elided amount
        ]
    )
    result = transaction.is_balanced()
    assert isinstance(result, Success)

def test_transaction_is_balanced_one_elided_amount_infers_zero_if_others_balance():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Elided Zero Balanced",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "transfer"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "food"])), # Elided, should be 0
        ]
    )
    result = transaction.is_balanced()
    # This case is tricky. The current logic might assign the imbalance to the single elided.
    # If assets and expenses already balance, the elided should be 0.
    # The current logic for `is_balanced` might need refinement for this specific scenario
    # if it doesn't correctly infer zero. For now, let's assume it should work.
    # Update: The logic was updated to handle this.
    assert isinstance(result, Success)


def test_transaction_is_balanced_two_elided_amounts_same_commodity_ambiguous():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Two Elided Ambiguous",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "food"])),      # Elided
            Posting(account=AccountName(["expenses", "entertainment"])), # Elided
        ]
    )
    result = transaction.is_balanced()
    assert isinstance(result, Failure)
    failure_val = result.failure()
    assert isinstance(failure_val, AmbiguousElidedAmountError)
    assert failure_val.commodity == Commodity("USD")

def test_transaction_is_balanced_multiple_commodities_balanced():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Multi Commodity Balanced",
        postings=[
            Posting(account=AccountName(["assets", "cash_usd"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "import_usd"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["assets", "cash_eur"]), amount=Amount(Decimal("50"), Commodity("EUR"))),
            Posting(account=AccountName(["expenses", "import_eur"]), amount=Amount(Decimal("-50"), Commodity("EUR"))),
        ]
    )
    result = transaction.is_balanced()
    assert isinstance(result, Success)

def test_transaction_is_balanced_multiple_commodities_imbalanced_one():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Multi Commodity Imbalanced EUR",
        postings=[
            Posting(account=AccountName(["assets", "cash_usd"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "import_usd"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["assets", "cash_eur"]), amount=Amount(Decimal("50"), Commodity("EUR"))),
            Posting(account=AccountName(["expenses", "import_eur"]), amount=Amount(Decimal("-40"), Commodity("EUR"))), # Imbalance here
        ]
    )
    result = transaction.is_balanced()
    assert isinstance(result, Failure)
    failure_val = result.failure()
    assert isinstance(failure_val, ImbalanceError)
    assert failure_val.commodity == Commodity("EUR")
    assert failure_val.balance_sum == Decimal("10")

def test_transaction_is_balanced_multiple_commodities_one_elided_infers():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Multi Commodity Elided EUR",
        postings=[
            Posting(account=AccountName(["assets", "cash_usd"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "import_usd"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["assets", "cash_eur"]), amount=Amount(Decimal("50"), Commodity("EUR"))),
            Posting(account=AccountName(["expenses", "import_eur"])), # Elided, should be -50 EUR
        ]
    )
    result = transaction.is_balanced()
    assert isinstance(result, Success)

def test_transaction_is_balanced_elided_with_no_other_postings_of_commodity():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Elided Unresolved",
        postings=[
            Posting(account=AccountName(["assets", "cash_usd"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "food"])), # Elided, should infer -100 USD
            Posting(account=AccountName(["assets", "cash_eur"])), # Elided, but no EUR to balance against
        ]
    )
    result = transaction.is_balanced()
    assert isinstance(result, Failure)
    failure_val = result.failure()
    assert isinstance(failure_val, AmbiguousElidedAmountError)
    assert failure_val.commodity == Commodity("USD")


def test_transaction_is_balanced_all_elided_fails():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="All Elided",
        postings=[
            Posting(account=AccountName(["assets", "cash"])),
            Posting(account=AccountName(["expenses", "food"])),
        ]
    )
    result = transaction.is_balanced()
    assert isinstance(result, Failure)
    failure_val = result.failure()
    assert isinstance(failure_val, NoCommoditiesElidedError)

def test_transaction_is_balanced_single_posting_elided_no_commodity_context():
    # This case is inherently unresolvable for balancing without knowing the commodity.
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Single Elided No Context",
        postings=[
            Posting(account=AccountName(["assets", "cash"])), # Elided
            Posting(account=AccountName(["expenses", "unknown"])) # Elided
        ]
    )
    result = transaction.is_balanced()
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), NoCommoditiesElidedError)

def test_transaction_is_balanced_complex_elided_inference():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Complex Elide",
        postings=[
            Posting(account=AccountName(["assets", "cash_usd"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["assets", "cash_eur"]), amount=Amount(Decimal("50"), Commodity("EUR"))),
            Posting(account=AccountName(["expenses", "goods_usd"])), # Elide USD
            Posting(account=AccountName(["expenses", "services_eur"]), amount=Amount(Decimal("-30"), Commodity("EUR"))),
            Posting(account=AccountName(["expenses", "fees_eur"])), # Elide EUR
        ]
    )
    # Expected: goods_usd = -100 USD, fees_eur = -20 EUR
    result = transaction.is_balanced()
    assert isinstance(result, Success), f"Balancing failed: {result.failure() if isinstance(result, Failure) else 'Success'}"

def test_transaction_is_balanced_multiple_elided_with_multiple_commodities():
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Multiple Elided with Multiple Commodities",
        postings=[
            Posting(account=AccountName(["assets", "cash_usd"]), amount=Amount(Decimal("100"), Commodity("USD"))),
            Posting(account=AccountName(["expenses", "import_usd"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["assets", "cash_eur"]), amount=Amount(Decimal("50"), Commodity("EUR"))),
            Posting(account=AccountName(["expenses", "import_eur"]), amount=Amount(Decimal("-50"), Commodity("EUR"))),
            Posting(account=AccountName(["expenses", "extra"])), # Elided, ambiguous due to multiple commodities
            Posting(account=AccountName(["expenses", "extra2"])), # Elided, ambiguous due to multiple commodities
        ]
    )
    result = transaction.is_balanced()
    assert isinstance(result, Failure)
    failure_val = result.failure()
    assert isinstance(failure_val, MultipleCommoditiesRemainingError)
    assert len(failure_val.commodities) == 2
    assert set(str(c) for c in failure_val.commodities) == {"USD", "EUR"}

def test_transaction_is_balanced_elided_posting_invalid_amount_in_other():
    # Test case where an elided posting exists, but another posting has an invalid amount structure
    # This should ideally be caught by validate_internal_consistency first,
    # but is_balanced should also handle it gracefully if it reaches that point.
    transaction = Transaction(
        date=date(2023, 1, 1),
        payee="Elided with Invalid Other",
        postings=[
            Posting(account=AccountName(["assets", "cash"]), amount="not-an-amount-object"), # type: ignore
            Posting(account=AccountName(["expenses", "food"])), # Elided
        ]
    )
    # First, check consistency
    consistency_result = transaction.validate_internal_consistency()
    assert isinstance(consistency_result, Failure)
    assert isinstance(consistency_result.failure(), InvalidPostingError)

    # Then, check balance (which should also fail due to the invalid posting)
    balance_result = transaction.is_balanced()
    assert isinstance(balance_result, Failure)
    assert isinstance(balance_result.failure(), InvalidPostingError)
