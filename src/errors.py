from typing import Optional, List
from pathlib import Path
from decimal import Decimal

# Error types for Transaction validation and balancing
class TransactionValidationError(Exception):
    """Base class for transaction validation and balancing errors."""
    pass

class TransactionIntegrityError(TransactionValidationError):
    """For issues with the basic structure or completeness of the Transaction object itself."""
    pass

class MissingDateError(TransactionIntegrityError):
    def __init__(self, message: str = "Transaction date is missing or invalid."):
        super().__init__(message)

class MissingDescriptionError(TransactionIntegrityError):
    def __init__(self, message: str = "Transaction payee/description is missing or empty."):
        super().__init__(message)

class InsufficientPostingsError(TransactionIntegrityError):
    def __init__(self, message: str = "Transaction must have at least two postings."):
        super().__init__(message)

class InvalidPostingError(TransactionIntegrityError):
    def __init__(self, message: str):
        super().__init__(message)

class TransactionBalanceError(TransactionValidationError):
    """For issues related to the sum of posting amounts."""
    pass

class ImbalanceError(TransactionBalanceError):
    def __init__(self, commodity: "Commodity", balance_sum: Decimal):
        self.commodity = commodity
        self.balance_sum = balance_sum
        super().__init__(f"Transaction does not balance for commodity {commodity}. Sum is {balance_sum}")

class AmbiguousElidedAmountError(TransactionBalanceError):
    def __init__(self, commodity: "Commodity"):
        self.commodity = commodity
        super().__init__(f"More than one elided amount for commodity {commodity}, cannot infer balance")

class UnresolvedElidedAmountError(TransactionBalanceError):
    def __init__(self, commodity: "Commodity"):
        self.commodity = commodity
        super().__init__(f"Cannot resolve elided amount for commodity {commodity}.")

class NoCommoditiesElidedError(TransactionBalanceError):
    def __init__(self, message: str = "Cannot resolve elided amount as no commodities are present in the transaction"):
        super().__init__(message)

class MultipleCommoditiesRemainingError(TransactionBalanceError):
    def __init__(self, commodities: List["Commodity"], message: Optional[str] = None):
        self.commodities = commodities
        if message is None:
            if commodities:
                commodity_str = ", ".join(str(c) for c in commodities)
                message = f"Cannot resolve remaining elided amounts due to multiple commodities present: {commodity_str}."
            else:
                message = "Cannot resolve remaining elided amounts due to multiple commodities present in the transaction."
        super().__init__(message)

# Verification Error Types
class VerificationError(Exception):
    """Base class for journal-level verification errors."""
    def __init__(self, message: str, source_location: Optional["SourceLocation"] = None):
        self.source_location = source_location
        super().__init__(message)

    def __str__(self):
        loc_str = f" at {self.source_location.filename}:{self.source_location.line}:{self.source_location.column}" if self.source_location and self.source_location.line is not None else ""
        # Ensure message is stringified properly before concatenation
        base_message = super().__str__()
        return f"{base_message}{loc_str}"


class AcquisitionMissingDatedSubaccountError(VerificationError):
    """Error for stock/option acquisition posting not using a dated subaccount."""
    def __init__(self, posting: "Posting"):
        message = f"Stock/option acquisition posting for '{posting.amount.commodity}' to account '{posting.account}' does not use a dated subaccount (YYYYMMDD)"
        super().__init__(message, posting.source_location)

class BalanceSheetCalculationError(VerificationError):
    """Error during balance sheet calculation."""
    # This will likely wrap other errors like ValueError or Failure contents
    def __init__(self, original_error: Exception, source_location: Optional["SourceLocation"] = None):
        self.original_error = original_error
        message = f"Balance sheet calculation failed: {original_error}"
        super().__init__(message, source_location)
