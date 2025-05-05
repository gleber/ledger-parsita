import functools # Import functools for reduce
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Union
import datetime
from datetime import date # Import date specifically for type hints if needed

from src.classes import AccountName, Amount, Commodity, Posting, Transaction, CostKind, CommodityKind, CapitalGainResult # Import CapitalGainResult

@dataclass
class Lot:
    """Represents a specific acquisition lot of an asset."""
    acquisition_date: str  # Using string for now, could be date object later
    quantity: Amount
    cost_basis_per_unit: Amount # Cost per unit in the transaction currency
    original_posting: Posting # Reference to the posting that created this lot
    remaining_quantity: Decimal = field(init=False) # Quantity remaining to be matched

    def __post_init__(self):
        # Initialize remaining_quantity to the initial quantity of the lot
        self.remaining_quantity = self.quantity.quantity

@dataclass
class Balance:
    """Base class for account balances."""
    commodity: Commodity
    total_amount: Amount = field(default_factory=lambda: Amount(Decimal(0), Commodity(""))) # Initialize with zero amount

@dataclass
class CashBalance(Balance):
    """Represents the balance of a cash or cryptocurrency commodity within an account."""
    # Inherits commodity and total_amount from Balance

    def add_posting(self, posting: Posting):
        """Adds a posting amount to the total_amount for this CashBalance."""
        if posting.amount is not None:
            if self.total_amount.commodity.name == "": # Handle initial zero amount
                 self.total_amount = Amount(self.total_amount.quantity + posting.amount.quantity, posting.amount.commodity)
            elif self.total_amount.commodity != posting.amount.commodity:
                raise ValueError("Cannot add amounts of different commodities")
            else:
                # Create a new Amount object with the updated quantity
                self.total_amount = Amount(self.total_amount.quantity + posting.amount.quantity, self.total_amount.commodity)


@dataclass
class AssetBalance(Balance):
    """Represents the balance of a stock or option commodity within an account, including lots."""
    # Inherits commodity and total_amount from Balance
    cost_basis_per_unit: Amount = field(default_factory=lambda: Amount(Decimal(0), Commodity(""))) # Initialize with zero amount
    lots: List[Lot] = field(default_factory=list)

    def add_lot(self, lot: Lot):
        """Adds a lot to this AssetBalance and incrementally recalculates total_amount and cost_basis_per_unit."""
        if lot.quantity.commodity != self.commodity:
            raise ValueError("Lot commodity must match Balance commodity")

        # Calculate the new total quantity and total cost
        current_total_quantity = self.total_amount.quantity if self.total_amount.commodity == self.commodity else Decimal(0)
        current_total_cost = current_total_quantity * self.cost_basis_per_unit.quantity if self.cost_basis_per_unit and self.cost_basis_per_unit.commodity.name != "" else Decimal(0)

        new_total_quantity = current_total_quantity + lot.quantity.quantity
        new_total_cost = current_total_cost + (lot.quantity.quantity * lot.cost_basis_per_unit.quantity if lot.cost_basis_per_unit else Decimal(0))

        # Update total_amount
        self.total_amount = Amount(new_total_quantity, self.commodity)

        # Update cost_basis_per_unit (weighted average)
        if new_total_quantity != 0:
            cost_commodity = lot.cost_basis_per_unit.commodity if lot.cost_basis_per_unit else (self.cost_basis_per_unit.commodity if self.cost_basis_per_unit.commodity.name != "" else Commodity(""))
            self.cost_basis_per_unit = Amount(new_total_cost / new_total_quantity, cost_commodity)
        else:
            self.cost_basis_per_unit = Amount(Decimal(0), self.cost_basis_per_unit.commodity if self.cost_basis_per_unit.commodity.name != "" else Commodity("")) # Handle zero quantity

        self.lots.append(lot)


@dataclass
class Account:
    """Represents an account with balances for different commodities."""
    name: AccountName
    balances: Dict[Commodity, Union[CashBalance, AssetBalance]] = field(default_factory=dict)

    def get_balance(self, commodity: Commodity) -> Union[CashBalance, AssetBalance]:
        """Gets or creates a Balance subclass object for a given commodity based on its type."""
        if commodity not in self.balances:
            # Determine the type of Balance to create based on commodity type
            if commodity.isCash():
                self.balances[commodity] = CashBalance(commodity=commodity)
            elif commodity.isStock() or commodity.isOption() or commodity.kind == CommodityKind.CRYPTO: # Include CRYPTO for AssetBalance
                 # Initialize AssetBalance with zero total_amount and cost_basis_per_unit
                self.balances[commodity] = AssetBalance(commodity=commodity, total_amount=Amount(Decimal(0), commodity), cost_basis_per_unit=Amount(Decimal(0), Commodity("")))
            else:
                # Default to CashBalance for unknown types or raise an error
                self.balances[commodity] = CashBalance(commodity=commodity) # Or raise ValueError(f"Unsupported commodity type: {commodity.name}")

        return self.balances[commodity]

    def add_lot(self, commodity: Commodity, lot: Lot):
        """Adds a lot to the balance of a specific commodity (must be an AssetBalance)."""
        balance = self.get_balance(commodity)
        if isinstance(balance, AssetBalance):
            balance.add_lot(lot)
        else:
            raise TypeError(f"Cannot add lot to non-asset balance for commodity: {commodity.name}")


@dataclass
class BalanceSheet:
    """Represents the balance sheet with accounts and their balances."""
    accounts: Dict[AccountName, Account] = field(default_factory=dict)
    capital_gains_realized: List[CapitalGainResult] = field(default_factory=list) # Store realized capital gains

    def get_account(self, account_name: AccountName) -> Account:
        """Gets or creates an Account object for a given account name."""
        if account_name not in self.accounts:
            self.accounts[account_name] = Account(name=account_name)
        return self.accounts[account_name]

    def update_balance(self, account_name: AccountName, amount: Amount):
        """Updates the balance of a specific commodity in an account (only for CashBalance)."""
        account = self.get_account(account_name)
        balance = account.get_balance(amount.commodity)
        if isinstance(balance, CashBalance):
             # Explicitly add amount quantity to total_amount quantity for CashBalance
            if balance.total_amount.commodity.name == "": # Handle initial zero amount
                 balance.total_amount = Amount(balance.total_amount.quantity + amount.quantity, amount.commodity)
            elif balance.total_amount.commodity != amount.commodity:
                raise ValueError("Cannot add amounts of different commodities")
            else:
                balance.total_amount.quantity += amount.quantity
        # For AssetBalance, total_amount is updated when lots are added, not by postings here


    def add_lot_to_account(self, account_name: AccountName, commodity: Commodity, lot: Lot):
        """Adds a lot to a specific commodity balance within an account (must be an AssetBalance)."""
        account = self.get_account(account_name)
        account.add_lot(commodity, lot)

    def apply_transaction(self, transaction: Transaction) -> 'BalanceSheet':
        """
        Applies a single transaction to the balance sheet, updating balances, lots, and calculating capital gains.
        This method modifies the BalanceSheet instance it's called on and returns it.

        Args:
            transaction: The Transaction object to apply.

        Returns:
            The modified BalanceSheet instance.
        """
        # Process postings to update cash balances
        for posting in transaction.postings:
            account_name = posting.account
            amount = posting.amount

            # Ensure the account exists in the balance sheet
            account = self.get_account(account_name)

            if amount is not None:
                # Ensure the balance for the commodity exists and update if it's a CashBalance
                balance = account.get_balance(amount.commodity)
                if isinstance(balance, CashBalance):
                    balance.add_posting(posting) # Call the add_posting method
                # For AssetBalance, total_amount is updated when lots are added, not by postings here

        # Check for asset acquisitions and track lots
        acquisition_posting = transaction.get_asset_acquisition_posting()
        if acquisition_posting:
            # Get the cost for this posting (explicit or inferred)
            cost = transaction.get_posting_cost(acquisition_posting)

            if cost and acquisition_posting.amount is not None:
                cost_basis_per_unit = None
                if cost.kind == CostKind.TotalCost:
                    # Calculate per-unit cost from total cost
                    if acquisition_posting.amount.quantity != 0:
                        cost_basis_per_unit_value = abs(cost.amount.quantity / acquisition_posting.amount.quantity)
                        cost_basis_per_unit = Amount(cost_basis_per_unit_value, cost.amount.commodity)
                elif cost.kind == CostKind.UnitCost:
                    # Unit cost is provided directly
                    cost_basis_per_unit = cost.amount

                if cost_basis_per_unit:
                    lot = Lot(
                        acquisition_date=str(transaction.date), # Use transaction date as acquisition date string
                        quantity=acquisition_posting.amount, # Use quantity from the acquisition posting
                        cost_basis_per_unit=cost_basis_per_unit,
                        original_posting=acquisition_posting
                        # remaining_quantity is initialized in __post_init__
                    )

                    account_name = acquisition_posting.account # Get account name from acquisition posting
                    self.add_lot_to_account(account_name, acquisition_posting.amount.commodity, lot)

        # --- Capital Gains Calculation (Integrated) ---
        # Check for closing postings (sales) after processing all postings in the transaction
        for posting in transaction.postings:
            if posting.isClosing():
                closing_account = posting.account
                closing_commodity = posting.amount.commodity if posting.amount else None
                closing_quantity = abs(posting.amount.quantity) if posting.amount else Decimal(0)

                if closing_commodity and closing_quantity > 0:
                    # Find proceeds for this closing posting within the same transaction
                    total_proceeds = Amount(Decimal(0), Commodity("")) # Initialize with zero amount and empty commodity
                    proceeds_found = False
                    for other_posting in transaction.postings:
                        if other_posting != posting and other_posting.amount and other_posting.amount.quantity > 0 and other_posting.amount.commodity.isCash():
                            if total_proceeds.commodity.name == "": # Set commodity on first cash posting
                                total_proceeds = Amount(total_proceeds.quantity + other_posting.amount.quantity, other_posting.amount.commodity)
                            elif total_proceeds.commodity == other_posting.amount.commodity:
                                total_proceeds.quantity += other_posting.amount.quantity
                            else:
                                # Handle multiple cash commodities in one transaction if necessary, or raise error
                                print(f"Warning: Multiple cash commodities in transaction {transaction.date} - {transaction.payee}. Only summing {total_proceeds.commodity.name}.")
                                total_proceeds.quantity += other_posting.amount.quantity # Still sum, but warn
                            proceeds_found = True

                    if not proceeds_found:
                        print(f"Warning: No cash proceeds found for closing posting in transaction {transaction.date} - {transaction.payee} for {closing_quantity} {closing_commodity.name} from {closing_account.name}.")
                        # Depending on requirements, might skip this posting or handle differently

                    quantity_to_match = closing_quantity

                    # Collect all relevant AssetBalance objects for the closing commodity under the closing account and its children
                    # Use the current state of the balance_sheet being built
                    relevant_asset_balances: List[AssetBalance] = []
                    for account_name, account_data in self.accounts.items():
                        # Check if the account is the closing account or a child account
                        if account_name.name.startswith(closing_account.name):
                            for commodity_name, balance in account_data.balances.items():
                                if isinstance(balance, AssetBalance) and balance.commodity == closing_commodity:
                                    relevant_asset_balances.append(balance)

                    if relevant_asset_balances:
                        # Combine lots from all relevant balances and sort by acquisition date
                        all_relevant_lots: List[Lot] = []
                        for balance in relevant_asset_balances:
                            # Only consider lots from the *current* state of the balance sheet
                            all_relevant_lots.extend(balance.lots)

                        # Sort lots by acquisition date (FIFO)
                        sorted_lots = sorted(all_relevant_lots, key=lambda lot: datetime.datetime.strptime(lot.acquisition_date, '%Y-%m-%d').date())

                        # Perform FIFO matching
                        for current_lot in sorted_lots:
                            if quantity_to_match <= 0:
                                break # Stop if the closing quantity is fully matched

                            if current_lot.remaining_quantity > 0:
                                match_quantity_decimal = min(quantity_to_match, current_lot.remaining_quantity)
                                match_quantity_amount = Amount(match_quantity_decimal, closing_commodity)

                                # Calculate cost basis for the matched quantity
                                cost_basis_decimal = match_quantity_decimal * current_lot.cost_basis_per_unit.quantity
                                cost_basis_amount = Amount(cost_basis_decimal, current_lot.cost_basis_per_unit.commodity)

                                # Calculate proceeds for the matched quantity (pro-rata)
                                proceeds_decimal = (match_quantity_decimal / closing_quantity) * total_proceeds.quantity if closing_quantity != 0 else Decimal(0)
                                proceeds_amount = Amount(proceeds_decimal, total_proceeds.commodity)

                                # Calculate gain/loss
                                # Ensure both amounts are in the same currency for calculation
                                if cost_basis_amount.commodity != proceeds_amount.commodity:
                                    print(f"Warning: Cost basis commodity ({cost_basis_amount.commodity.name}) and proceeds commodity ({proceeds_amount.commodity.name}) differ for match in transaction {transaction.date} - {transaction.payee}. Cannot calculate gain/loss directly.")
                                    gain_loss_amount = Amount(Decimal(0), Commodity("")) # Cannot calculate if currencies differ
                                else:
                                    gain_loss_decimal = proceeds_decimal - cost_basis_decimal
                                    gain_loss_amount = Amount(gain_loss_decimal, proceeds_amount.commodity)

                                # Determine acquisition date from the lot's acquisition_date string
                                try:
                                    # Use datetime.date directly if available, otherwise parse string
                                    if isinstance(current_lot.acquisition_date, date):
                                        acquisition_date_obj = current_lot.acquisition_date
                                    else:
                                        acquisition_date_obj = datetime.datetime.strptime(current_lot.acquisition_date, '%Y-%m-%d').date()
                                except ValueError:
                                    print(f"Warning: Could not parse acquisition date '{current_lot.acquisition_date}' for lot. Using date.min.")
                                    acquisition_date_obj = date.min # Use date.min as fallback

                                # Create and append CapitalGainResult to the BalanceSheet's list
                                self.capital_gains_realized.append(CapitalGainResult(
                                    closing_posting=posting,
                                    opening_lot_original_posting=current_lot.original_posting,
                                    matched_quantity=match_quantity_amount,
                                    cost_basis=cost_basis_amount,
                                    proceeds=proceeds_amount,
                                    gain_loss=gain_loss_amount,
                                    closing_date=transaction.date, # Get closing date from the current transaction
                                    acquisition_date=acquisition_date_obj # Use determined acquisition date object
                                ))

                                # Update remaining quantity in the lot (within the balance_sheet being built)
                                current_lot.remaining_quantity -= match_quantity_decimal
                                quantity_to_match -= match_quantity_decimal

                                # --- Apply Gain/Loss to Running Balances ---
                                # Determine the appropriate gain/loss account
                                if gain_loss_amount.quantity > 0:
                                    gain_loss_account_name = AccountName(["income", "capital_gains"]) # Example account
                                    # Credit the income account
                                    self.update_balance(gain_loss_account_name, gain_loss_amount)
                                    # Debit the asset account (this is already handled by the posting itself)
                                elif gain_loss_amount.quantity < 0:
                                    gain_loss_account_name = AccountName(["expenses", "capital_losses"]) # Example account
                                    # Debit the expense account (use absolute value for debit)
                                    self.update_balance(gain_loss_account_name, gain_loss_amount)
                                    # Credit the asset account (this is already handled by the posting itself)

                        if quantity_to_match > 0:
                            print(f"Warning: Not enough open lots found for {closing_quantity} {closing_commodity.name} in {closing_account.name} to match closing posting in transaction {transaction.date} - {transaction.payee}. Remaining quantity to match: {quantity_to_match}")

                    else:
                        print(f"Warning: Could not find any relevant AssetBalance for {closing_account.name}:{closing_commodity.name} to perform FIFO matching.")

        return self # Return self to allow chaining/use with reduce


    @staticmethod
    def from_transactions(transactions: List[Transaction]) -> 'BalanceSheet':
        """
        Builds a BalanceSheet by applying a list of transactions sequentially using functools.reduce.

        Args:
            transactions: A list of Transaction objects.

        Returns:
            A BalanceSheet reflecting the state after applying all transactions.
        """
        # Sort transactions by date to ensure correct FIFO processing
        sorted_transactions = sorted(transactions, key=lambda t: t.date)

        # Define the reducer function that applies a transaction to the balance sheet
        def reducer(balance_sheet: BalanceSheet, transaction: Transaction) -> BalanceSheet:
            return balance_sheet.apply_transaction(transaction)

        # Use functools.reduce to apply the reducer function to the sorted transactions
        # Initialize with an empty BalanceSheet
        final_balance_sheet = functools.reduce(reducer, sorted_transactions, BalanceSheet())

        return final_balance_sheet
