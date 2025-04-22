from abc import abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field, fields, replace  # Import replace
from enum import Enum
from pathlib import Path
from typing import List, Optional, Self, Union, Dict, Generic, TypeVar
from datetime import date, datetime  # Ensure datetime is imported
from decimal import Decimal

Output = TypeVar("Output")


class PositionAware(Generic[Output]):
    """An object which can cooperate with the positioned parser.

    The ``positioned`` parser calls the ``set_position`` method on values it
    receives. This abstract base class marks those objects that can cooperate
    with ``positioned`` in this way and receive the input position to produce
    the final value.
    """

    def set_position(self, filename: str, start: int, length: int) -> Self:
        return replace(
            self,
            source_location=SourceLocation(
                filename=filename, offset=start, length=length
            ),
        )

    def strip_loc(self):
        stripped_fields = {
            field.name: getattr(self, field.name) for field in fields(self)
        }

        def strip_one(v):
            if isinstance(v, PositionAware):
                return v.strip_loc()
            if isinstance(v, Iterable) and not isinstance(v, str):
                return [strip_one(i) for i in v]
            return v

        for k in stripped_fields.keys():
            stripped_fields[k] = strip_one(stripped_fields[k])
        stripped_fields["source_location"] = None
        return replace(self, **stripped_fields)

    def set_filename(self, filename):
        if not isinstance(self, PositionAware):
            return self
        sub_fields = {field.name: getattr(self, field.name) for field in fields(self)}

        def set_one(v):
            if isinstance(v, PositionAware):
                return v.set_filename(filename)
            if isinstance(v, Iterable) and not isinstance(v, str):
                return [set_one(i) for i in v]
            return v

        for k in sub_fields.keys():
            sub_fields[k] = set_one(sub_fields[k])
        if "source_location" not in sub_fields:
            raise Exception(f"{self} does not have source_location!")
        sl = sub_fields["source_location"]
        if isinstance(sl, SourceLocation) and sl is not None:
            sub_fields["source_location"] = replace(
                sub_fields["source_location"], filename=filename
            )
        return replace(self, **sub_fields)


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


@dataclass
class Comment:
    comment: str
    source_location: Optional["SourceLocation"] = None

    def to_journal_string(self) -> str:
        return f"; {self.comment}"


@dataclass
class Commodity(PositionAware["Commodity"]):
    """A commodity"""

    name: str
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return self.name

    def to_journal_string(self) -> str:
        if not self.name.isalnum():
            return f'"{self.name}"'
        return self.name


@dataclass
class Amount(PositionAware["Amount"]):
    """An amount"""

    quantity: Decimal
    commodity: Commodity
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return f"{self.quantity} {self.commodity}"

    def to_journal_string(self) -> str:
        return f"{self.quantity} {self.commodity.name}"


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


@dataclass
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


class Status(Enum):
    """The status of a transaction or posting"""

    Unmarked = ""
    Pending = "!"
    Cleared = "*"

    def __str__(self):
        return self.value


@dataclass
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
    example_amount: Amount = None
    comment: Optional[Comment] = None
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return f"commodity {self.commodity}{' ' + self.comment.to_journal_string() if self.comment else ''}"

    def to_journal_string(self) -> str:
        s = f"commodity {self.commodity.to_journal_string()}"
        if self.comment:
            s += f" {self.comment.to_journal_string()}"
        return s


@dataclass
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


@dataclass
class Transaction(PositionAware["Transaction"]):
    """A transaction in the ledger"""

    date: date
    payee: Union[str, AccountName]
    postings: List[Posting] = field(default_factory=list)
    comments: List[Comment] = field(default_factory=list)  # Added comments field
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
    time: Optional[datetime] = None  # Optional time component
    comment: Optional[Comment] = None  # Add comment field
    source_location: Optional["SourceLocation"] = None

    def to_journal_string(self) -> str:
        s = f"P {self.date.strftime('%Y-%m-%d')}"
        if self.time:
            s += f" {self.time.strftime('%H:%M:%S')}"
        s += f" {self.commodity.to_journal_string()} {self.unit_price.to_journal_string()}"
        if self.comment:
            s += f" {self.comment.to_journal_string()}"
        return s


@dataclass
class File(PositionAware["File"]):
    """A ledger file"""

    path: str
    included_files: List["File"] = field(default_factory=list)
    source_location: Optional["SourceLocation"] = None


@dataclass
class Account(PositionAware["Account"]):
    """An account in the ledger"""

    name: AccountName
    parent: Optional["Account"] = None
    subaccounts: List["Account"] = field(default_factory=list)
    balance_exclusive: Dict[str, Decimal] = field(default_factory=dict)
    balance_inclusive: Dict[str, Decimal] = field(default_factory=dict)
    source_location: Optional["SourceLocation"] = None


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
        if self.transaction:
            return self.transaction.to_journal_string()
        elif self.include:
            return self.include.to_journal_string()
        elif self.commodity_directive:
            return self.commodity_directive.to_journal_string()
        elif self.account_directive:
            return self.account_directive.to_journal_string()
        elif self.alias:
            return self.alias.to_journal_string()
        elif self.market_price:
            return self.market_price.to_journal_string()
        raise Exception("Unexpected journal entry type")

    @staticmethod
    def create(
        item: (
            Transaction
            | Include
            | CommodityDirective
            | AccountDirective
            | Alias
            | MarketPrice
        ),
    ):  # Add MarketPrice to type hint
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
        if isinstance(item, MarketPrice):  # Add check for MarketPrice
            return JournalEntry(market_price=item)
        if isinstance(item, Comment):
            return JournalEntry(comment=item)
        raise Exception(f"Unexpected value {item}")


@dataclass
class Journal(PositionAware["Journal"]):
    """A journal"""

    entries: List[JournalEntry] = field(default_factory=list)
    source_location: Optional["SourceLocation"] = None

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
                            comment=entry.include.to_journal_string(),
                            source_location=entry.include.source_location,
                        ),
                        source_location=entry.include.source_location,
                    )
                )
                flattened_entries.extend(entry.include.journal.flatten().entries)
            else:
                # Add non-include entries or includes without a journal directly
                flattened_entries.append(entry)

        # Create a new Journal instance with the flattened entries
        return Journal(entries=flattened_entries, source_location=self.source_location)
