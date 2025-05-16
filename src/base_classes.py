from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from .common_types import (
    SourceLocation,
    PositionAware,
    CommodityKind,
    Comment, 
)

import re

CASH_TICKERS = ["USD", "PLN", "EUR"]
CRYPTO_TICKERS = ["BTC", "ETH", "XRP", "LTC", "BCH", "ADA", "DOT", "UNI", "LINK", "SOL", "PseudoUSD", "BUSD", "FDUSD", "USDT", "USDC", "FTM", "ALGO"]
SIMPLE_CURRENCIES = ["$"]


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
        return self.name in ["USD", "PLN", "EUR"] # Use hardcoded cash tickers for now

    def isCrypto(self) -> bool:
        """Checks if the commodity is a cryptocurrency."""
        return self.name in ["BTC", "ETH", "XRP", "LTC", "BCH", "ADA", "DOT", "UNI", "LINK", "SOL", "PseudoUSD", "BUSD", "FDUSD", "USDT", "USDC", "FTM", "ALGO"] # Use hardcoded crypto tickers for now

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


