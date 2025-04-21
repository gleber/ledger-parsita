from abc import abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field, fields, replace # Import replace
from enum import Enum
from typing import List, Optional, Self, Union, Dict, Generic, TypeVar
from datetime import date, datetime
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
        return replace(self, source_location=SourceLocation(filename=filename, offset=start, length=length))

    def strip_loc(self):
        stripped_fields = {field.name: getattr(self, field.name) for field in fields(self)}
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

class CostKind(Enum):
    UnitCost = "@"
    TotalCost = "@@"

    def __str__(self):
        return self.value


@dataclass
class SourceLocation:
    """A location in a source file"""
    filename: str
    offset: int
    length: int


@dataclass
class Commodity(PositionAware["Commodity"]):
    """A commodity"""
    name: str
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return self.name


@dataclass
class Amount(PositionAware["Amount"]):
    """An amount"""
    quantity: Decimal
    commodity: Commodity
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return f"{self.quantity} {self.commodity}"



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



@dataclass
class AccountName(PositionAware["AccountName"]):
    """An account name"""
    parts: List[str]
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return ":".join(self.parts)

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


@dataclass
class Posting(PositionAware["Posting"]):
    """A posting in a transaction"""

    account: 'AccountName'
    amount: Optional['Amount'] = None
    cost: Optional[Cost] = None
    balance: Optional[Amount] = None
    comment: Optional[str] = None
    status: Optional[str] = None
    date: Optional[date] = None
    datetime: Optional[datetime] = None
    tags: List[Tag] = field(default_factory=list)
    source_location: Optional["SourceLocation"] = None



@dataclass
class MixedAmount(PositionAware["MixedAmount"]):
    """A mixed amount"""
    amounts: List[Amount] = field(default_factory=list)
    source_location: Optional["SourceLocation"] = None



@dataclass
class Transaction(PositionAware["Transaction"]):
    """A transaction in the ledger"""

    date: date
    payee: Union[str, AccountName]
    postings: List[Posting] = field(default_factory=list)
    comments: List[str] = field(default_factory=list) # Added comments field
    comment: Optional[str] = None
    code: Optional[str] = None
    status: Optional[Status] = None
    source_location: Optional["SourceLocation"] = None



@dataclass
class AccountDirective(PositionAware["AccountDirective"]):
    """An account directive"""
    name: str
    type: Optional[str] = None
    note: Optional[str] = None
    alias: Optional[str] = None
    payee: Optional[str] = None
    check: Optional[str] = None
    eval: Optional[str] = None
    assert_expr: Optional[str] = None
    assert_amount: Optional[str] = None
    close: Optional[str] = None
    source_location: Optional["SourceLocation"] = None



@dataclass
class Price(PositionAware["Price"]):
    """A price"""
    date: date
    commodity: Commodity
    amount: Amount
    source_location: Optional["SourceLocation"] = None



@dataclass
class File(PositionAware["File"]):
    """A ledger file"""

    path: str
    included_files: List["File"] = field(default_factory=list)
    source_location: Optional["SourceLocation"] = None


@dataclass
class MarketPrice(PositionAware["MarketPrice"]):
    """A price in the market"""

    date: date
    amount: Amount  # TODO: should be a mixed amount
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
class JournalSource(PositionAware["JournalSource"]):
    """A journal file and parsed transactions & directives."""

    file: File
    transactions: List["Transaction"] = field(default_factory=list)
    directives: List[Union["Commodity", "AccountDirective", "Price"]] = field(
        default_factory=list
    )
    default_year: Optional[int] = None
    default_commodity: Optional[str] = None
    decimal_mark: Optional[str] = None
    parent_accounts: List[AccountName] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    transaction_count: int = 0
    timeclock_entries: List[str] = field(default_factory=list)
    include_file_stack: List[str] = field(default_factory=list)
    declared_payees: List[str] = field(default_factory=list)
    declared_tags: List[str] = field(default_factory=list)
    declared_accounts: List[str] = field(default_factory=list)
    declared_account_tags: Dict[str, List[Tag]] = field(default_factory=dict)
    declared_account_types: Dict[str, List[str]] = field(default_factory=dict)
    account_types: Dict[str, str] = field(default_factory=dict)
    declared_commodities: Dict[str, Commodity] = field(default_factory=dict)
    inferred_commodity_styles: Dict[str, AmountStyle] = field(default_factory=dict)
    global_commodity_styles: Dict[str, AmountStyle] = field(default_factory=dict)
    price_directives: List[Price] = field(default_factory=list)
    inferred_market_prices: List[MarketPrice] = field(default_factory=list)
    txn_modifiers: List[str] = field(default_factory=list)
    periodic_txns: List[str] = field(default_factory=list)
    final_comment_lines: Optional[str] = None
    files: List[tuple[str, str]] = field(default_factory=list)
    source_location: Optional["SourceLocation"] = None


@dataclass
class Journal(PositionAware["Journal"]):
    """A journal"""
    sources: List[JournalSource] = field(default_factory=list)
    source_location: Optional["SourceLocation"] = None


@dataclass
class Report(PositionAware["Report"]):
    """A report"""
    name: str
    source_location: Optional["SourceLocation"] = None
