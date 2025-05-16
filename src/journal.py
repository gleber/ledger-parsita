from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING, List, Union, Self

from pathlib import Path
from dataclasses import field, replace

from .common_types import (
    SourceLocation,
    PositionAware,
    Comment,
)

from returns.result import Result, Success, Failure, safe
from returns.maybe import Some, Nothing
from returns.pipeline import flow
from returns.pointfree import bind

from parsita import ParseError

from .classes import JournalEntry

from .errors import (
    TransactionBalanceError,
    NoCommoditiesElidedError,
    ImbalanceError,
    UnresolvedElidedAmountError,
    AmbiguousElidedAmountError,
    VerificationError,
)


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

    def balance(self) -> Result["Journal", TransactionBalanceError]:
        """
        Attempts to balance all transactions within the journal.
        Returns a new Journal with balanced transactions if all transactions balance successfully.
        If any transaction fails to balance, the entire balancing operation fails.
        """
        balanced_entries: List[JournalEntry] = []
        for entry in self.entries:
            if entry.transaction:
                balance_result = entry.transaction.balance()
                if isinstance(balance_result, Success):
                    balanced_transaction = balance_result.unwrap()
                    balanced_entries.append(
                        replace(entry, transaction=balanced_transaction)
                    )
                else:
                    # Fail the entire balancing operation if any transaction fails
                    return Failure(balance_result.failure())
            else:
                # Non-transaction entries are retained unchanged
                balanced_entries.append(entry)
        return Success(
            Journal(entries=balanced_entries, source_location=self.source_location)
        )

    @staticmethod
    def parse_from_file(
        filename: str,
        *,
        query: Optional["Filters"] = None,
        flat: bool = False,
        strip: bool = False,
    ) -> Result["Journal", Union[ParseError, str, ValueError]]:
        """
        Parses an hledger journal file and returns a Journal object.

        Optionally filters, flattens, and strips location information.
        """
        if not isinstance(filename, Path):
            filename = Path(filename)

        # Define helper functions for the pipeline
        def _apply_flatten(journal: Journal) -> Result[Journal, ValueError]:
            if flat:
                return Success(journal.flatten())
            return Success(journal)

        def _apply_strip(journal: Journal) -> Result[Journal, ValueError]:
            if strip:
                return Success(journal.strip_loc())
            return Success(journal)

        def _apply_filters_to_journal(journal: Journal) -> Result[Journal, ValueError]:
            if query:
                filtered_entries = query.apply_to_entries(journal.entries)
                return Success(replace(journal, entries=filtered_entries))
            return Success(journal)

        # Use flow and bind to chain the file reading, parsing, and processing operations
        return flow(
            filename,
            Journal.read_file_content,  # Use the static method
            bind(
                lambda file_content: Journal.parse_from_content(  # Use the static method
                    file_content, filename
                )
            ),
            bind(
                lambda journal: journal.recursive_include(filename)
            ),  # Use the instance method
            bind(_apply_flatten),  # Apply flattening
            bind(_apply_filters_to_journal),  # Apply filtering
            bind(_apply_strip),  # Apply stripping
        )

    @staticmethod
    @safe
    def read_file_content(filename: Path) -> str:
        return filename.read_text()

    @staticmethod
    def parse_from_content(
        content: str, filename: Path
    ) -> Result["Journal", Union[ParseError, str]]:
        """Parses hledger journal content string and returns a Journal object."""
        from src.hledger_parser import (
            HledgerParsers,
        )  # Import here to avoid circular dependency

        return HledgerParsers.journal.parse(content).map(
            lambda j: j.set_filename(filename, content)
        )

    def recursive_include(self, journal_fn: Path) -> Result["Journal", str]:
        parent_journal_dir = Path(journal_fn).parent

        def include_one(entry: JournalEntry) -> JournalEntry:
            if not entry.include:
                return entry
            include = entry.include
            # Recursively parse included journal and handle the Result
            included_journal_result = Journal.parse_from_file(  # Use the static method
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

        entries = [include_one(i) for i in self.entries]  # Use self.entries
        return Success(replace(self, entries=entries))  # Use self

    def verify(self) -> Result[None, List[VerificationError]]:
        """
        Performs comprehensive verification of the journal.

        Checks include:
        1. Stock/option acquisitions use dated subaccounts.
        2. Individual transaction integrity and balance.
        3. Successful balance sheet calculation.

        Returns Success(None) if all checks pass, otherwise Failure containing a list of VerificationError objects.
        """
        from src.balance import (
            BalanceSheet,
        )  # Import locally to avoid circular dependency

        verification_errors: List[VerificationError] = []

        # Check 1: Stock/option acquisitions use dated subaccounts
        for entry in self.entries:
            if entry.transaction:
                tx = entry.transaction
                maybe_acq_posting = tx.get_asset_acquisition_posting()
                if isinstance(maybe_acq_posting, Some):
                    acq_posting = maybe_acq_posting.unwrap()
                    # Check commodity type again just to be sure (though get_asset_acquisition_posting should handle this)
                    if acq_posting.amount and (
                        acq_posting.amount.commodity.isStock()
                        or acq_posting.amount.commodity.isOption()
                    ):
                        if not acq_posting.account.isDatedSubaccount():
                            verification_errors.append(
                                AcquisitionMissingDatedSubaccountError(acq_posting)
                            )

        # Check 2: Individual transaction verification
        for entry in self.entries:
            if entry.transaction:
                tx = entry.transaction
                tx_verify_result = tx.verify()  # This now checks integrity and balance
                if isinstance(tx_verify_result, Failure):
                    # Wrap the TransactionValidationError in a VerificationError
                    # Need to handle potential list of errors if verify changes later
                    err = tx_verify_result.failure()
                    # Attempt to get source location from the transaction itself
                    loc = tx.source_location
                    # If the error itself has a location (less likely for tx errors), prefer that? No, stick to tx location.
                    verification_errors.append(VerificationError(str(err), loc))

        # Check 3: Balance Sheet Calculation Errors
        balance_sheet_build_result = BalanceSheet.from_journal(self)
        if isinstance(balance_sheet_build_result, Failure):
            # from_journal now returns Failure(List[BalanceSheetCalculationError])
            # These errors already have source locations if available from the transaction
            # that caused the error during its apply_transaction call.
            bs_errors = balance_sheet_build_result.failure()
            verification_errors.extend(
                bs_errors
            )  # bs_errors is already List[BalanceSheetCalculationError]

        if verification_errors:
            return Failure(verification_errors)
        else:
            return Success(None)
