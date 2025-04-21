from collections.abc import Sequence
from parsita import *

from parsita.util import splat
from datetime import date as date_class
from decimal import Decimal
from .classes import (
    Transaction,
    Posting,
    Amount,
    AccountName,
    Commodity,
    Cost,
    CostKind,  # Import CostKind
    Tag,
    Status,
    MarketPrice,
    AccountDirective,
    File,
    JournalSource,
    Report,
    Journal,
    SourceLocation,
    PositionAware,  # Import PositionAware
)

from abc import abstractmethod
from typing import Generic, Optional, TypeVar
from parsita.state import Continue, Input, Output, State
from parsita import Parser, Reader  # Import necessary classes

Output_positioned = TypeVar("Output_positioned")


class PositionedParser(
    Generic[Input, Output_positioned], Parser[Input, Output_positioned]
):
    def __init__(
        self, parser: Parser[Input, PositionAware[Output_positioned]], filename: str
    ):
        super().__init__()
        self.parser = parser
        self.filename = filename

    def _consume(
        self, state: State, reader: Reader[Input]
    ) -> Optional[Continue[Input, Output_positioned]]:
        start = reader.position
        status = self.parser.consume(state, reader)

        if isinstance(status, Continue):
            end = status.remainder.position
            return Continue(
                status.remainder,
                status.value.set_position(self.filename, start, end - start),
            )
        else:
            return status

    def __repr__(self) -> str:
        return self.name_or_nothing() + f"positioned({self.parser.name_or_repr()})"


def positioned(
    parser: Parser[Input, PositionAware[Output_positioned]], filename: str
) -> PositionedParser[Input, Output_positioned]:
    """Set the position on a PositionAware value.

    This parser matches ``parser`` and, if successful, calls ``set_position``
    on the produced value to produce a new value. The value produces by
    ``parser`` must implement the ``PositionAware`` interface so that it can
    receive the position in the input.

    Args:
        parser: Parser
        filename: The name of the source file being parsed
    """
    return PositionedParser(parser, filename)


def listify(x):
    if isinstance(x, Sequence):
        return x
    return [x]

def oneify(x, default=None):
    if not isinstance(x, Sequence):
        raise Exception("BAD VALUE")
    if x:
        return x[0]
    return default


# Can't use whitespace since ledger language requires indentation
class HledgerParsers(ParserContext, whitespace=None):
    newline = reg(r"\r?\n")
    indent = reg(r"[ \t]+")
    ws = reg(r"[ \t]+")
    ows = reg(r"[ \t]*")
    aws = reg(r"\s*")
    wsn = ws >> newline
    owsn = ows >> newline

    year = reg(r"\d{4}") > int
    month = reg(r"\d{2}") > int
    day = reg(r"\d{2}") > int
    # Transform date components into a date object
    date = year << lit("-") & month << lit("-") & day > (
        lambda parts: date_class(*parts)
    )

    status = opt(lit("*", "!")) > (lambda s: Status(s[0]) if s else Status.Unmarked)
    payee = reg(r"[^\n]*")

    # Account names can contain colons, underscores, periods, and hyphens
    # Transform account name string into AccountName object
    account_name = positioned(
        reg(r"[a-zA-Z0-9:_\.\-]+") > (lambda name: AccountName(parts=name.split(":"))),
        filename="",
    )  # Filename will be populated later

    # Amount can have commas and an optional decimal
    # Transform amount string into Decimal
    amount_value = reg(r"[-+]?[\d,]*\d(\.\d*)?") > (
        lambda s: Decimal(s.replace(",", ""))
    )

    # Currency can be one or more uppercase letters or anything in double quotes
    # Transform currency string into Commodity object (removing quotes if present)
    currency = positioned(
        reg(r'"[^"]+"|[A-Za-z]+') > (lambda name: Commodity(name=name.strip('"'))),
        filename="",
    )  # Filename will be populated later

    # Amount with optional currency
    amount = positioned(
        (amount_value & opt(ws >> currency))
        > (
            lambda parts: Amount(
                quantity=parts[0],
                commodity=parts[1][0] if parts[1] else Commodity(name=""),
            )
        ),
        filename="",
    )  # Handle optional currency, Filename will be populated later

    balance = lit('=') >> ws >> amount

    # Cost
    cost = positioned(
        ((lit("@") | lit("@@")) << ws & amount)
        > (lambda parts: Cost(kind=CostKind(parts[0]), amount=parts[1])),
        filename="",
    )  # Filename will be populated later

    comment_text = lit(";") >> ows >> reg(r"[^\n]*")

    # A non-indented posting
    posting = positioned(
        account_name
        & opt(ws >> amount)
        & opt(ws >> cost)
        & opt(ws >> balance)
        & opt(ws >> comment_text) << ows
        > (
            lambda parts: Posting(
                account=parts[0],
                amount=oneify(parts[1]),
                cost=oneify(parts[2]),
                balance=oneify(parts[3]),
                comment=oneify(parts[4]),
            )
        ),
        filename="",
    )  # Filename will be populated later

    # A transaction starts with a date, status, description, and then postings
    transaction_code = lit("(") >> reg(r"[^)]+") << lit(")")

    transaction_header = (
        date << ws
        & opt(status << ws)
        & opt(transaction_code << ws)
        & payee << ows << newline
    )

    # A transaction consists of a header followed by zero or more postings. It must contain closing newline
    transaction = positioned(
        (
            transaction_header << indent
            & repsep(posting | comment_text, newline & indent, min=1)
        )
        > (
            lambda parts: Transaction(
                date=parts[0][0],
                status=oneify(parts[0][1]),
                code=(
                    parts[0][2][0] if parts[0][2] else None
                ),  # Extract the optional code
                payee=parts[0][3].strip(),
                postings=[
                    p for p in parts[1] if isinstance(p, Posting)
                ],  # Combine first item and repeated items, then filter
                comments=[
                    c for c in parts[1] if isinstance(c, str)
                ],  # Combine first item and repeated items, then capture comments
            )
        ),
        filename="",
    )  # Filename will be populated later

    # Balance assertion: account name, equals sign, amount
    balance_assertion = positioned(
        account_name & (ws >> lit("=") >> ws >> amount)
        > (lambda parts: Balance(account=parts[0], amount=parts[1])),
        filename="",  # Filename will be populated later
    )

    tli = transaction | balance_assertion

    # The full journal is just a repetition of top-level items (transactions or balance assertions).
    # Each top-level item is separated by one or more whitespace lines.
    journal = aws >> repsep(tli, rep(ows << newline)) << aws > (lambda items: items)


def parse_hledger_journal(file_content, filename=""):
    return HledgerParsers.journal.parse(file_content)


if __name__ == "__main__":
    file_path = "examples/all.txt"
    try:
        with open(file_path, "r") as f:
            journal_content = f.read()

        parsed_data = parse_hledger_journal(journal_content, file_path)
        print("Successfully parsed hledger journal:")
        print(f"Parsed {len(parsed_data)} top-level entries.")
        if parsed_data:
            print("\nFirst few parsed entries:")
            for entry in parsed_data[:5]:  # Print first 5 entries
                print(f"- Type: {type(entry).__name__}, Content: {entry}")
                if isinstance(entry, Transaction):
                    print(f"  Source location: {entry.source_location}")
                    if entry.postings:
                        print(
                            f"  First posting source location: {entry.postings[0].source_location}"
                        )
                elif isinstance(entry, Balance):
                    print(f"  Source location: {entry.source_location}")

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except ParseError as e:
        print(f"Parsing failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
