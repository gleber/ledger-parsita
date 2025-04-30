import click
import pprint
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from parsita import lit, reg, rep, rep1, repsep, opt, ParserContext, ParseError

from parsita.util import splat
from datetime import (
    date as date,
    datetime as datetime_class,
)  # Import date, time, and datetime
from decimal import Decimal
from src.classes import (
    Include,
    Transaction,
    Posting,
    Amount,
    AccountName,
    Commodity,
    Cost,
    CostKind,
    Comment,
    Tag,
    Status,
    AccountDirective,
    File,
    JournalEntry,
    Journal,
    SourceLocation,
    PositionAware,
    CommodityDirective,
    Alias,
    MarketPrice,
)

from abc import abstractmethod
from typing import Generic, Optional, TypeVar, Union
from parsita.state import Continue, Input, Output, State
from parsita import Parser, Reader
from returns.result import (
    Result,
    Success,
    Failure,
    safe,
)  # Import Result, Success, Failure, safe
from returns.pipeline import flow
from returns.pointfree import bind

Output_positioned = TypeVar("Output_positioned")


class PositionedParser(
    Generic[Input, Output_positioned], Parser[Input, Output_positioned]
):
    def __init__(
        self, parser: Parser[Input, PositionAware[Output_positioned]]
    ):
        super().__init__()
        self.parser = parser

    def _consume(
        self, state: State, reader: Reader[Input]
    ) -> Optional[Continue[Input, Output_positioned]]:
        start = reader.position
        status = self.parser.consume(state, reader)

        if isinstance(status, Continue):
            end = status.remainder.position
            return Continue(
                status.remainder,
                status.value.set_position(start, end - start),  # type: ignore
            )
        else:
            return status

    def __repr__(self) -> str:
        return self.name_or_nothing() + f"positioned({self.parser.name_or_repr()})"


def positioned(
    parser: Parser[Input, PositionAware[Output_positioned]]
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
    return PositionedParser(parser)


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
    newline: Parser[str, str] = reg(r"\r?\n")
    indent: Parser[str, str] = reg(r"[ \t]+")
    ws: Parser[str, str] = reg(r"[ \t]+")
    ows: Parser[str, str] = reg(r"[ \t]*")
    aws: Parser[str, str] = reg(r"\s*")
    wsn: Parser[str, str] = ws >> newline
    owsn: Parser[str, str] = ows >> newline

    year: Parser[str, int] = reg(r"\d{4}") > int
    month: Parser[str, int] = reg(r"\d{2}") > int
    day: Parser[str, int] = reg(r"\d{2}") > int
    # Transform date components into a date object
    date_p: Parser[str, date] = year << lit("-") & month << lit("-") & day > (
        lambda parts: date(*parts)
    )

    status: Parser[str, Status] = opt(lit("*", "!")) > (
        lambda s: Status(s[0]) if s else Status.Unmarked
    )
    payee: Parser[str, str] = reg(r"[^\n]*")

    # Account names can contain colons, underscores, periods, and hyphens
    # Transform account name string into AccountName object
    account_name: PositionedParser[str, AccountName] = positioned(
        reg(r"[a-zA-Z0-9:_\.\-]+") > (lambda name: AccountName(parts=name.split(":")))
    )  # Filename will be populated later

    # Amount can have commas and an optional decimal
    # Transform amount string into Decimal
    amount_value: Parser[str, Decimal] = reg(r"[-+]?[\d, ]*\d(\.\d*)?") > (
        lambda s: Decimal(s.replace(",", "").replace(" ", ""))
    )

    # Currency can be one or more uppercase letters or anything in double quotes
    # Transform currency string into Commodity object (removing quotes if present)
    currency: PositionedParser[str, Commodity] = positioned(
        reg(r'"[^"]+"|\$|[A-Za-z]+') > (lambda name: Commodity(name=name.strip('"')))
    )  # Filename will be populated later

    # Amount parser supporting: QUANTITY [CURRENCY] or CURRENCY QUANTITY
    amount_qty_first: Parser[str, Amount] = amount_value & opt(ws >> currency) > (
        lambda parts: Amount(
            quantity=parts[0], commodity=parts[1][0] if parts[1] else Commodity(name="")
        )
    )
    amount_cur_first: Parser[str, Amount] = currency & opt(ws) >> amount_value > (
        lambda parts: Amount(quantity=parts[1], commodity=parts[0])
    )  # Allow optional space
    amount_no_cur: Parser[str, Amount] = amount_value > (
        lambda qty: Amount(quantity=qty, commodity=Commodity(name=""))
    )  # Handle amount without currency

    amount: PositionedParser[str, Amount] = positioned(
        (amount_qty_first | amount_cur_first | amount_no_cur)
    )  # Filename will be populated later

    balance: Parser[str, Amount] = lit("=") >> ws >> amount

    # Cost
    cost: PositionedParser[str, Cost] = positioned(
        ((lit("@") | lit("@@")) << ws & amount)
        > (lambda parts: Cost(kind=CostKind(parts[0]), amount=parts[1]))
    )  # Filename will be populated later

    inline_comment: Parser[str, Comment] = lit(";") >> ows >> reg(r"[^\n]*") > Comment

    top_comment: Parser[str, Comment] = (
        ows >> lit(";", "#") >> ows >> reg(r"[^\n]*") > Comment
    )

    # A non-indented posting
    posting: PositionedParser[str, Posting] = positioned(
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
        )
    )  # Filename will be populated later

    # A transaction starts with a date, status, description, and then postings
    transaction_code: Parser[str, str] = lit("(") >> reg(r"[^)]+") << lit(")")

    # A transaction consists of a header followed by zero or more postings. It must contain closing newline
    transaction: PositionedParser[str, Transaction] = positioned(
        (
            (
                date_p << ws
                & opt(status << ws)
                & opt(transaction_code << ws)
                & payee << ows << newline
            )
            << indent
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
                    c for c in parts[1] if isinstance(c, Comment)
                ],  # Combine first item and repeated items, then capture comments
            )
        )
    )  # Filename will be populated later

    filename: Parser[str, str] = reg(
        r"[A-Za-z0-9/\._\-]+"
    )  # Allow digits and hyphens in filenames
    quoted_filename: Parser[str, str] = lit('"') >> filename << lit('"')

    include: PositionedParser[str, Include] = positioned(
        lit("include") >> ws >> (quoted_filename | filename) > Include
    )

    commodity_directive: PositionedParser[str, CommodityDirective] = positioned(
        lit("commodity") >> opt(ws >> amount_value)
        & ws >> currency
        & opt(ws >> inline_comment)
        > (
            lambda parts: CommodityDirective(
                commodity=parts[1],
                example_amount=oneify(parts[0]),
                comment=oneify(parts[2]),
            )
        )
    )

    account_directive: PositionedParser[str, AccountDirective] = positioned(
        lit("account") >> ws >> account_name & opt(ws >> inline_comment)
        > (lambda parts: AccountDirective(name=parts[0], comment=oneify(parts[1])))
    )

    # Alias directive: alias <PATTERN> = <TARGET_ACCOUNT>
    alias_directive: PositionedParser[str, Alias] = positioned(
        lit("alias") >> ws >> reg(r"[^\s=]+") << ws << lit("=") << ws & account_name
        > (lambda parts: Alias(pattern=parts[0], target_account=parts[1]))
    )

    # Price directive: P DATE COMMODITY UNITPRICE
    price_directive: PositionedParser[str, MarketPrice] = positioned(
        lit("P") >> ws >> date_p
        & ws >> currency
        & ws >> amount
        & opt(ws >> inline_comment)
        > (
            lambda parts: MarketPrice(
                date=parts[0],
                commodity=parts[1],
                unit_price=parts[2],
                comment=oneify(parts[3]),
            )
        )
    )

    tli: PositionedParser[str, JournalEntry] = positioned((
        transaction
        | include
        | commodity_directive
        | account_directive
        | alias_directive
        | price_directive
        | top_comment
    ) > JournalEntry.create)

    # The full journal is just a repetition of top-level items (transactions or includes or etc).
    # Each top-level item is separated by one or more whitespace lines.
    journal: PositionedParser[str, Journal] = positioned(
        aws >> repsep(tli, rep(ows << newline)) << aws
        > (
            lambda items: Journal(
                # Filter out string comments before creating JournalEntry objects. Skip comments.
                entries=[item for item in items if isinstance(item, JournalEntry)]
            )
        )
    )


def recursive_include(journal: Journal, journal_fn: str) -> Result[Journal, str]:
    parent_journal_dir = Path(journal_fn).parent

    def include_one(entry: JournalEntry) -> JournalEntry:
        if not entry.include:
            return entry
        include = entry.include
        # Recursively parse included journal and handle the Result
        included_journal_result = parse_hledger_journal(
            Path(parent_journal_dir, include.filename)
        )

        # Use pattern matching to handle the Result
        match included_journal_result:
            case Success(included_journal):
                include = replace(entry.include, journal=included_journal)
                return replace(entry, include=include)
            case Failure(error):
                # Handle the error, perhaps by logging or returning a JournalEntry indicating the error
                # For now, we'll return the original entry, but this should be improved
                print(f"Error including file {include.filename}: {error}")
                return entry
        raise Exception("Inexhaustive match!")

    entries = [include_one(i) for i in journal.entries]
    return Success(replace(journal, entries=entries))


def parse_hledger_journal_content(
    file_content, filename=""
) -> Result[Journal, ParseError]:
    # Use map to handle the parsing result instead of unwrap
    return HledgerParsers.journal.parse(file_content).map(
        lambda journal: journal.set_filename(Path(filename), file_content)
    )


@safe
def read_file_content(filename: Path) -> str:
    return filename.read_text()


def parse_hledger_journal(filename: str | Path) -> Result[Journal, Exception]:
    if not isinstance(filename, Path):
        filename = Path(filename)

    # Use flow and bind to chain the file reading and parsing operations
    return flow(
        filename,
        read_file_content,
        bind(
            lambda file_content: parse_hledger_journal_content(
                file_content, str(filename)
            )
        ),
        bind(lambda journal: recursive_include(journal, str(filename))),
    )
