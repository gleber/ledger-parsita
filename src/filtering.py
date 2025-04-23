# This file will contain the filtering logic for transactions.

from typing import List, Optional, Union

from parsita import lit, rep, reg, repsep, ParserContext, opt, ParseError

from src.classes import JournalEntry, Transaction, Posting, Amount, AccountName, BaseFilter
from datetime import date, datetime
from decimal import Decimal
import re
from dataclasses import dataclass
from returns.result import Result, safe, Success, Failure


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
        print(f"Filtering with: name={self.name}, value={self.value}")
        for posting in transaction.postings:
            for tag in posting.tags:
                print(f"  Checking tag: name={tag.name}, value={tag.value}")
                if tag.name == self.name:
                    if self.value is None or tag.value == self.value:
                        print("    Match found!")
                        return True
        print("  No match found.")
        return False


class FilterQueryParsers(ParserContext, whitespace=r"\s*"):
    # Basic parsers
    colon = lit(":")
    number = reg(r"-?\d+(\.\d+)?") > (lambda x: Decimal(x))
    date_str = reg(r"\d{4}-\d{2}-\d{2}") > (lambda parts: datetime.strptime(parts, '%Y-%m-%d').date())

    # Filter value parsers
    account_part = reg(r"[A-Za-z_]+")
    account = repsep(account_part, lit(":"), min=1)

    date_range = opt(date_str) & lit("..") & opt(date_str) > (
        lambda parts: (parts[0][0] if parts[0] else None, parts[2][0] if parts[2] else None)
    )
    single_date = date_str > (lambda d: (d,d))

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

    # Combined filter parser
    filter_condition = (
        account_filter | date_filter | description_filter | amount_filter | tag_filter
    )

    # Main query parser (list of filter conditions separated by spaces)
    query_parser = rep(filter_condition, min=1)

def parse_query_safe(query: str) -> Result[List[BaseFilter], ParseError]:
    return FilterQueryParsers.query_parser.parse(query).map(list)

def parse_query(query: str) -> Result[List[BaseFilter], ParseError]:
    """Parses a query string into a list of filter conditions using Result for error handling."""
    return parse_query_safe(query)


def matches_query(transaction: Transaction, parsed_conditions: List[BaseFilter]) -> bool:
    """Checks if a single transaction matches the filter query string."""
    for condition in parsed_conditions:
        if not condition.is_matching(transaction):
            return False
    return True # All conditions matched

def _apply_filters(entries: List[JournalEntry], filters: List[BaseFilter]) -> List[JournalEntry]:
    """Applies the parsed filter conditions to a list of journal entries."""
    filtered_transactions = []
    for entry in entries:
        if entry.transaction and matches_query(entry.transaction, filters):
            filtered_transactions.append(entry)
    return filtered_transactions

def filter_entries(entries: List[JournalEntry], query: str) -> Result[List[JournalEntry], ParseError]:
    """Filters a list of transactions based on a query string, returning a Result."""
    return parse_query(query).map(lambda filters: _apply_filters(entries, filters))
