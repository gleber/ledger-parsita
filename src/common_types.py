from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field, fields, replace
from enum import Enum
from pathlib import Path
from typing import Optional, Self, List, Dict, Generic, TypeVar
from datetime import date # Import date
from decimal import Decimal
import re
import bisect
from parsita.state import Continue, Input, Output, State # Import from parsita.state
from returns.maybe import Maybe # Import Maybe types

# Assuming Commodity and Amount will be in ledger_entities.py,
# but needed for type hints here. Use forward references.
# from .ledger_entities import Commodity, Amount

# Global instance (not a true singleton with __init__)
# This needs to be defined before SourceCacheManager uses it.
source_cache_manager = None # Will be initialized below

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


@dataclass
class AmountStyle(PositionAware["AmountStyle"]):
    """Style of an amount"""

    source_location: Optional["SourceLocation"] = None


@dataclass
class Price(PositionAware["Price"]):
    """A price"""

    date: date
    commodity: "Commodity" # Use forward reference
    amount: "Amount" # Use forward reference
    source_location: Optional["SourceLocation"] = None


@dataclass
class Cost(PositionAware["Cost"]):
    """Amount of a cost"""

    kind: CostKind
    amount: "Amount" # Use forward reference
    source_location: Optional["SourceLocation"] = None

    def __str__(self):
        return f"{{{self.amount}}}"

    def to_journal_string(self) -> str:
        return f"{self.kind.value} {self.amount.to_journal_string()}"


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


class PositionEffect(Enum):
    UNKNOWN = "unknown"
    OPEN_LONG = "open_long"
    CLOSE_LONG = "close_long"
    OPEN_SHORT = "open_short"
    CLOSE_SHORT = "close_short"
    ASSERT_BALANCE = "assert_balance"
    CASH_MOVEMENT = "cash_movement"

    def is_open(self) -> bool:
        return self in (self.OPEN_LONG, self.OPEN_SHORT)
