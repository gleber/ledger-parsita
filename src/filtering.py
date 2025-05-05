# This file will contain the filtering logic for transactions.

import click
from typing import List, Optional, Union

from parsita import lit, rep, reg, repsep, ParserContext, opt, ParseError

from src.classes import JournalEntry, Transaction, Posting, Amount, AccountName
from datetime import date, datetime, timedelta
from decimal import Decimal
import re
from dataclasses import dataclass, field
from returns.result import Result, safe, Success, Failure
from returns.curry import partial
from abc import ABC, abstractmethod
import calendar

@dataclass
class BaseFilter(ABC):
    """Abstract base class for all filter conditions."""

    @abstractmethod
    def is_matching(self, transaction: "Transaction") -> bool:
        """Checks if the transaction matches the filter condition."""
        pass


# Define filter condition classes
@dataclass
class AccountFilter(BaseFilter):
    pattern: List[str]

    def is_matching(self, transaction: Transaction) -> bool:
        """Checks if any posting in the transaction has an account matching the pattern."""
        account_pattern = ":".join(self.pattern)
        for posting in transaction.postings:
            if re.search(account_pattern, str(posting.account), re.IGNORECASE):
                return True
        return False


@dataclass
class BeforeDateFilter(BaseFilter):
    filter_date: date

    def is_matching(self, transaction: Transaction) -> bool:
        """Checks if the transaction date is before the specified date."""
        return transaction.date < self.filter_date

@dataclass
class AfterDateFilter(BaseFilter):
    filter_date: date

    def is_matching(self, transaction: Transaction) -> bool:
        """Checks if the transaction date is after the specified date."""
        return transaction.date > self.filter_date

@dataclass
class PeriodFilter(BaseFilter):
    start_date: date
    end_date: date

    def is_matching(self, transaction: Transaction) -> bool:
        """Checks if the transaction date falls within the specified period."""
        return self.start_date <= transaction.date <= self.end_date

@dataclass
class DateFilter(BaseFilter):
    start_date: Optional[date]
    end_date: Optional[date]

    def is_matching(self, transaction: Transaction) -> bool:
        """Checks if the transaction date falls within the specified date filter."""
        if self.start_date and self.end_date:
            return self.start_date <= transaction.date <= self.end_date
        elif self.start_date:
            return self.start_date <= transaction.date
        elif self.end_date:
            return transaction.date <= self.end_date
        else:
            return False  # Should not happen with proper parsing


@dataclass
class DescriptionFilter(BaseFilter):
    text: str

    def is_matching(self, transaction: Transaction) -> bool:
        """Checks if the transaction payee contains the specified text (case-insensitive)."""
        if isinstance(transaction.payee, str):
            return self.text.lower() in transaction.payee.lower()
        elif isinstance(transaction.payee, AccountName):
            return self.text.lower() in str(transaction.payee).lower()
        return False


@dataclass
class AmountFilter(BaseFilter):
    operator: str
    value: Decimal

    def is_matching(self, transaction: Transaction) -> bool:
        """Checks if any posting amount in the transaction matches the amount filter."""
        for posting in transaction.postings:
            if posting.amount:
                amount_value = posting.amount.quantity
                if self.operator == ">" and amount_value > self.value:
                    return True
                elif self.operator == "<" and amount_value < self.value:
                    return True
                elif self.operator == ">=" and amount_value >= self.value:
                    return True
                elif self.operator == "<=" and amount_value <= self.value:
                    return True
                elif self.operator == "==" and amount_value == self.value:
                    return True
                elif self.operator == "!=" and amount_value != self.value:
                    return True
        return False


@dataclass
class TagFilter(BaseFilter):
    name: str
    value: Optional[str]

    def is_matching(self, transaction: Transaction) -> bool:
        """Checks if any posting in the transaction has a tag matching the tag filter."""
        for posting in transaction.postings:
            for tag in posting.tags:
                if tag.name == self.name:
                    if self.value is None or tag.value == self.value:
                        return True
        return False


class FilterQueryParsers(ParserContext, whitespace=r"\s*"):
    # Basic parsers
    colon = lit(":")
    number = reg(r"-?\d+(\.\d+)?") > (lambda x: Decimal(x))

    # Flexible date parser (YYYY-MM-DD, YYYY-MM, YYYY)
    year_parser = reg(r"\d{4}") > (lambda y: int(y))
    month_parser = reg(r"\d{2}") > (lambda m: int(m))
    day_parser = reg(r"\d{2}") > (lambda d: int(d))

    full_date_parser = year_parser & lit("-") & month_parser & lit("-") & day_parser > (
        lambda parts: date(parts[0], parts[2], parts[4])
    )
    month_date_parser = year_parser & lit("-") & month_parser > (
        lambda parts: (date(parts[0], parts[2], 1), date(parts[0], parts[2], calendar.monthrange(parts[0], parts[2])[1]))
    )
    year_date_parser = year_parser > (
        lambda year: (date(year, 1, 1), date(year, 12, 31))
    )

    flexible_date_parser = full_date_parser | month_date_parser | year_date_parser

    # Filter value parsers
    account_part = reg(r"[A-Za-z_]+")
    account = repsep(account_part, lit(":"), min=1)

    date_range = opt(full_date_parser) & lit("..") & opt(full_date_parser) > (
        lambda parts: (parts[0][0] if parts[0] else None, parts[2][0] if parts[2] else None)
    )
    single_date = full_date_parser > (lambda d: (d,d))

    description_text = reg(r"[^\s]+")
    amount_operator = reg(r"(>=|<=|!=|==|>|<)")
    amount_value_part = amount_operator & number
    tag_name = reg(r"[^\s:]+")

    # Filter parsers
    account_filter = lit("account") >> colon & account > (
        lambda parts: AccountFilter(pattern=parts[1])
    )
    date_filter = lit("date") >> colon >> (date_range | single_date) > (
        lambda parts: DateFilter(
            start_date=parts[0],
            end_date=parts[1],
        )
    )
    description_filter = lit("desc") >> colon >> description_text > (
        lambda parts: DescriptionFilter(text=parts[1])
    )
    amount_filter = lit("amount") >> colon >> amount_value_part > (
        lambda parts: AmountFilter(operator=parts[0], value=parts[1])
    )
    tag_filter = lit("tag") >> colon >> tag_name & opt(colon >> reg(r"[^\s:]*")) > (
        lambda parts: TagFilter(
            # parts[0] is tag name and parts[1] is tag value
            name=parts[0], value=parts[1][0] if parts[1] and parts[1][0] else None
        )
    )

    before_date_filter = lit("before") >> colon >> flexible_date_parser > (
        lambda parsed_date: BeforeDateFilter(
            filter_date=parsed_date if isinstance(parsed_date, date) else parsed_date[0]
        )
    )

    after_date_filter = lit("after") >> colon >> flexible_date_parser > (
        lambda parsed_date: AfterDateFilter(
            filter_date=parsed_date if isinstance(parsed_date, date) else parsed_date[1]
        )
    )

    period_filter = lit("period") >> colon >> flexible_date_parser > (
        lambda parsed_date: PeriodFilter(
            start_date=parsed_date if isinstance(parsed_date, date) else parsed_date[0],
            end_date=parsed_date if isinstance(parsed_date, date) else parsed_date[1]
        )
    )


    # Combined filter parser
    filter_condition = (
        account_filter | date_filter | description_filter | amount_filter | tag_filter |
        before_date_filter | after_date_filter | period_filter
    )

    # Main query parser (list of filter conditions separated by spaces)
    query_parser = rep(filter_condition, min=1)

def parse_query_safe(query: str) -> Result[List[BaseFilter], ParseError]:
    return FilterQueryParsers.query_parser.parse(query).map(list)

def parse_query(query: str) -> Result[List[BaseFilter], ParseError]:
    """Parses a query string into a list of filter conditions using Result for error handling."""
    return parse_query_safe(query)

@dataclass
class Filters:
    """Represents a collection of filter conditions."""
    conditions: List[BaseFilter] = field(default_factory=list)

    def apply_to_entries(self, entries: List[JournalEntry]) -> List[JournalEntry]:
        """Applies the filter conditions to a list of journal entries."""
        filtered_transactions = []
        for entry in entries:
            if entry.transaction and matches_query(entry.transaction, self.conditions):
                filtered_transactions.append(entry)
        return filtered_transactions

def matches_query(transaction: Transaction, parsed_conditions: List[BaseFilter]) -> bool:
    """Checks if a single transaction matches the filter query string."""
    for condition in parsed_conditions:
        if not condition.is_matching(transaction):
            return False
    return True # All conditions matched

def filter_entries(entries: List[JournalEntry], query: str) -> Result[List[JournalEntry], ParseError]:
    """Filters a list of transactions based on a query string, returning a Result."""
    return parse_query(query).map(lambda filters: Filters(conditions=filters).apply_to_entries(entries))

class FilterListParamType(click.ParamType):
    name = "filter_list"

    def convert(self, value, param, ctx):
        if value is None:
            return None
        result = parse_query(value)
        match result:
            case Success(filters):
                return Filters(conditions=filters)
            case Failure(error):
                self.fail(f"Invalid query string: {error}", param, ctx)

FILTER_LIST = FilterListParamType()
