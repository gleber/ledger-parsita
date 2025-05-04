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

CASH_TICKERS = ["USD", "PLN", "EUR"]
CRYPTO_TICKERS = ["BTC", "ETH", "XRP", "LTC", "BCH", "ADA", "DOT", "UNI", "LINK", "SOL", "PseudoUSD", "BUSD", "FDUSD", "USDT", "USDC", "FTM", "ALGO"]
SIMPLE_CURRENCIES = ["$"]

Output = TypeVar("Output")


@dataclass
class BaseFilter(ABC):
    """Abstract base class for all filter conditions."""

    @abstractmethod
    def is_matching(self, transaction: "Transaction") -> bool:
        """Checks if the transaction matches the filter condition."""
        pass


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

    def _calculate_line_column(self, content: str, offset: int) -> tuple[int, int]:
        """Calculates the 1-based line and column number from an offset."""
        line = 1
        column = 1
        for i, char in enumerate(content):
            if i == offset:
                break
            if char == "\n":
                line += 1
                column = 1
            else:
                column += 1
        return line, column

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
            line, column = self._calculate_line_column(file_content, start_offset)
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
        kinds = {
            CommodityKind.CASH: self.isCash(),
            CommodityKind.CRYPTO: self.isCrypto(),
            CommodityKind.OPTION: self.isOption(),
            CommodityKind.STOCK: self.isStock(),
        }
        f = defaultdict(list)
        for k, v in kinds.items():
            f[v].append(k)
        if len(f[True]) != 1:
            raise Exception(f"Invalid commodity {self.name} type: {kinds}")
        return f[True][0]


    def isCash(self) -> bool:
        """Checks if the commodity is a cash commodity (USD or PLN)."""
        return self.name in CASH_TICKERS

    def isStock(self) -> bool:
        """Checks if the commodity is likely a stock (simple ticker check)."""
        # Check for 1-5 uppercase letters and ensure it's not a known cryptocurrency or cash
        return bool(re.fullmatch(r"[A-Z\.]{1,5}", self.name)) and not self.isCash() and not self.isCrypto()

    def isCrypto(self) -> bool:
        """Checks if the commodity is a known cryptocurrency."""
        # Predefined list of common cryptocurrencies
        return self.name in CRYPTO_TICKERS

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


class TransactionSide(Enum):
    UNKNOWN = "UNKNOWN"
    OPEN = "OPEN"
    CLOSE = "CLOSE"


@dataclass(unsafe_hash=True)
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
    
    def side(self) -> TransactionSide:
        return TransactionSide.UNKNOWN

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

        # Attempt to infer cost (Variant 3: two postings, different commodities)
        if len(self.postings) == 2:
            posting1 = self.postings[0]
            posting2 = self.postings[1]

            # Ensure both postings have amounts and different commodities
            if posting1.amount is not None and posting2.amount is not None and posting1.amount.commodity != posting2.amount.commodity:
                # Determine which posting is the target and which is the other
                other_posting = None
                if target_posting == posting1:
                    other_posting = posting2
                elif target_posting == posting2:
                    other_posting = posting1

                if other_posting:
                    # Infer total cost (@@) based on the other posting's amount
                    # The inferred cost amount is the absolute value of the other posting's amount
                    inferred_amount = Amount(abs(other_posting.amount.quantity), other_posting.amount.commodity)
                    return Cost(kind=CostKind.TotalCost, amount=inferred_amount)

        return None # No explicit cost and inference not possible

    def get_asset_acquisition_posting(self) -> Optional[Posting]:
        """Finds the asset acquisition posting in the transaction, if any."""
        for posting in self.postings:
            if posting.account.isAsset() and posting.account.isDatedSubaccount() and posting.amount is not None and posting.amount.quantity > 0:
                return posting
        return None

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
