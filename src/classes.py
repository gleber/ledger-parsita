from abc import abstractmethod
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field, fields, replace
from enum import Enum
from pathlib import Path
from typing import List, Optional, Self, Union, Dict, Generic, TypeVar
from datetime import date, datetime
from decimal import Decimal
import re
import bisect
from returns.result import Result, Success, Failure, safe # Import Result, Success, Failure, safe
from returns.pipeline import flow
from returns.pointfree import bind
from returns.maybe import Maybe, Some, Nothing # Import Maybe types
from parsita import ParseError, ParserContext, Parser, Reader, lit, reg, rep, rep1, repsep, opt # Import necessary parsita components
from parsita.state import Continue, Input, Output, State # Import from parsita.state
from parsita.util import splat # Import splat

# Error types for Transaction validation and balancing
class TransactionValidationError(Exception):
    """Base class for transaction validation and balancing errors."""
    pass

class TransactionIntegrityError(TransactionValidationError):
    """For issues with the basic structure or completeness of the Transaction object itself."""
    pass

class MissingDateError(TransactionIntegrityError):
    def __init__(self, message: str = "Transaction date is missing or invalid."):
        super().__init__(message)

class MissingDescriptionError(TransactionIntegrityError):
    def __init__(self, message: str = "Transaction payee/description is missing or empty."):
        super().__init__(message)

class InsufficientPostingsError(TransactionIntegrityError):
    def __init__(self, message: str = "Transaction must have at least two postings."):
        super().__init__(message)

class InvalidPostingError(TransactionIntegrityError):
    def __init__(self, message: str):
        super().__init__(message)

class TransactionBalanceError(TransactionValidationError):
    """For issues related to the sum of posting amounts."""
    pass

class ImbalanceError(TransactionBalanceError):
    def __init__(self, commodity: "Commodity", balance_sum: Decimal):
        self.commodity = commodity
        self.balance_sum = balance_sum
        super().__init__(f"Transaction does not balance for commodity {commodity}. Sum is {balance_sum}")

class AmbiguousElidedAmountError(TransactionBalanceError):
    def __init__(self, commodity: "Commodity"):
        self.commodity = commodity
        super().__init__(f"More than one elided amount for commodity {commodity}, cannot infer balance")

class UnresolvedElidedAmountError(TransactionBalanceError):
    def __init__(self, commodity: "Commodity"):
        self.commodity = commodity
        super().__init__(f"Cannot resolve elided amount for commodity {commodity}.")

class NoCommoditiesElidedError(TransactionBalanceError):
    def __init__(self, message: str = "Cannot resolve elided amount as no commodities are present in the transaction"):
        super().__init__(message)

class MultipleCommoditiesRemainingError(TransactionBalanceError):
    def __init__(self, commodities: List["Commodity"], message: Optional[str] = None): # Fixed type hint
        self.commodities = commodities
        if message is None:
            if commodities:
                commodity_str = ", ".join(str(c) for c in commodities)
                message = f"Cannot resolve remaining elided amounts due to multiple commodities present: {commodity_str}."
            else:
                message = "Cannot resolve remaining elided amounts due to multiple commodities present in the transaction."
        super().__init__(message)

# Verification Error Types
class VerificationError(Exception):
    """Base class for journal-level verification errors."""
    def __init__(self, message: str, source_location: Optional["SourceLocation"] = None):
        self.source_location = source_location
        super().__init__(message)

    def __str__(self):
        loc_str = f" at {self.source_location.filename}:{self.source_location.line}:{self.source_location.column}" if self.source_location and self.source_location.line is not None else ""
        # Ensure message is stringified properly before concatenation
        base_message = super().__str__()
        return f"{base_message}{loc_str}"


class AcquisitionMissingDatedSubaccountError(VerificationError):
    """Error for stock/option acquisition posting not using a dated subaccount."""
    def __init__(self, posting: "Posting"):
        message = f"Stock/option acquisition posting for '{posting.amount.commodity}' to account '{posting.account}' does not use a dated subaccount (YYYYMMDD)"
        super().__init__(message, posting.source_location)

class BalanceSheetCalculationError(VerificationError):
    """Error during balance sheet calculation."""
    # This will likely wrap other errors like ValueError or Failure contents
    def __init__(self, original_error: Exception, source_location: Optional["SourceLocation"] = None):
        self.original_error = original_error
        message = f"Balance sheet calculation failed: {original_error}"
        super().__init__(message, source_location)


CASH_TICKERS = ["USD", "PLN", "EUR"]
CRYPTO_TICKERS = ["BTC", "ETH", "XRP", "LTC", "BCH", "ADA", "DOT", "UNI", "LINK", "SOL", "PseudoUSD", "BUSD", "FDUSD", "USDT", "USDC", "FTM", "ALGO"]
SIMPLE_CURRENCIES = ["$"]

class SourceCacheManager:
    """Manages caching of file content and newline offsets for efficient position lookup."""

    def __init__(self):
        self._content_cache: Dict[Path, str] = {}
        self._newline_offsets_cache: Dict[Path, List[int]] = {}

    def get_content(self, filename: Path, file_content: Optional[str]) -> str:
        """Reads and caches file content if not already cached."""
        resolved_path = filename.resolve()
        if resolved_path not in self._content_cache:
            content = file_content or resolved_path.read_text()
            self._content_cache[resolved_path] = content
            self._newline_offsets_cache[resolved_path] = [i for i, char in enumerate(content) if char == '\n']
        return self._content_cache[resolved_path]

    def get_newline_offsets(self, filename: Path, file_content: Optional[str]) -> List[int]:
        """Returns cached newline offsets, ensuring content is cached first."""
        resolved_path = filename.resolve()
        if resolved_path not in self._newline_offsets_cache:
             # Ensure content and offsets are cached
            self.get_content(filename, file_content)
        return self._newline_offsets_cache[resolved_path]

    def calculate_line_column(self, filename: Path, file_content: Optional[str], offset: int) -> tuple[int, int]:
        """Calculates 1-based line and column using cached newline offsets."""
        newline_offsets = self.get_newline_offsets(filename, file_content)

        # Find the index of the newline character immediately preceding the offset
        # bisect_left finds the insertion point to maintain order, which is the index
        # of the first element greater than or equal to offset.
        # We want the index of the newline *before* the offset, so we subtract 1.
        line_index = bisect.bisect_left(newline_offsets, offset)

        # The line number is 1-based, so it's the index + 1
        line = line_index + 1

        # The column number is the offset relative to the start of the current line.
        # The start of the current line is the offset of the previous newline + 1.
        # If it's the first line (line_index == 0), the start offset is 0.
        start_of_line_offset = newline_offsets[line_index - 1] + 1 if line_index > 0 else 0
        column = offset - start_of_line_offset + 1 # Column is also 1-based

        return line, column

# Global instance (not a true singleton with __init__)
source_cache_manager = SourceCacheManager()


class PositionAware(Generic[Output]):
    """An object which can cooperate with the positioned parser.

    The ``positioned`` parser calls the ``set_position`` method on values it
    receives. This abstract base class marks those objects that can cooperate
    with ``positioned`` in this way and receive the input position to produce
    the final value.
    """

    source_location: Optional["SourceLocation"] = None

    def set_position(self, start: int, length: int) -> Self:
        return replace(  # type: ignore
            self,
            source_location=SourceLocation(filename=Path(""), offset=start, length=length),
        )

    def strip_loc(self):
        stripped_fields = {
            # Mypy can't handle self well
            field.name: getattr(self, field.name)
            for field in fields(self)  # type: ignore
        }

        def strip_one(v):
            if v is None:  # Add check for None
                return None
            if isinstance(v, PositionAware):
                return v.strip_loc()
            if isinstance(v, Iterable) and not isinstance(v, str):
                return [strip_one(i) for i in v]
            return v

        for k in stripped_fields.keys():
            stripped_fields[k] = strip_one(stripped_fields[k])
        stripped_fields["source_location"] = None
        # mypy can't handle self well
        return replace(self, **stripped_fields)  # type: ignore

    def set_filename(self, filename: Path, file_content: str) -> Self:
        # mypy can't handle self well
        sub_fields = {field.name: getattr(self, field.name) for field in fields(self)}  # type: ignore

        def set_one(v):
            if isinstance(v, PositionAware):
                return v.set_filename(filename, file_content)
            if isinstance(v, Iterable) and not isinstance(v, str):
                return [set_one(i) for i in v]
            return v

        for k in sub_fields.keys():
            sub_fields[k] = set_one(sub_fields[k])
        if "source_location" not in sub_fields:
            raise Exception(f"{self} does not have source_location!")
        sl = sub_fields["source_location"]
        if isinstance(sl, SourceLocation) and sl is not None:
            start_offset = sl.offset
            length = sl.length
            # Use the singleton cache manager to calculate line and column
            line, column = source_cache_manager.calculate_line_column(filename, file_content, start_offset)
            sub_fields["source_location"] = SourceLocation(
                filename=filename.resolve(),
                offset=start_offset,
                length=length,
                line=line,
                column=column,
            )
        # mypy can't handle self well
        return replace(self, **sub_fields) # type: ignore


class CostKind(Enum):
    UnitCost = "@"
    TotalCost = "@@"

    def __str__(self):
        return self.value


@dataclass
class SourceLocation:
    """A location in a source file"""

    filename: Path
    offset: int
    length: int
    line: Optional[int] = None
    column: Optional[int] = None


def sl(sl: SourceLocation | None) -> SourceLocation:
    if sl is None:
        return SourceLocation(Path(""), 0, 0, None, None)
    return sl


@dataclass
class Comment(PositionAware["Comment"]):
    comment: str
    source_location: Optional["SourceLocation"] = None

    def to_journal_string(self) -> str:
        return f"; {self.comment}"


class CommodityKind(Enum):
    CASH = "CASH"
    CRYPTO = "CRYPTO"
    OPTION = "OPTION"
    STOCK = "STOCK"


@dataclass(eq=False)
class Commodity(PositionAware["Commodity"]):
    """A commodity"""

    name: str
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return self.name

    def to_journal_string(self) -> str:
        if self.name.isalpha() or self.name in SIMPLE_CURRENCIES:
            return self.name
        return f'"{self.name}"'

    @property
    def kind(self) -> CommodityKind:
        if self.name in CASH_TICKERS:
            return CommodityKind.CASH
        if self.name in CRYPTO_TICKERS:
            return CommodityKind.CRYPTO
        # Add checks for OPTION and STOCK based on existing methods or logic
        if self.isOption():
            return CommodityKind.OPTION
        if self.isStock():
            return CommodityKind.STOCK
        # Default or raise an error for unknown types
        # For now, we can default to CASH or raise an error
        # raise ValueError(f"Unknown commodity type: {self.name}")
        return CommodityKind.CASH # Defaulting for now, might need refinement


    def isCash(self) -> bool:
        """Checks if the commodity is a cash commodity (USD or PLN)."""
        return self.name in CASH_TICKERS

    def isCrypto(self) -> bool:
        """Checks if the commodity is a cryptocurrency."""
        return self.name in CRYPTO_TICKERS

    def isStock(self) -> bool:
        """Checks if the commodity is likely a stock (simple ticker check)."""
        # Check for 1-5 uppercase letters, allowing periods, and ensure it's not a known cryptocurrency or cash
        return bool(re.fullmatch(r"[A-Z\.]{1,7}", self.name)) and not self.isCash() and not self.isCrypto() # Adjusted length for tickers like MSFT.US

    def isOption(self) -> bool:
        """Checks if the commodity is likely an option contract (basic pattern check)."""
        # Basic regex for a common option format (e.g., TSLA260116C200, TSLA260116c200)
        # This is a simplified pattern and might need refinement
        option_regex = re.compile(r"^[A-Z]+(?:\d{6})?[CPcp]\d+(\.\d+)?$")
        return bool(option_regex.match(self.name))

    def __eq__(self, other):
        if not isinstance(other, Commodity):
            return NotImplemented
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)


@dataclass
class Amount(PositionAware["Amount"]):
    """An amount"""

    quantity: Decimal
    commodity: Commodity
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return f"{self.quantity} {self.commodity}"

    def to_journal_string(self) -> str:
        return f"{self.quantity} {self.commodity.to_journal_string()}"

    def __add__(self, other: "Amount") -> "Amount":
        if self.commodity != other.commodity:
            raise ValueError("Cannot add amounts with different commodities")
        return Amount(self.quantity + other.quantity, self.commodity)

    def __iadd__(self, other: "Amount") -> "Amount":
        if self.commodity != other.commodity:
            raise ValueError("Cannot add amounts with different commodities")
        self.quantity += other.quantity
        return self


@dataclass
class CapitalGainResult:
    """Represents the result of a capital gain/loss calculation for a matched sale portion."""
    closing_posting: "Posting"
    opening_lot_original_posting: "Posting" # Reference to the original posting of the matched lot
    matched_quantity: "Amount"
    cost_basis: "Amount" # Total cost basis for the matched quantity
    proceeds: "Amount" # Total proceeds for the matched quantity
    gain_loss: "Amount" # Calculated gain or loss
    closing_date: date # Add closing date
    acquisition_date: date # Add acquisition date

@dataclass
class AmountStyle(PositionAware["AmountStyle"]):
    """Style of an amount"""

    source_location: Optional["SourceLocation"] = None


@dataclass
class Cost(PositionAware["Cost"]):
    """Amount of a cost"""

    kind: CostKind
    amount: Amount
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return f"{{{self.amount}}}"

    def to_journal_string(self) -> str:
        return f"{self.kind.value} {self.amount.to_journal_string()}"


@dataclass(eq=False)
class AccountName(PositionAware["AccountName"]):
    """An account name"""

    parts: List[str]
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return ":".join(self.parts)

    def to_journal_string(self) -> str:
        return str(self)

    @property
    def name(self) -> str:
        return str(self)

    @property
    def parent(self) -> Optional["AccountName"]:
        if len(self.parts) > 1:
            return AccountName(self.parts[:-1])
        return None

    def isAsset(self) -> bool:
        """Checks if the account is an asset account."""
        return self.name.lower().startswith("assets:")

    def isDatedSubaccount(self) -> bool:
        """Checks if the account has a dated subaccount."""
        # 20251015
        dated_account_regex = re.compile(r"^\d{8}$")
        if not self.parts:
            return False
        return bool(dated_account_regex.match(self.parts[-1]))

    def __eq__(self, other):
        if not isinstance(other, AccountName):
            return NotImplemented
        return self.parts == other.parts

    def __hash__(self):
        return hash(tuple(self.parts))


class Status(Enum):
    """The status of a transaction or posting"""

    Unmarked = ""
    Pending = "!"
    Cleared = "*"

    def __str__(self):
        return self.value


@dataclass(unsafe_hash=True)
class Tag(PositionAware["Tag"]):
    """A tag"""

    name: str
    value: Optional[str] = None
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        if self.value:
            return f"{self.name}:{self.value}"
        return f"{self.name}"

    def to_journal_string(self) -> str:
        if self.value:
            return f"{self.name}:{self.value}"
        return self.name


@dataclass
class CommodityDirective(PositionAware["CommodityDirective"]):
    """A commodity directive"""

    commodity: Commodity
    example_amount: Optional[Amount] = None
    comment: Optional[Comment] = None
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return f"commodity {self.commodity}{' ' + self.comment.to_journal_string() if self.comment else ''}"

    def to_journal_string(self) -> str:
        s = f"commodity {self.commodity.to_journal_string()}"
        if self.comment:
            s += f" {self.comment.to_journal_string()}"
        return s


@dataclass(unsafe_hash=True)
class Posting(PositionAware["Posting"]):
    """A posting in a transaction"""

    account: "AccountName"
    amount: Optional["Amount"] = None
    cost: Optional[Cost] = None
    balance: Optional[Amount] = None
    comment: Optional[Comment] = None
    status: Optional[str] = None
    date: Optional[date] = None
    datetime: Optional[datetime] = None
    tags: List[Tag] = field(default_factory=list)
    source_location: Optional["SourceLocation"] = None

    def isOpening(self) -> bool:
        """Checks if a posting indicates opening a position in an asset account and is not cash."""
        return bool(
            self.account
            and self.account.isAsset()
            and self.amount
            and self.amount.quantity > 0
            and not self.amount.commodity.isCash()
        )

    def isClosing(self) -> bool:
        return bool(
            self.account
            and self.account.isAsset()
            and self.amount
            and self.amount.quantity < 0
            and not self.amount.commodity.isCash()
        )

    def to_journal_string(self) -> str:
        s = ""
        if self.status:
            s += f"{self.status} "
        s += self.account.to_journal_string()

        if self.amount:
            s += f"  {self.amount.to_journal_string()}"
        elif self.balance:
            s += f"  = {self.balance.to_journal_string()}"

        if self.cost:
            s += f" {self.cost.to_journal_string()}"

        if self.tags:
            s += " :" + ":".join([tag.to_journal_string() for tag in self.tags]) + ":"

        if self.comment:
            s += f" {self.comment.to_journal_string()}"

        return s.strip()  # Remove any potential trailing whitespace

    def add_comment(self, comment_to_add: "Comment") -> "Posting":
        """Adds a comment to the posting, appending to any existing comment."""
        if self.comment:
            # Append to existing comment
            new_comment_text = f"{self.comment.comment} {comment_to_add.comment}"
            updated_comment = Comment(comment=new_comment_text, source_location=self.comment.source_location) # Keep original comment's source location
        else:
            # Set the new comment
            updated_comment = comment_to_add # Use the new comment directly

        # Return a new Posting object with the updated comment
        return replace(self, comment=updated_comment)


@dataclass(unsafe_hash=True)
class Transaction(PositionAware["Transaction"]):
    """A transaction in the ledger"""

    date: date
    payee: Union[str, AccountName]
    postings: List[Posting] = field(default_factory=list)
    comments: List[Comment] = field(default_factory=list)
    comment: Optional[Comment] = None
    code: Optional[str] = None
    status: Optional[Status] = None
    source_location: Optional["SourceLocation"] = None

    def to_journal_string(self) -> str:
        s = f"{self.date.strftime('%Y-%m-%d')}"
        if self.status:
            s += f" {self.status}"
        if self.code:
            s += f" ({self.code})"
        s += f" {self.payee}"

        for posting in self.postings:
            s += f"\n  {posting.to_journal_string()}"

        if self.comment:
            s += f"\n  {self.comment.to_journal_string()}"

        return s
    
    def getKey(self):
        """Returns a unique key for the transaction."""
        posting_keys = tuple(
            sorted(
                (str(p.account), str(p.amount) if p.amount else None)
                for p in self.postings
            )
        )
        return (self.date, self.payee, posting_keys)

    def get_posting_cost(self, target_posting: Posting) -> Optional[Cost]:
        """Gets the explicit or infers the cost for a posting."""
        # Return explicit cost if it exists
        if target_posting.cost:
            return target_posting.cost

        # Attempt to infer cost if transaction has exactly two postings
        if len(self.postings) == 2:
            p1 = self.postings[0]
            p2 = self.postings[1]

            # Both postings must have amounts to infer cost
            if p1.amount and p2.amount:
                amt1 = p1.amount
                amt2 = p2.amount

                # Case 1: Different commodities (e.g., asset purchase with cash or currency exchange)
                if amt1.commodity != amt2.commodity:
                    other_posting = p2 if target_posting == p1 else p1
                    # This logic infers the cost of target_posting from other_posting.
                    # It's assumed that in a 2-posting transaction with different commodities,
                    # one is the "price" of the other.
                    if other_posting.amount: # Ensure other_posting has an amount
                        inferred_amount = Amount(abs(other_posting.amount.quantity), other_posting.amount.commodity)
                        return Cost(kind=CostKind.TotalCost, amount=inferred_amount)

                # Case 2: Same commodities (e.g., RSU-like income leading to asset acquisition)
                elif amt1.commodity == amt2.commodity and target_posting.isOpening():
                    # target_posting is the asset acquisition (e.g., +4 GOOG)
                    # The other posting should be the income offset (e.g., -4 GOOG from income:...)
                    other_posting = p2 if target_posting == p1 else p1

                    # Check if other_posting is from an income account and has the opposite quantity of target_posting
                    if other_posting.amount and \
                       target_posting.amount and \
                       other_posting.amount.quantity == -target_posting.amount.quantity and \
                       other_posting.account.name.startswith("income:"):
                        
                        # Infer $0 cost basis.
                        # Determine currency for the $0 cost: use a cash commodity from the transaction if available, else default to USD.
                        zero_cost_currency = Commodity("USD") # Default
                        for post_in_tx in self.postings: # self.postings refers to the transaction's postings
                            if post_in_tx.amount and post_in_tx.amount.commodity.isCash():
                                zero_cost_currency = post_in_tx.amount.commodity
                                break
                        
                        zero_cost_amount = Amount(Decimal(0), zero_cost_currency)
                        return Cost(kind=CostKind.UnitCost, amount=zero_cost_amount)

        return None # No explicit cost and inference not possible

    def get_asset_acquisition_posting(self) -> Maybe[Posting]:
        """Finds the asset acquisition posting in the transaction, if any. Returns Maybe."""
        for posting in self.postings:
            # Check if it's an asset, has an amount, and quantity is positive (acquisition)
            # No longer checking isDatedSubaccount here, as that's part of the verification step.
            if posting.account.isAsset() and posting.amount is not None and posting.amount.quantity > 0:
                 # Check if it's stock or option
                if posting.amount.commodity.isStock() or posting.amount.commodity.isOption():
                    return Some(posting)
        return Nothing

    def get_cost_basis_posting(self, acquisition_posting: Posting) -> Optional[Posting]:
        """Finds the cost basis posting for a given asset acquisition posting."""
        for other_posting in self.postings:
            # Look for a posting with a negative cash amount in any account other than the asset account being acquired
            if (
                other_posting != acquisition_posting
                and other_posting.amount is not None
                and other_posting.amount.quantity < 0
                and other_posting.amount.commodity.isCash()
                and other_posting.account != acquisition_posting.account # Ensure it's not the same asset account
            ):
                return other_posting
        return None

    def calculate_cost_basis_per_unit(self, acquisition_posting: Posting, cost_basis_posting: Posting) -> Optional[Amount]:
        """Calculates the cost basis per unit for an asset acquisition."""
        if acquisition_posting.amount is None or cost_basis_posting.amount is None:
            return None # Should not happen if called after finding valid postings

        if acquisition_posting.amount.quantity != 0:
            cost_basis_per_unit_value = abs(cost_basis_posting.amount.quantity / acquisition_posting.amount.quantity)
            return Amount(cost_basis_per_unit_value, cost_basis_posting.amount.commodity)
        else:
            return None # Handle zero quantity acquisition

    def verify_integrity(self) -> Result[None, TransactionIntegrityError]:
        """
        Checks if the Transaction object has all its essential components present and in a basic valid state.
        Assumes the transaction is already parsed.
        """
        if not isinstance(self.date, date): # datetime.date, not datetime.datetime specifically
            return Failure(MissingDateError())

        if isinstance(self.payee, str) and not self.payee.strip():
            return Failure(MissingDescriptionError())
        elif not isinstance(self.payee, (str, AccountName)): # Should be str or AccountName
             return Failure(MissingDescriptionError("Transaction payee/description has invalid type."))


        if len(self.postings) < 2:
            return Failure(InsufficientPostingsError())

        for i, p in enumerate(self.postings):
            if not isinstance(p, Posting):
                return Failure(InvalidPostingError(f"Item at index {i} in postings is not a Posting object."))
            if not isinstance(p.account, AccountName):
                return Failure(InvalidPostingError(f"Posting {i} has an invalid account type: {type(p.account)}."))
            if p.amount is not None: # Amount can be None for elided amounts
                if not isinstance(p.amount, Amount):
                    return Failure(InvalidPostingError(f"Posting {i} has an invalid amount type: {type(p.amount)}."))
                if not isinstance(p.amount.quantity, Decimal):
                     return Failure(InvalidPostingError(f"Posting {i} amount quantity is not a Decimal: {type(p.amount.quantity)}."))
                if not isinstance(p.amount.commodity, Commodity):
                     return Failure(InvalidPostingError(f"Posting {i} amount commodity is not a Commodity: {type(p.amount.commodity)}."))
            # Further checks for cost, balance, etc., could be added if they are non-optional or have specific type requirements
            # For now, focusing on account and amount (if present) as per the plan.
        return Success(None)

    def verify(self) -> Result[None, TransactionValidationError]:
        """
        Performs a full verification of the transaction, checking for integrity and balance.
        """
        integrity_check = self.verify_integrity()
        if isinstance(integrity_check, Failure):
            return integrity_check

        balance_check = self.is_balanced()
        # is_balanced already returns Result[None, TransactionBalanceError]
        # TransactionBalanceError is a subclass of TransactionValidationError
        return balance_check

    def has_elided_values(self) -> bool:
        """
        Checks if the transaction has any postings with elided (missing) amounts.
        Returns True if there are postings without an Amount object, False otherwise.
        """
        return any(posting.amount is None for posting in self.postings)

    def is_balanced(self) -> Result[None, TransactionBalanceError]:
        """
        Checks if the transaction can be balanced, either as-is or by inferring elided values.
        Returns Success(None) if balanced or can be balanced, or Failure with an appropriate error if not.
        """
        # First check for internal consistency
        integrity_result = self.verify_integrity() # Changed from validate_internal_consistency
        if isinstance(integrity_result, Failure):
            return Failure(integrity_result.failure())

        # Use balance() to check if the transaction can be balanced
        balance_result = self.balance()
        if isinstance(balance_result, Success):
            return Success(None)
        else:
            return balance_result  # Propagate the Failure from balance()

    def balance(self) -> Result['Transaction', TransactionBalanceError]:
        # Integrity check first
        integrity_result = self.verify_integrity()
        if isinstance(integrity_result, Failure):
            return Failure(integrity_result.failure())

        current_tx_copy = replace(self) # Work with a copy for potential augmentation
        commodity_sums: Dict[Commodity, Decimal] = defaultdict(Decimal)
        elided_postings_indices = []

        # Calculate initial sums (including cost-value logic) and identify elided postings
        for i, posting in enumerate(current_tx_copy.postings):
            if posting.amount and isinstance(posting.amount, Amount):
                # Add effect of the primary amount
                commodity_sums[posting.amount.commodity] += posting.amount.quantity

                # If there's a cost, this posting also contributes to the balance of the cost's commodity.
                # The value of this posting in terms of the cost commodity is added.
                if posting.cost and isinstance(posting.cost, Cost) and isinstance(posting.cost.amount, Amount):
                    cost_commodity = posting.cost.amount.commodity
                    cost_price_per_unit_or_total = posting.cost.amount.quantity

                    if posting.cost.kind == CostKind.UnitCost: # @ (per-unit price)
                        # Value in cost_commodity is (primary_quantity * price_per_unit)
                        value_in_cost_commodity = posting.amount.quantity * cost_price_per_unit_or_total
                        commodity_sums[cost_commodity] += value_in_cost_commodity
                    elif posting.cost.kind == CostKind.TotalCost: # @@ (total price)
                        # Value in cost_commodity is total_price (if primary_quantity > 0)
                        # or -total_price (if primary_quantity < 0).
                        if posting.amount.quantity > Decimal(0):
                            commodity_sums[cost_commodity] += cost_price_per_unit_or_total
                        elif posting.amount.quantity < Decimal(0):
                            commodity_sums[cost_commodity] -= cost_price_per_unit_or_total
                        # If posting.amount.quantity is 0, a total cost (@@) doesn't contribute to balancing here.
            else:
                elided_postings_indices.append(i)
                # Note: elided postings with balance assertions are handled later in elision logic

        if not elided_postings_indices: # No elided amounts
            imbalances = {comm: sm for comm, sm in commodity_sums.items() if sm != Decimal(0)}
            
            if not imbalances: # Already balanced
                return Success(current_tx_copy)

            if 1 <= len(imbalances) <= 2: # Potential for equity inference
                inferred_equity_postings = []
                equity_account = AccountName(["equity", "conversion"])
                for comm, sum_val in imbalances.items():
                    # Use the new add_comment method
                    inferred_equity_postings.append(
                        Posting(account=equity_account, amount=Amount(-sum_val, comm)).add_comment(Comment("inferred by equity conversion"))
                    )
                
                # Create a new transaction with these equity postings added
                final_postings = current_tx_copy.postings + inferred_equity_postings
                augmented_tx = replace(current_tx_copy, postings=final_postings)
                
                # Return the augmented transaction
                return Success(augmented_tx)
            else: # More than 2 imbalances, cannot infer equity simply
                # Return failure with the first imbalance found
                first_imbalance_comm = list(imbalances.keys())[0]
                return Failure(ImbalanceError(first_imbalance_comm, imbalances[first_imbalance_comm]))
        else: # There are elided amounts, proceed with existing elision logic
            # This part adapts the original elision logic to use the pre-calculated commodity_sums
            # and operate on the current_tx_copy.

            actual_elided_postings = [current_tx_copy.postings[i] for i in elided_postings_indices]

            # Removed the redundant InsufficientPostingsError check here as it's done by verify_integrity

            if len(actual_elided_postings) == len(current_tx_copy.postings): # All postings were elided
                 # If all postings are elided and there are at least two, cannot balance without commodity context
                 return Failure(NoCommoditiesElidedError())


            if len(actual_elided_postings) == 1:
                elided_posting_original = actual_elided_postings[0]
                elided_idx_in_original_postings = current_tx_copy.postings.index(elided_posting_original) # Find its true index

                # Check imbalances based on *already calculated* commodity_sums
                current_imbalances = {c: s for c, s in commodity_sums.items() if s != Decimal(0)}

                if len(current_imbalances) == 1:
                    comm, net_sum = list(current_imbalances.items())[0]
                    
                    # Use the new add_comment method
                    modified_posting = replace(
                        elided_posting_original,
                        amount=Amount(quantity=-net_sum, commodity=comm),
                    ).add_comment(Comment("auto-balanced"))
                    
                    current_tx_copy.postings[elided_idx_in_original_postings] = modified_posting
                    return Success(current_tx_copy)
                
                elif not current_imbalances: # All sums are zero, elided amount must be zero
                    if commodity_sums: # If there were any commodities at all
                        comm_to_use = list(commodity_sums.keys())[0]
                        # Use the new add_comment method
                        modified_posting = replace(
                            elided_posting_original,
                            amount=Amount(quantity=Decimal(0), commodity=comm_to_use),
                        ).add_comment(Comment("auto-balanced"))
                        current_tx_copy.postings[elided_idx_in_original_postings] = modified_posting
                        return Success(current_tx_copy)
                    else: # No commodities at all in the transaction, cannot infer for elided
                        return Failure(NoCommoditiesElidedError())
                else: # Multiple imbalances, cannot resolve single elided amount
                    # Return failure with the first imbalance found
                    first_imbalance_comm = list(current_imbalances.keys())[0]
                    return Failure(UnresolvedElidedAmountError(first_imbalance_comm))

            # Multiple elided postings
            # This part needs to handle the case where multiple elided postings exist.
            # The original logic had checks for:
            # - All sums zero: fill elided with 0 of a common commodity.
            # - Number of imbalances == number of elided: try to match them.
            # - Else: Ambiguous or MultipleCommoditiesRemaining.

            # Check if all explicit sums are zero.
            all_sums_zero = all(s == Decimal(0) for s in commodity_sums.values())
            if all_sums_zero:
                if commodity_sums: # At least one commodity was present
                    comm_to_use = list(commodity_sums.keys())[0]
                    for i in elided_postings_indices:
                        original_posting = current_tx_copy.postings[i]
                        # Use the new add_comment method
                        current_tx_copy.postings[i] = replace(original_posting, amount=Amount(Decimal(0), comm_to_use)).add_comment(Comment("auto-balanced"))
                    return Success(current_tx_copy)
                else: # No commodities at all, and all postings elided (covered by earlier check)
                    return Failure(NoCommoditiesElidedError()) # Should be caught earlier

            # If sums are not all zero, and multiple elisions, it's ambiguous or potentially resolvable
            # The original code had logic to try and match imbalances to elided postings if the counts matched.
            # Let's re-integrate that part.
            current_imbalances = {c: s for c, s in commodity_sums.items() if s != Decimal(0)}
            if len(current_imbalances) == len(actual_elided_postings):
                 # Attempt to match imbalances to elided postings based on order
                 # This assumes a specific ordering which might not always be correct,
                 # but it's how the original logic seemed to work for the test case.
                 imbalance_items = list(current_imbalances.items()) # Get a consistent order
                 for i, elided_idx in enumerate(elided_postings_indices):
                     if i < len(imbalance_items): # Ensure we don't go out of bounds
                         comm, net_sum = imbalance_items[i]
                         original_posting = current_tx_copy.postings[elided_idx]
                         # Use the new add_comment method
                         current_tx_copy.postings[elided_idx] = replace(
                             original_posting,
                             amount=Amount(quantity=-net_sum, commodity=comm),
                         ).add_comment(Comment("auto-balanced"))
                     else:
                         # If there are more elided postings than imbalances, the remaining ones should be zero
                         original_posting = current_tx_copy.postings[elided_idx]
                         # Need a commodity for the zero amount. Use the first commodity from sums if available.
                         comm_to_use = list(commodity_sums.keys())[0] if commodity_sums else Commodity("USD") # Default if no commodities at all
                         # Use the new add_comment method
                         current_tx_copy.postings[elided_idx] = replace(
                             original_posting,
                             amount=Amount(quantity=Decimal(0), commodity=comm_to_use),
                         ).add_comment(Comment("auto-balanced"))
                 return Success(current_tx_copy)

            # If counts don't match, or other complex multi-elision scenarios
            if commodity_sums:
                 # If there's only one commodity with a non-zero sum, but multiple elided postings, it's ambiguous
                 if len(current_imbalances) == 1:
                     return Failure(AmbiguousElidedAmountError(list(current_imbalances.keys())[0]))
                 # If there are multiple commodities with non-zero sums and multiple elided postings, and counts don't match
                 elif len(current_imbalances) > 1:
                      return Failure(MultipleCommoditiesRemainingError(list(current_imbalances.keys())))
                 # If there are no imbalances but multiple elided postings (should be caught by all_sums_zero case)
                 # This case should not be reached if all_sums_zero is handled correctly.
                 pass # Should not happen

            # Fallback for unhandled complex elision cases
            # This part might need more specific error types depending on the exact scenario.
            # For now, a general unresolved error if we reach here with elided postings and not successful.
            # This part might need further refinement based on testing.
            if actual_elided_postings: # If we still have elided postings and haven't returned Success
                 # This is a catch-all for complex elision that wasn't resolved.
                 # The specific error might depend on the state of commodity_sums.
                 if commodity_sums:
                      # If there are imbalances, it's unresolved
                      if any(s != Decimal(0) for s in commodity_sums.values()):
                           # Pick one of the imbalanced commodities for the error message
                           first_imbalanced_comm = next((c for c, s in commodity_sums.items() if s != Decimal(0)), Commodity("USD")) # Default if somehow no imbalances found here
                           return Failure(UnresolvedElidedAmountError(first_imbalanced_comm))
                      else:
                           # If all sums are zero but multiple elided, it's ambiguous (should be caught earlier)
                           if len(actual_elided_postings) > 1:
                                return Failure(AmbiguousElidedAmountError(list(commodity_sums.keys())[0] if commodity_sums else Commodity("USD")))
                           # If all sums are zero and one elided (should be caught earlier)
                           # This case should result in a Success with 0 amount.
                           pass # Should not happen if single elided case is handled.
                 else: # No commodities at all, and elided postings exist
                      return Failure(NoCommoditiesElidedError()) # Should be caught earlier

            # If we reach here, it means there were elided postings, but none of the specific elision
            # resolution cases matched, and no clear error condition was met within the elision block.
            # This might indicate a logical gap or an unhandled scenario.
            # For robustness, return a general failure if elided postings were present but not resolved.
            # This might need a more specific error type.
            # For now, let's assume the ImbalanceError is a reasonable fallback if sums are not zero.
            # If sums *are* zero but elided postings remain (shouldn't happen after successful elision),
            # it's an internal logic error.
            
            # This final fallback should ideally not be reached if elision logic is complete.
            # If we are here, it means elided postings were present but not resolved.
            # The most likely scenario is an unresolved imbalance.
            final_imbalances = {c: s for c, s in commodity_sums.items() if s != Decimal(0)}
            if final_imbalances:
                 first_imbalanced_comm = list(final_imbalances.keys())[0]
                 return Failure(ImbalanceError(first_imbalanced_comm, final_imbalances[first_imbalanced_comm]))
            else:
                 # If no imbalances but elided postings remain, this is an internal error.
                 # This case should be covered by the all_sums_zero block for multiple elided,
                 # or the single elided zero balance case.
                 # If we somehow reach here, it's a logic error.
                 return Failure(TransactionBalanceError("Internal logic error: Elided postings remain but no imbalances found."))

@dataclass
class Include(PositionAware["Include"]):

    filename: str
    journal: Optional["Journal"] = None
    source_location: Optional["SourceLocation"] = None

    def to_journal_string(self) -> str:
        return f"include {self.filename}"


@dataclass
class AccountDirective(PositionAware["AccountDirective"]):
    """An account directive"""

    name: AccountName
    comment: Optional[Comment] = None
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return f"account {self.name}{' ' + self.comment.to_journal_string() if self.comment else ''}"

    def to_journal_string(self) -> str:
        s = f"account {self.name.to_journal_string()}"
        if self.comment:
            s += f" {self.comment.to_journal_string()}"
        return s


@dataclass
class Price(PositionAware["Price"]):
    """A price"""

    date: date
    commodity: Commodity
    amount: Amount
    source_location: Optional["SourceLocation"] = None


@dataclass
class MarketPrice(PositionAware["MarketPrice"]):
    """A market price directive (P directive)"""

    date: date
    commodity: Commodity  # The commodity being priced
    unit_price: (
        Amount  # The price per unit (Amount includes quantity and price commodity)
    )
    comment: Optional[Comment] = None  # Add comment field
    source_location: Optional["SourceLocation"] = None

    def to_journal_string(self) -> str:
        s = f"P {self.date.strftime('%Y-%m-%d')}"
        s += f" {self.commodity.to_journal_string()} {self.unit_price.to_journal_string()}"
        if self.comment:
            s += f" {self.comment.to_journal_string()}"
        return s


@dataclass
class Alias(PositionAware["Alias"]):
    """An account alias directive"""

    pattern: str
    target_account: AccountName
    source_location: Optional["SourceLocation"] = None

    def to_journal_string(self) -> str:
        return f"alias {self.pattern} = {self.target_account.to_journal_string()}"


@dataclass
class JournalEntry(PositionAware["JournalEntry"]):
    transaction: Optional[Transaction] = None
    include: Optional[Include] = None
    commodity_directive: Optional[CommodityDirective] = None
    account_directive: Optional[AccountDirective] = None
    alias: Optional[Alias] = None
    market_price: Optional[MarketPrice] = None
    comment: Optional[Comment] = None
    source_location: Optional["SourceLocation"] = None

    def to_journal_string(self) -> str:
        r = []
        if self.source_location:
            r.append(
                Comment(
                    comment=f"{self.source_location.filename}:{self.source_location.offset}:{self.source_location.length}"
                ).to_journal_string()
            )
        if self.transaction:
            r.append(self.transaction.to_journal_string())
        elif self.include:
            r.append(self.include.to_journal_string())
        elif self.commodity_directive:
            r.append(self.commodity_directive.to_journal_string())
        elif self.account_directive:
            r.append(self.account_directive.to_journal_string())
        elif self.alias:
            r.append(self.alias.to_journal_string())
        elif self.market_price:
            r.append(self.market_price.to_journal_string())
        elif self.comment:
            r.append(self.comment.to_journal_string())
        else:
            raise Exception("Unexpected journal entry type")
        return "\n".join(r)

    @staticmethod
    def create(
        item: (
            Transaction
            | Include
            | CommodityDirective
            | AccountDirective
            | Alias
            | MarketPrice
            | Comment  # Add Comment to type hint
        ),
    ):
        if isinstance(item, Transaction):
            return JournalEntry(transaction=item)
        if isinstance(item, Include):
            return JournalEntry(include=item)
        if isinstance(item, CommodityDirective):
            return JournalEntry(commodity_directive=item)
        if isinstance(item, AccountDirective):
            return JournalEntry(account_directive=item)
        if isinstance(item, Alias):
            return JournalEntry(alias=item)
        if isinstance(item, MarketPrice):
            return JournalEntry(market_price=item)
        if isinstance(item, Comment):
            return JournalEntry(comment=item)
        raise Exception(f"Unexpected value {item}")


@dataclass
class Journal(PositionAware["Journal"]):
    """A journal"""

    entries: List[JournalEntry] = field(default_factory=list)
    source_location: Optional["SourceLocation"] = None

    def set_filename(self, filename: Path, file_content: str) -> Self:
        # return Self with updated source_location for each entry
        return replace(
            self,
            entries=[
                entry.set_filename(filename, file_content) for entry in self.entries
            ],
            source_location=SourceLocation(filename=filename, offset=0, length=0),
        )        

    def __len__(self):
        return len(self.entries)

    def to_journal_string(self) -> str:
        return "\n\n".join([entry.to_journal_string() for entry in self.entries])

    def flatten(self) -> "Journal":
        """Returns a new Journal with includes flattened."""
        flattened_entries: List[JournalEntry] = []
        for entry in self.entries:
            if entry.include and entry.include.journal:
                # Recursively flatten the included journal and extend the list
                flattened_entries.append(
                    JournalEntry(
                        comment=Comment(
                            comment=f"begin {entry.include.to_journal_string()}",
                            source_location=entry.include.source_location,
                        ),
                        source_location=entry.include.source_location,
                    )
                )
                flattened_entries.extend(entry.include.journal.flatten().entries)
                flattened_entries.append(
                    JournalEntry(
                        comment=Comment(
                            comment=f"end {entry.include.to_journal_string()}",
                            source_location=entry.include.source_location,
                        ),
                        source_location=entry.include.source_location,
                    )
                )
            else:
                # Add non-include entries or includes without a journal directly
                flattened_entries.append(entry)

        # Create a new Journal instance with the flattened entries
        return Journal(entries=flattened_entries, source_location=self.source_location)

    def balance(self) -> Result["Journal", TransactionBalanceError]:
        """
        Attempts to balance all transactions within the journal.
        Returns a new Journal with balanced transactions if all transactions balance successfully.
        If any transaction fails to balance, the entire balancing operation fails.
        """
        balanced_entries: List[JournalEntry] = []
        for entry in self.entries:
            if entry.transaction:
                balance_result = entry.transaction.balance()
                if isinstance(balance_result, Success):
                    balanced_transaction = balance_result.unwrap()
                    balanced_entries.append(replace(entry, transaction=balanced_transaction))
                else:
                    # Fail the entire balancing operation if any transaction fails
                    return Failure(balance_result.failure())
            else:
                # Non-transaction entries are retained unchanged
                balanced_entries.append(entry)
        return Success(Journal(entries=balanced_entries, source_location=self.source_location))

    @staticmethod
    def parse_from_file(filename: str, *, query: Optional["Filters"] = None, flat: bool = False, strip: bool = False) -> Result["Journal", Union[ParseError, str, ValueError]]:
        """
        Parses an hledger journal file and returns a Journal object.

        Optionally filters, flattens, and strips location information.
        """
        if not isinstance(filename, Path):
            filename = Path(filename)

        # Define helper functions for the pipeline
        def _apply_flatten(journal: Journal) -> Result[Journal, ValueError]:
            if flat:
                return Success(journal.flatten())
            return Success(journal)

        def _apply_strip(journal: Journal) -> Result[Journal, ValueError]:
            if strip:
                return Success(journal.strip_loc())
            return Success(journal)

        def _apply_filters_to_journal(journal: Journal) -> Result[Journal, ValueError]:
            if query:
                filtered_entries = query.apply_to_entries(journal.entries)
                return Success(replace(journal, entries=filtered_entries))
            return Success(journal)


        # Use flow and bind to chain the file reading, parsing, and processing operations
        return flow(
            filename,
            Journal.read_file_content, # Use the static method
            bind(
                lambda file_content: Journal.parse_from_content( # Use the static method
                    file_content, filename
                )
            ),
            bind(lambda journal: journal.recursive_include(filename)), # Use the instance method
            bind(_apply_flatten), # Apply flattening
            bind(_apply_filters_to_journal), # Apply filtering
            bind(_apply_strip), # Apply stripping
        )

    @staticmethod
    @safe
    def read_file_content(filename: Path) -> str:
        return filename.read_text()

    @staticmethod
    def parse_from_content(content: str, filename: Path) -> Result["Journal", Union[ParseError, str]]:
        """Parses hledger journal content string and returns a Journal object."""
        from src.hledger_parser import HledgerParsers  # Import here to avoid circular dependency
        return HledgerParsers.journal.parse(content).map(lambda j: j.set_filename(filename, content))

    def recursive_include(self, journal_fn: Path) -> Result["Journal", str]:
        parent_journal_dir = Path(journal_fn).parent

        def include_one(entry: JournalEntry) -> JournalEntry:
            if not entry.include:
                return entry
            include = entry.include
            # Recursively parse included journal and handle the Result
            included_journal_result = Journal.parse_from_file( # Use the static method
                Path(parent_journal_dir, include.filename)
            )

            # Use pattern matching to handle the Result
            match included_journal_result:
                case Success(included_journal):
                    include = replace(entry.include, journal=included_journal)
                    return replace(entry, include=include)
                case Failure(error):
                    # Handle the error, perhaps by logging or returning a JournalEntry indicating the error
                    # For now, we'll return the original entry, but this should be improved
                    print(f"Error including file {include.filename}: {error}")
                    return entry
            raise Exception("Inexhaustive match!")

        entries = [include_one(i) for i in self.entries] # Use self.entries
        return Success(replace(self, entries=entries)) # Use self

    def verify(self) -> Result[None, List[VerificationError]]:
        """
        Performs comprehensive verification of the journal.

        Checks include:
        1. Stock/option acquisitions use dated subaccounts.
        2. Individual transaction integrity and balance.
        3. Successful balance sheet calculation.

        Returns Success(None) if all checks pass, otherwise Failure containing a list of VerificationError objects.
        """
        from src.balance import BalanceSheet # Import locally to avoid circular dependency

        verification_errors: List[VerificationError] = []

        # Check 1: Stock/option acquisitions use dated subaccounts
        for entry in self.entries:
            if entry.transaction:
                tx = entry.transaction
                maybe_acq_posting = tx.get_asset_acquisition_posting()
                if isinstance(maybe_acq_posting, Some):
                    acq_posting = maybe_acq_posting.unwrap()
                    # Check commodity type again just to be sure (though get_asset_acquisition_posting should handle this)
                    if acq_posting.amount and (acq_posting.amount.commodity.isStock() or acq_posting.amount.commodity.isOption()):
                        if not acq_posting.account.isDatedSubaccount():
                            verification_errors.append(AcquisitionMissingDatedSubaccountError(acq_posting))

        # Check 2: Individual transaction verification
        for entry in self.entries:
            if entry.transaction:
                tx = entry.transaction
                tx_verify_result = tx.verify() # This now checks integrity and balance
                if isinstance(tx_verify_result, Failure):
                    # Wrap the TransactionValidationError in a VerificationError
                    # Need to handle potential list of errors if verify changes later
                    err = tx_verify_result.failure()
                    # Attempt to get source location from the transaction itself
                    loc = tx.source_location
                    # If the error itself has a location (less likely for tx errors), prefer that? No, stick to tx location.
                    verification_errors.append(VerificationError(str(err), loc))


        # Check 3: Balance Sheet Calculation Errors
        balance_sheet_build_result = BalanceSheet.from_journal(self)
        if isinstance(balance_sheet_build_result, Failure):
            # from_journal now returns Failure(List[BalanceSheetCalculationError])
            # These errors already have source locations if available from the transaction
            # that caused the error during its apply_transaction call.
            bs_errors = balance_sheet_build_result.failure()
            verification_errors.extend(bs_errors) # bs_errors is already List[BalanceSheetCalculationError]

        if verification_errors:
            return Failure(verification_errors)
        else:
            return Success(None)
