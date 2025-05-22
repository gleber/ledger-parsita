from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest
from src.classes import (
    AccountName,
    Amount,
    Commodity,
    Posting,
    Transaction,
)
from src.common_types import (
    SourceLocation,
    Cost, # Import Cost
    CostKind, # Import CostKind
    Comment, # Import Comment
)
from src.errors import (
    TransactionBalanceError,
    ImbalanceError,
    AmbiguousElidedAmountError,
    UnresolvedElidedAmountError,
    NoCommoditiesElidedError,
    MultipleCommoditiesRemainingError,
    TransactionIntegrityError,
    MissingDateError,
    MissingDescriptionError,
    InsufficientPostingsError,
    InvalidPostingError,
)
from returns.result import Success, Failure


def test_account_name_str():
    assert str(AccountName(parts=["assets", "cash"])) == "assets:cash"


def test_account_name_parent():
    assert AccountName(parts=["assets", "cash"]).parent == AccountName(
        parts=["assets"]
    )
    assert AccountName(parts=["assets"]).parent is None


def test_account_name_is_asset():
    assert AccountName(parts=["assets", "cash"]).isAsset() is True
    assert AccountName(parts=["Assets", "Cash"]).isAsset() is True # Case-insensitive check
    assert AccountName(parts=["expenses", "food"]).isAsset() is False
    assert AccountName(parts=["income", "salary"]).isAsset() is False
    assert AccountName(parts=["liabilities", "creditcard"]).isAsset() is False


def test_account_name_is_dated_subaccount():
    assert AccountName(parts=["assets", "broker", "XYZ", "20230115"]).isDatedSubaccount() is True
    assert AccountName(parts=["assets", "broker", "XYZ", "ABC"]).isDatedSubaccount() is False
    assert AccountName(parts=["assets", "broker", "XYZ"]).isDatedSubaccount() is False
    assert AccountName(parts=["20230115"]).isDatedSubaccount() is True
    assert AccountName(parts=[]).isDatedSubaccount() is False


def test_commodity_is_cash():
    assert Commodity(name="USD").isCash() is True
    assert Commodity(name="PLN").isCash() is True
    assert Commodity(name="EUR").isCash() is True
    assert Commodity(name="BTC").isCash() is False
    assert Commodity(name="XYZ").isCash() is False


def test_commodity_is_crypto():
    assert Commodity(name="BTC").isCrypto() is True
    assert Commodity(name="ETH").isCrypto() is True
    assert Commodity(name="PseudoUSD").isCrypto() is True # Test a stablecoin
    assert Commodity(name="USD").isCrypto() is False
    assert Commodity(name="XYZ").isCrypto() is False


def test_commodity_is_stock():
    assert Commodity(name="AAPL").isStock() is True
    assert Commodity(name="GOOGL").isStock() is True
    assert Commodity(name="MSFT.US").isStock() is True # Test with period
    assert Commodity(name="USD").isStock() is False
    assert Commodity(name="BTC").isStock() is False
    assert Commodity(name="TSLA260116C200").isStock() is False # Option
    assert Commodity(name="VERYLONGTICKER").isStock() is False # Too long


def test_commodity_is_option():
    assert Commodity(name="TSLA260116C200").isOption() is True
    assert Commodity(name="SPY251231P400.5").isOption() is True
    assert Commodity(name="AAPL").isOption() is False
    assert Commodity(name="USD").isOption() is False
    assert Commodity(name="BTC").isOption() is False


def test_transaction_get_key():
    # Create some sample postings
    posting1 = Posting(account=AccountName(["assets", "cash"]), amount=Amount(Decimal("-100"), Commodity("USD")))
    posting2 = Posting(account=AccountName(["expenses", "food"]), amount=Amount(Decimal("100"), Commodity("USD")))
    posting3 = Posting(account=AccountName(["assets", "bank"]), amount=Amount(Decimal("-50"), Commodity("EUR")))
    posting4 = Posting(account=AccountName(["expenses", "travel"]), amount=Amount(Decimal("50"), Commodity("EUR")))

    # Create transactions
    tx1_date = date(2023, 1, 15)
    tx1_payee = "Grocery Store"
    tx1 = Transaction(date=tx1_date, payee=tx1_payee, postings=[posting1, posting2])

    tx2_date = date(2023, 1, 15)
    tx2_payee = "Grocery Store"
    tx2 = Transaction(date=tx2_date, payee=tx2_payee, postings=[posting2, posting1]) # Same postings, different order

    tx3_date = date(2023, 1, 16)
    tx3_payee = "Grocery Store"
    tx3 = Transaction(date=tx3_date, payee=tx3_payee, postings=[posting1, posting2]) # Different date

    tx4_date = date(2023, 1, 15)
    tx4_payee = "Supermarket"
    tx4 = Transaction(date=tx4_date, payee=tx4_payee, postings=[posting1, posting2]) # Different payee

    tx5_date = date(2023, 1, 15)
    tx5_payee = "Grocery Store"
    tx5 = Transaction(date=tx5_date, payee=tx5_payee, postings=[posting3, posting4]) # Different postings

    # Get keys
    key1 = tx1.getKey()
    key2 = tx2.getKey()
    key3 = tx3.getKey()
    key4 = tx4.getKey()
    key5 = tx5.getKey()

    # Assertions
    assert key1 == key2, "Keys should be the same for transactions with the same date, payee, and postings (regardless of posting order)"
    assert key1 != key3, "Keys should be different for transactions with different dates"
    assert key1 != key4, "Keys should be different for transactions with different payees"
    assert key1 != key5, "Keys should be different for transactions with different postings"

    # Test with elided amounts
    posting_elided = Posting(account=AccountName(["assets", "cash"]))
    tx_elided1 = Transaction(date=tx1_date, payee=tx1_payee, postings=[posting_elided, posting2])
    tx_elided2 = Transaction(date=tx1_date, payee=tx1_payee, postings=[posting2, posting_elided])
    key_elided1 = tx_elided1.getKey()
    key_elided2 = tx_elided2.getKey()
    assert key_elided1 == key_elided2, "Keys should be the same for elided amounts, order independent"
    assert key1 != key_elided1, "Key with elided amount should differ from non-elided"

# --- Test Cases for Transaction.validate_internal_consistency ---
def test_validate_internal_consistency_valid():
    tx = Transaction(
        date=date(2024, 1, 1),
        payee="Valid Payee",
        postings=[
            Posting(account=AccountName(["Assets", "Bank"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["Expenses", "Food"]), amount=Amount(Decimal("100"), Commodity("USD"))),
        ]
    )
    assert isinstance(tx.verify_integrity(), Success) # Changed

def test_validate_internal_consistency_missing_date():
    tx = Transaction(
        date=None, # type: ignore
        payee="Valid Payee",
        postings=[
            Posting(account=AccountName(["Assets", "Bank"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["Expenses", "Food"]), amount=Amount(Decimal("100"), Commodity("USD"))),
        ]
    )
    result = tx.verify_integrity() # Changed
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), MissingDateError)

def test_validate_internal_consistency_missing_payee_str():
    tx = Transaction(
        date=date(2024, 1, 1),
        payee="", # Empty string
        postings=[
            Posting(account=AccountName(["Assets", "Bank"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["Expenses", "Food"]), amount=Amount(Decimal("100"), Commodity("USD"))),
        ]
    )
    result = tx.verify_integrity() # Changed
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), MissingDescriptionError)

def test_validate_internal_consistency_invalid_payee_type():
    tx = Transaction(
        date=date(2024, 1, 1),
        payee=123, # type: ignore # Invalid type
        postings=[
            Posting(account=AccountName(["Assets", "Bank"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["Expenses", "Food"]), amount=Amount(Decimal("100"), Commodity("USD"))),
        ]
    )
    result = tx.verify_integrity() # Changed
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), MissingDescriptionError)
    assert "invalid type" in str(result.failure())


def test_validate_internal_consistency_insufficient_postings_none():
    tx = Transaction(
        date=date(2024, 1, 1),
        payee="Valid Payee",
        postings=[] # No postings
    )
    result = tx.verify_integrity() # Changed
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InsufficientPostingsError)

def test_validate_internal_consistency_insufficient_postings_one():
    tx = Transaction(
        date=date(2024, 1, 1),
        payee="Valid Payee",
        postings=[
            Posting(account=AccountName(["Assets", "Bank"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
        ] # Only one posting
    )
    result = tx.verify_integrity() # Changed
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InsufficientPostingsError)

def test_validate_internal_consistency_invalid_posting_item_type():
    tx = Transaction(
        date=date(2024, 1, 1),
        payee="Valid Payee",
        postings=[
            Posting(account=AccountName(["Assets", "Bank"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            "not a posting" # type: ignore
        ]
    )
    result = tx.verify_integrity() # Changed
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InvalidPostingError)
    assert "Item at index 1" in str(result.failure())


def test_validate_internal_consistency_invalid_posting_account_type():
    tx = Transaction(
        date=date(2024, 1, 1),
        payee="Valid Payee",
        postings=[
            Posting(account=AccountName(["Assets", "Bank"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account="NotAnAccountName", amount=Amount(Decimal("100"), Commodity("USD"))), # type: ignore
        ]
    )
    result = tx.verify_integrity() # Changed
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InvalidPostingError)
    assert "Posting 1 has an invalid account type" in str(result.failure())

def test_validate_internal_consistency_invalid_posting_amount_type():
    tx = Transaction(
        date=date(2024, 1, 1),
        payee="Valid Payee",
        postings=[
            Posting(account=AccountName(["Assets", "Bank"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["Expenses", "Food"]), amount="NotAnAmount"), # type: ignore
        ]
    )
    result = tx.verify_integrity() # Changed
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InvalidPostingError)
    assert "Posting 1 has an invalid amount type" in str(result.failure())

def test_validate_internal_consistency_invalid_posting_amount_quantity_type():
    tx = Transaction(
        date=date(2024, 1, 1),
        payee="Valid Payee",
        postings=[
            Posting(account=AccountName(["Assets", "Bank"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["Expenses", "Food"]), amount=Amount(quantity="NotADecimal", commodity=Commodity("USD"))), # type: ignore
        ]
    )
    result = tx.verify_integrity() # Changed
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InvalidPostingError)
    assert "Posting 1 amount quantity is not a Decimal" in str(result.failure())

def test_validate_internal_consistency_invalid_posting_amount_commodity_type():
    tx = Transaction(
        date=date(2024, 1, 1),
        payee="Valid Payee",
        postings=[
            Posting(account=AccountName(["Assets", "Bank"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["Expenses", "Food"]), amount=Amount(quantity=Decimal("100"), commodity="NotACommodity")), # type: ignore
        ]
    )
    result = tx.verify_integrity() # Changed
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), InvalidPostingError)
    assert "Posting 1 amount commodity is not a Commodity" in str(result.failure())

def test_validate_internal_consistency_posting_amount_is_none_valid():
    tx = Transaction(
        date=date(2024, 1, 1),
        payee="Valid Payee",
        postings=[
            Posting(account=AccountName(["Assets", "Bank"]), amount=Amount(Decimal("-100"), Commodity("USD"))),
            Posting(account=AccountName(["Expenses", "Food"]), amount=None), # Elided amount
        ]
    )
    assert isinstance(tx.verify_integrity(), Success) # Changed


