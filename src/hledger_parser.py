import click
import pprint
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from parsita import *

from parsita.util import splat
from datetime import date as date_class, datetime as datetime_class  # Import datetime
from decimal import Decimal
from .classes import (
    Include,
    Transaction,
    Posting,
    Amount,
    AccountName,
    Commodity,
    Cost,
    CostKind,  # Import CostKind
    Comment,
    Tag,
    Status,
    MarketPrice,
    AccountDirective,
    File,
    JournalEntry,
    Report,
    Journal,
    SourceLocation,
    PositionAware,  # Import PositionAware
    CommodityDirective,  # Import CommodityDirective
    Alias,  # Import Alias
    MarketPrice,  # Import MarketPrice
)

from abc import abstractmethod
from typing import Generic, Optional, TypeVar
from parsita.state import Continue, Input, Output, State
from parsita import Parser, Reader

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

    # Time parser (HH:MM:SS or HH:MM)
    hour = reg(r"\d{2}") > int
    minute = reg(r"\d{2}") > int
    second = reg(r"\d{2}") > int
    time = hour << lit(":") & minute & opt(lit(":") >> second) > (
        lambda parts: datetime_class.strptime(
            f"{parts[0]:02}:{parts[1]:02}:{parts[2][0] if parts[2] else 0:02}",
            "%H:%M:%S",
        ).time()
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
    amount_value = reg(r"[-+]?[\d, ]*\d(\.\d*)?") > (
        lambda s: Decimal(s.replace(",", "").replace(" ", ""))
    )

    # Currency can be one or more uppercase letters or anything in double quotes
    # Transform currency string into Commodity object (removing quotes if present)
    currency = positioned(
        reg(r'"[^"]+"|\$|[A-Za-z]+') > (lambda name: Commodity(name=name.strip('"'))),
        filename="",
    )  # Filename will be populated later

    # Amount parser supporting: QUANTITY [CURRENCY] or CURRENCY QUANTITY
    amount_qty_first = amount_value & opt(ws >> currency) > (
        lambda parts: Amount(
            quantity=parts[0], commodity=parts[1][0] if parts[1] else Commodity(name="")
        )
    )
    amount_cur_first = currency & opt(ws) >> amount_value > (
        lambda parts: Amount(quantity=parts[1], commodity=parts[0])
    )  # Allow optional space
    amount_no_cur = amount_value > (
        lambda qty: Amount(quantity=qty, commodity=Commodity(name=""))
    )  # Handle amount without currency

    amount = positioned(
        (amount_qty_first | amount_cur_first | amount_no_cur),
        filename="",
    )  # Filename will be populated later

    balance = lit("=") >> ws >> amount

    # Cost
    cost = positioned(
        ((lit("@") | lit("@@")) << ws & amount)
        > (lambda parts: Cost(kind=CostKind(parts[0]), amount=parts[1])),
        filename="",
    )  # Filename will be populated later

    inline_comment = lit(";") >> ows >> reg(r"[^\n]*") > Comment

    top_comment = ows >> lit(";", "#") >> ows >> reg(r"[^\n]*") > Comment

    # A non-indented posting
    posting = positioned(
        account_name
        & opt(ws >> amount)
        & opt(ws >> cost)
        & opt(ws >> balance)
        & opt(ws >> inline_comment) << ows
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
            & repsep(posting | inline_comment, newline & indent, min=1)
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

    filename = reg(r"[A-Za-z0-9/\._\-]+")  # Allow digits and hyphens in filenames

    include = positioned(
        lit("include") >> ws >> filename > (lambda fn: Include(filename=fn)),
        filename="",
    )

    commodity_directive = positioned(
        lit("commodity") >> opt(ws >> amount_value)
        & ws >> currency
        & opt(ws >> inline_comment)
        > (
            lambda parts: CommodityDirective(
                commodity=parts[1],
                example_amount=oneify(parts[0]),
                comment=oneify(parts[2]),
            )
        ),
        filename="",
    )

    account_directive = positioned(
        lit("account") >> ws >> account_name & opt(ws >> inline_comment)
        > (lambda parts: AccountDirective(name=parts[0], comment=oneify(parts[1]))),
        filename="",
    )

    # Alias directive: alias <PATTERN> = <TARGET_ACCOUNT>
    alias_directive = positioned(
        lit("alias") >> ws >> reg(r"[^\s=]+") << ws << lit("=") << ws & account_name
        > (lambda parts: Alias(pattern=parts[0], target_account=parts[1])),
        filename="",
    )

    # Price directive: P DATE [TIME] COMMODITY UNITPRICE
    price_directive = positioned(
        lit("P") >> ws >> date
        & opt(ws >> time)
        & ws >> currency
        & ws >> amount
        & opt(ws >> inline_comment)
        > (
            lambda parts: MarketPrice(
                date=parts[0],
                time=oneify(parts[1]),
                commodity=parts[2],
                unit_price=parts[3],
                comment=oneify(parts[4]),
            )
        ),  # Corrected indices
        filename="",
    )

    tli = (
        transaction
        | include
        | commodity_directive
        | account_directive
        | alias_directive
        | price_directive
        | top_comment
    )  # Add price_directive

    # The full journal is just a repetition of top-level items (transactions or includes or etc).
    # Each top-level item is separated by one or more whitespace lines.
    journal = aws >> repsep(tli, rep(ows << newline)) << aws > (
        lambda items: Journal(
            # Filter out string comments before creating JournalEntry objects. Skip comments.
            entries=[
                JournalEntry.create(i) for i in items if not isinstance(i, Comment)
            ]
        )
    )


def recursive_include(journal: Journal, journal_fn: str):
    parent_journal_dir = Path(journal_fn).parent

    def include_one(entry: JournalEntry):
        if not entry.include:
            return entry
        include = entry.include
        include = replace(
            entry.include,
            journal=parse_hledger_journal(Path(parent_journal_dir, include.filename)),
        )
        return replace(entry, include=include)

    entries = [include_one(i) for i in journal.entries]
    return replace(journal, entries=entries)


def parse_hledger_journal_content(file_content, filename=""):
    journal = HledgerParsers.journal.parse(file_content).unwrap()
    journal = journal.set_filename(filename)
    return recursive_include(journal, filename)


def parse_hledger_journal(filename: str):
    path = Path(filename)
    file_content = path.read_text()
    full_filename = path.absolute()
    return parse_hledger_journal_content(file_content, full_filename)


# Define the main click group
@click.group()
def cli():
    """A command-line tool for parsing hledger journal files."""
    pass

# Define the pprint command
@cli.command("pprint") # Explicitly name the command
@click.argument('filename', type=click.Path(exists=True, dir_okay=False, path_type=Path)) # Use Path object
def pprint_cmd(filename: Path):
    """Parses the journal file and pretty-prints the result."""
    try:
        # Pass the absolute path string to the parser function
        parsed_data = parse_hledger_journal(str(filename.absolute()))
        print(f"Successfully parsed hledger journal: {filename}")
        # Use pprint.pformat for better control if needed, or just pprint
        pprint.pprint(parsed_data, indent=2) # Add indentation for readability
    except ParseError as e:
        # Improve error reporting
        print(f"Parsing failed in '{filename}': {e}")
        # Consider showing the problematic line/context if possible from Parsita error
    except Exception as e:
        print(f"An unexpected error occurred while processing '{filename}': {e}")
        # Consider adding traceback for debugging unexpected errors
        # import traceback
        # traceback.print_exc()

if __name__ == "__main__":
    cli()
