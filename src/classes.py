from abc import abstractmethod
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field, fields, replace
from enum import Enum
from pathlib import Path
from typing import List, Optional, Self, Union, Dict, Generic, TypeVar
import datetime
from decimal import Decimal
import re
import bisect
from returns.result import (
    Result,
    Success,
    Failure,
    safe,
)  # Import Result, Success, Failure, safe
from returns.pipeline import flow
from returns.pointfree import bind
from returns.maybe import Maybe, Some, Nothing  # Import Maybe types
from parsita import (
    ParseError,
    ParserContext,
    Parser,
    Reader,
    lit,
    reg,
    rep,
    rep1,
    repsep,
    opt,
)  # Import necessary parsita components
from parsita.state import Continue, Input, Output, State  # Import from parsita.state
from parsita.util import splat  # Import splat

from src.transaction_balance import _transaction_balance  # Import the new function

# Import error classes from the new errors module
from .errors import (
    TransactionValidationError,
    TransactionIntegrityError,
    MissingDateError,
    MissingDescriptionError,
    InsufficientPostingsError,
    InvalidPostingError,
    TransactionBalanceError,
    ImbalanceError,
    AmbiguousElidedAmountError,
    UnresolvedElidedAmountError,
    NoCommoditiesElidedError,
    MultipleCommoditiesRemainingError,
    VerificationError,
    AcquisitionMissingDatedSubaccountError,
    BalanceSheetCalculationError,
)

# Import common types from the new common_types module
from .common_types import (
    SourceCacheManager,
    source_cache_manager,
    PositionAware,
    CostKind,
    SourceLocation,
    sl,
    Comment,
    CommodityKind,
    AmountStyle,
    Price,
    Status,
    Tag,
    PositionEffect,
)

from .base_classes import (
    Amount,
    Commodity,
    AccountName,
)


@dataclass
class CapitalGainResult:
    """Represents the result of a capital gain/loss calculation for a matched sale portion."""

    closing_posting: "Posting"
    opening_lot_original_posting: (
        "Posting"  # Reference to the original posting of the matched lot
    )
    matched_quantity: "Amount"
    cost_basis: "Amount"  # Total cost basis for the matched quantity
    proceeds: "Amount"  # Total proceeds for the matched quantity
    gain_loss: "Amount"  # Calculated gain or loss
    closing_date: datetime.date  # Add closing date
    acquisition_date: datetime.date  # Add acquisition date


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
    status: Optional[Status] = None
    date: Optional[datetime.date] = None
    tags: List[Tag] = field(default_factory=list)
    source_location: Optional["SourceLocation"] = None

    def get_effect(self) -> PositionEffect:
        """Determines the effect of this posting on asset positions."""
        if not self.account:
            return PositionEffect.UNKNOWN

        if self.balance is not None and self.amount is None:
            # If balance is provided, we can't determine the effect
            return PositionEffect.ASSERT_BALANCE
        
        if not self.amount:
            return PositionEffect.UNKNOWN

        is_cash_commodity = self.amount.commodity.isCash()
        has_short_tag = any(tag.name == "type" and tag.value == "short" for tag in self.tags)

       
        if is_cash_commodity:
            return PositionEffect.CASH_MOVEMENT

        if self.amount.quantity > 0:  # Buying or covering short
            if has_short_tag: # Short tag is both for opening shorts and closing shorts.
                return PositionEffect.CLOSE_SHORT
            # If not tagged short, it's either opening a long.
            return PositionEffect.OPEN_LONG # Could also be CLOSE_SHORT
        elif self.amount.quantity < 0:  # Selling or opening short
            if has_short_tag:
                return PositionEffect.OPEN_SHORT
            else:
                return PositionEffect.CLOSE_LONG # Could also be OPEN_SHORT if not tagged, but less likely by convention

        return PositionEffect.UNKNOWN

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

    def add_comment(self, comment_to_add: Comment) -> "Posting":
        """Adds a comment to the posting, appending to any existing comment."""
        if self.comment:
            # Append to existing comment
            new_comment_text = f"{self.comment.comment} {comment_to_add.comment}"
            updated_comment = Comment(
                comment=new_comment_text, source_location=self.comment.source_location
            )  # Keep original comment's source location
        else:
            # Set the new comment
            updated_comment = comment_to_add  # Use the new comment directly

        # Return a new Posting object with the updated comment
        return replace(self, comment=updated_comment)


@dataclass(unsafe_hash=True)
class Transaction(PositionAware["Transaction"]):
    """A transaction in the ledger"""

    date: datetime.date
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
                    if other_posting.amount:  # Ensure other_posting has an amount
                        inferred_amount = Amount(
                            abs(other_posting.amount.quantity),
                            other_posting.amount.commodity,
                        )
                        return Cost(kind=CostKind.TotalCost, amount=inferred_amount)

                # Case 2: Same commodities (e.g., RSU-like income leading to asset acquisition)
                # Replace target_posting.isOpening() with a check for OPEN_LONG effect
                elif amt1.commodity == amt2.commodity and target_posting.get_effect() == PositionEffect.OPEN_LONG:
                    # target_posting is the asset acquisition (e.g., +4 GOOG)
                    # The other posting should be the income offset (e.g., -4 GOOG from income:...)
                    other_posting = p2 if target_posting == p1 else p1

                    # Check if other_posting is from an income account and has the opposite quantity of target_posting
                    if (
                        other_posting.amount
                        and target_posting.amount
                        and other_posting.amount.quantity
                        == -target_posting.amount.quantity
                        and other_posting.account.name.startswith("income:")
                    ):

                        # Infer $0 cost basis.
                        # Determine currency for the $0 cost: use a cash commodity from the transaction if available, else default to USD.
                        zero_cost_currency = Commodity("USD")  # Default
                        for (
                            post_in_tx
                        ) in (
                            self.postings
                        ):  # self.postings refers to the transaction's postings
                            if (
                                post_in_tx.amount
                                and post_in_tx.amount.commodity.isCash()
                            ):
                                zero_cost_currency = post_in_tx.amount.commodity
                                break

                        zero_cost_amount = Amount(Decimal(0), zero_cost_currency)
                        return Cost(kind=CostKind.UnitCost, amount=zero_cost_amount)

        return None  # No explicit cost and inference not possible

    def get_asset_acquisition_posting(self) -> Maybe[Posting]:
        """Finds the asset acquisition posting in the transaction, if any. Returns Maybe."""
        for posting in self.postings:
            # Check if it's an asset, has an amount, and quantity is positive (acquisition)
            # No longer checking isDatedSubaccount here, as that's part of the verification step.
            if (
                posting.account.isAsset()
                and posting.amount is not None
                and posting.amount.quantity > 0
            ):
                # Check if it's stock or option
                if (
                    posting.amount.commodity.isStock()
                    or posting.amount.commodity.isOption()
                ):
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
                and other_posting.account
                != acquisition_posting.account  # Ensure it's not the same asset account
            ):
                return other_posting
        return None

    def calculate_cost_basis_per_unit(
        self, acquisition_posting: Posting, cost_basis_posting: Posting
    ) -> Optional[Amount]:
        """Calculates the cost basis per unit for an asset acquisition."""
        if acquisition_posting.amount is None or cost_basis_posting.amount is None:
            return None  # Should not happen if called after finding valid postings

        if acquisition_posting.amount.quantity != 0:
            cost_basis_per_unit_value = abs(
                cost_basis_posting.amount.quantity / acquisition_posting.amount.quantity
            )
            return Amount(
                cost_basis_per_unit_value, cost_basis_posting.amount.commodity
            )
        else:
            return None  # Handle zero quantity acquisition

    def verify_integrity(self) -> Result[None, TransactionIntegrityError]:
        """
        Checks if the Transaction object has all its essential components present and in a basic valid state.
        Assumes the transaction is already parsed.
        """
        if not isinstance(
            self.date, datetime.date
        ):  # datetime.date, not datetime.datetime specifically
            return Failure(MissingDateError())

        if isinstance(self.payee, str) and not self.payee.strip():
            return Failure(MissingDescriptionError())
        elif not isinstance(
            self.payee, (str, AccountName)
        ):  # Should be str or AccountName
            return Failure(
                MissingDescriptionError(
                    "Transaction payee/description has invalid type."
                )
            )

        if len(self.postings) < 2:
            return Failure(InsufficientPostingsError())

        for i, p in enumerate(self.postings):
            if not isinstance(p, Posting):
                return Failure(
                    InvalidPostingError(
                        f"Item at index {i} in postings is not a Posting object."
                    )
                )
            if not isinstance(p.account, AccountName):
                return Failure(
                    InvalidPostingError(
                        f"Posting {i} has an invalid account type: {type(p.account)}."
                    )
                )
            if p.amount is not None:  # Amount can be None for elided amounts
                if not isinstance(p.amount, Amount):
                    return Failure(
                        InvalidPostingError(
                            f"Posting {i} has an invalid amount type: {type(p.amount)}."
                        )
                    )
                if not isinstance(p.amount.quantity, Decimal):
                    return Failure(
                        InvalidPostingError(
                            f"Posting {i} amount quantity is not a Decimal: {type(p.amount.quantity)}."
                        )
                    )
                if not isinstance(p.amount.commodity, Commodity):
                    return Failure(
                        InvalidPostingError(
                            f"Posting {i} amount commodity is not a Commodity: {type(p.amount.commodity)}."
                        )
                    )
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

    def balance(self) -> Result["Transaction", TransactionBalanceError | TransactionIntegrityError]:
        """
        Balances the transaction by inferring elided values.
        Returns a new Transaction object with inferred values or an error if balancing fails.
        """

        integrity_check = self.verify_integrity()
        if isinstance(integrity_check, Failure):
            return integrity_check

        # Attempt to balance the transaction
        # The balance method now directly calls the imported _transaction_balance
        return _transaction_balance(self)

    def is_balanced(self) -> Result[None, TransactionBalanceError | TransactionIntegrityError]:
        """
        Checks if the transaction can be balanced, either as-is or by inferring elided values.
        Returns Success(None) if balanced or can be balanced, or Failure with an appropriate error if not.
        """
        # Check integrity, then try to balance, all using returns chaining
        return self.balance().map(lambda _: None)


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
class MarketPrice(PositionAware["MarketPrice"]):
    """A market price directive (P directive)"""

    date: datetime.date
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
