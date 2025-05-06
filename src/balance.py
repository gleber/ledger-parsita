import functools
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Union, Optional, Generator # Import Generator
import datetime
from datetime import date
from collections import defaultdict # Import defaultdict

from src.classes import AccountName, Amount, Commodity, Posting, Transaction, CostKind, CommodityKind, CapitalGainResult, Comment, Journal # Import Journal

@dataclass
class Lot:
    """Represents a specific acquisition lot of an asset."""
    acquisition_date: str
    quantity: Amount
    cost_basis_per_unit: Amount
    original_posting: Posting
    remaining_quantity: Decimal = field(init=False)

    def __post_init__(self):
        self.remaining_quantity = self.quantity.quantity

@dataclass
class Balance:
    """Base class for account balances."""
    commodity: Commodity
    total_amount: Amount = field(default_factory=lambda: Amount(Decimal(0), Commodity("")))

@dataclass
class CashBalance(Balance):
    """Represents the balance of a cash or cryptocurrency commodity within an account."""

    def add_posting(self, posting: Posting):
        """Adds a posting amount to the total_amount for this CashBalance."""
        if posting.amount is not None:
            if self.total_amount.commodity.name == "":
                 self.total_amount = Amount(self.total_amount.quantity + posting.amount.quantity, posting.amount.commodity)
            elif self.total_amount.commodity != posting.amount.commodity:
                raise ValueError("Cannot add amounts of different commodities")
            else:
                self.total_amount = Amount(self.total_amount.quantity + posting.amount.quantity, self.total_amount.commodity)

@dataclass
class AssetBalance(Balance):
    """Represents the balance of a stock or option commodity within an account, including lots."""
    cost_basis_per_unit: Amount = field(default_factory=lambda: Amount(Decimal(0), Commodity("")))
    lots: List[Lot] = field(default_factory=list)

    def add_lot(self, lot: Lot):
        """Adds a lot to this AssetBalance and incrementally recalculates total_amount and cost_basis_per_unit."""
        if lot.quantity.commodity != self.commodity:
            raise ValueError("Lot commodity must match Balance commodity")

        current_total_quantity = self.total_amount.quantity if self.total_amount.commodity == self.commodity else Decimal(0)
        current_total_cost = current_total_quantity * self.cost_basis_per_unit.quantity if self.cost_basis_per_unit and self.cost_basis_per_unit.commodity.name != "" else Decimal(0)

        new_total_quantity = current_total_quantity + lot.quantity.quantity
        new_total_cost = current_total_cost + (lot.quantity.quantity * lot.cost_basis_per_unit.quantity if lot.cost_basis_per_unit else Decimal(0))

        self.total_amount = Amount(new_total_quantity, self.commodity)

        if new_total_quantity != 0:
            cost_commodity = lot.cost_basis_per_unit.commodity if lot.cost_basis_per_unit else (self.cost_basis_per_unit.commodity if self.cost_basis_per_unit.commodity.name != "" else Commodity(""))
            self.cost_basis_per_unit = Amount(new_total_cost / new_total_quantity, cost_commodity)
        else:
            self.cost_basis_per_unit = Amount(Decimal(0), self.cost_basis_per_unit.commodity if self.cost_basis_per_unit.commodity.name != "" else Commodity(""))

        self.lots.append(lot)


@dataclass
class Account:
    """Represents an account in the hierarchical structure with its own and total balances."""
    name_part: str # The part of the account name at this level
    full_name: AccountName # The full name of the account up to this node
    parent: Optional['Account'] = field(default=None, repr=False) # Link to parent account
    children: Dict[str, 'Account'] = field(default_factory=dict) # Child accounts, keyed by name part
    own_balances: Dict[Commodity, Union[CashBalance, AssetBalance]] = field(default_factory=dict) # Balances from postings directly to this account level
    total_balances: Dict[Commodity, Amount] = field(default_factory=lambda: defaultdict(lambda: Amount(Decimal(0), Commodity("")))) # Aggregated balances (own + children)

    def get_own_balance(self, commodity: Commodity) -> Union[CashBalance, AssetBalance]:
        """Gets or creates a Balance subclass object for a given commodity in own_balances."""
        if commodity not in self.own_balances:
            if commodity.isCash():
                self.own_balances[commodity] = CashBalance(commodity=commodity)
            elif commodity.isStock() or commodity.isOption() or commodity.kind == CommodityKind.CRYPTO:
                 self.own_balances[commodity] = AssetBalance(commodity=commodity, total_amount=Amount(Decimal(0), commodity), cost_basis_per_unit=Amount(Decimal(0), Commodity("")))
            else:
                # Default to CashBalance for unknown types, or raise error
                self.own_balances[commodity] = CashBalance(commodity=commodity)
        return self.own_balances[commodity]

    def _propagate_total_balance_update(self, change_amount: Amount):
        """Adds the change_amount to total_balances and recursively calls parent."""
        if change_amount is None: # Guard against None change_amount
            return

        commodity = change_amount.commodity
        current_total_amount = self.total_balances.get(commodity, Amount(Decimal(0), commodity))
        new_total_amount = Amount(current_total_amount.quantity + change_amount.quantity, commodity)
        self.total_balances[commodity] = new_total_amount

        if self.parent:
            self.parent._propagate_total_balance_update(change_amount)

    def format_hierarchical(self, indent: int = 0, display: str = 'total') -> Generator[str, None, None]:
        """Recursively formats account balances with indentation, yielding lines, suppressing zero balances."""
        indent_str = "  " * indent
        temp_own_lines: List[str] = []
        all_commodities_for_this_account = set(self.own_balances.keys()).union(set(self.total_balances.keys()))

        for commodity in sorted(all_commodities_for_this_account, key=lambda x: str(x)):
            own_balance_obj = self.own_balances.get(commodity)
            total_balance_amount_obj = self.total_balances.get(commodity)
            line_to_add = ""
            if display == 'own':
                if own_balance_obj and own_balance_obj.total_amount.quantity != 0:
                    line_to_add = f"{indent_str}  {own_balance_obj.total_amount}"
            elif display == 'total':
                if total_balance_amount_obj and total_balance_amount_obj.quantity != 0:
                    line_to_add = f"{indent_str}  {total_balance_amount_obj}"
            elif display == 'both':
                parts = []
                if own_balance_obj and own_balance_obj.total_amount.quantity != 0:
                    parts.append(f"Own: {own_balance_obj.total_amount}")
                if total_balance_amount_obj and total_balance_amount_obj.quantity != 0:
                    parts.append(f"Total: {total_balance_amount_obj}")
                if parts:
                    line_to_add = f"{indent_str}  {' | '.join(parts)}"
            if line_to_add:
                temp_own_lines.append(line_to_add)

        children_lines: List[str] = []
        for child_name_part in sorted(self.children.keys()):
            child_account = self.children[child_name_part]
            child_output = list(child_account.format_hierarchical(indent + 1, display=display))
            if child_output:
                children_lines.extend(child_output)
        
        if temp_own_lines or children_lines:
            yield f"{indent_str}{self.full_name.name}"
            for line in temp_own_lines:
                yield line
            for line in children_lines:
                yield line

    def format_flat_lines(self, display: str = 'total') -> Generator[str, None, None]:
        """Formats the current single account's balances for a flat list representation."""
        balance_lines_for_this_account = []
        all_commodities = set(self.own_balances.keys()).union(set(self.total_balances.keys()))

        for commodity in sorted(all_commodities, key=lambda x: str(x)):
            own_balance = self.own_balances.get(commodity)
            total_balance_amount = self.total_balances.get(commodity)
            if display == 'own' and own_balance and own_balance.total_amount.quantity != 0:
                balance_lines_for_this_account.append(f"  {own_balance.total_amount}")
            elif display == 'total' and total_balance_amount and total_balance_amount.quantity != 0:
                balance_lines_for_this_account.append(f"  {total_balance_amount}")
            elif display == 'both':
                parts = []
                if own_balance and own_balance.total_amount.quantity != 0:
                    parts.append(f"Own: {own_balance.total_amount}")
                if total_balance_amount and total_balance_amount.quantity != 0:
                    parts.append(f"Total: {total_balance_amount}")
                if parts:
                    balance_lines_for_this_account.append(f"  {' | '.join(parts)}")
        
        if balance_lines_for_this_account:
            yield self.full_name.name
            for line in balance_lines_for_this_account:
                yield line

    def get_all_subaccounts(self) -> List['Account']:
        """Recursively collects the current account and all its descendant accounts into a flat list."""
        accounts = [self]
        for child in self.children.values():
            accounts.extend(child.get_all_subaccounts())
        return accounts

    def get_account(self, account_name_parts: List[str]) -> Optional['Account']:
        """Recursively returns the Account node for the given account name parts, or None if not found."""
        if not account_name_parts:
            return self
        first_part = account_name_parts[0]
        if first_part in self.children:
            return self.children[first_part].get_account(account_name_parts[1:])
        else:
            return None

    def _collect_lots_recursive(self, commodity: Commodity) -> List[Lot]:
        """Recursively collects all Lot objects for a commodity from this account and its children."""
        relevant_lots: List[Lot] = []
        if commodity in self.own_balances:
            balance = self.own_balances[commodity]
            if isinstance(balance, AssetBalance):
                relevant_lots.extend(balance.lots)
        for child_account in self.children.values():
            relevant_lots.extend(child_account._collect_lots_recursive(commodity))
        return relevant_lots

    def _format_balances_for_error(self, commodity_filter: Optional[Commodity] = None) -> str:
        """Formats own and total balances for an account, optionally filtered by commodity."""
        lines = []
        commodities_to_display = []
        if commodity_filter:
            if commodity_filter in self.own_balances or commodity_filter in self.total_balances:
                commodities_to_display.append(commodity_filter)
        else:
            commodities_to_display = sorted(
                list(set(self.own_balances.keys()).union(set(self.total_balances.keys()))),
                key=lambda c: str(c)
            )

        for comm in commodities_to_display:
            own_b = self.own_balances.get(comm)
            total_b = self.total_balances.get(comm)
            own_s = f"Own: {own_b.total_amount}" if own_b and own_b.total_amount.quantity != 0 else ""
            total_s = f"Total: {total_b}" if total_b and total_b.quantity != 0 else ""
            
            if own_s and total_s:
                lines.append(f"    - {comm.name}: {own_s} | {total_s}")
            elif own_s:
                lines.append(f"    - {comm.name}: {own_s}")
            elif total_s:
                lines.append(f"    - {comm.name}: {total_s}")
        return "\n".join(lines) if lines else "    (No relevant balances to display)"


@dataclass
class BalanceSheet:
    """Represents the balance sheet with a hierarchical structure of accounts."""
    root_accounts: Dict[str, Account] = field(default_factory=dict)
    capital_gains_realized: List[CapitalGainResult] = field(default_factory=list)

    def get_account(self, account_name: AccountName) -> Optional[Account]:
        if not account_name.parts:
            return None
        first_part = account_name.parts[0]
        if first_part in self.root_accounts:
            return self.root_accounts[first_part].get_account(account_name.parts[1:])
        else:
            return None

    def get_or_create_account(self, account_name: AccountName) -> Account:
        current_node: Optional[Account] = None
        parent_node: Optional[Account] = None
        current_dict = self.root_accounts
        for i, part in enumerate(account_name.parts):
            if part not in current_dict:
                full_name_up_to_here = AccountName(account_name.parts[:i+1])
                new_account = Account(name_part=part, full_name=full_name_up_to_here, parent=parent_node)
                current_dict[part] = new_account
                current_node = new_account
            else:
                current_node = current_dict[part]
            parent_node = current_node
            current_dict = current_node.children
        if current_node is None:
             raise Exception(f"Could not get or create account for {account_name.name}")
        return current_node

    def _apply_direct_posting_effects(self, posting: Posting, transaction: Transaction):
        """Applies direct effects of a posting: updates own balance, creates lots for acquisitions."""
        if posting.amount is None:
            return
        
        current_amount: Amount = posting.amount # Ensure Mypy knows it's not None

        account_node = self.get_or_create_account(posting.account)
        balance_obj = account_node.get_own_balance(current_amount.commodity)

        if posting.isOpening() and isinstance(balance_obj, AssetBalance):
            cost = transaction.get_posting_cost(posting)
            if cost:
                cost_basis_per_unit = None
                if cost.kind == CostKind.TotalCost and current_amount.quantity != 0:
                    cost_basis_per_unit_value = abs(cost.amount.quantity / current_amount.quantity)
                    cost_basis_per_unit = Amount(cost_basis_per_unit_value, cost.amount.commodity)
                elif cost.kind == CostKind.UnitCost:
                    cost_basis_per_unit = cost.amount
                
                if cost_basis_per_unit:
                    lot = Lot(
                        acquisition_date=str(transaction.date),
                        quantity=current_amount,
                        cost_basis_per_unit=cost_basis_per_unit,
                        original_posting=posting
                    )
                    balance_obj.add_lot(lot) # add_lot updates AssetBalance.total_amount
        elif isinstance(balance_obj, CashBalance):
            balance_obj.add_posting(posting) # Posting object itself is passed, add_posting handles its amount
        elif posting.isClosing() and isinstance(balance_obj, AssetBalance):
            # Just update the quantity for the sale; FIFO will handle lot adjustments.
            balance_obj.total_amount = Amount(balance_obj.total_amount.quantity + current_amount.quantity, balance_obj.commodity)
        
        account_node._propagate_total_balance_update(current_amount)

    def _apply_gain_loss_to_income_accounts(self, gain_loss_amount: Amount, source_account_name: AccountName, transaction_date: date):
        """Creates and applies a synthetic posting for the calculated capital gain or loss."""
        if gain_loss_amount.quantity == 0:
            return

        if gain_loss_amount.quantity > 0:
            gain_loss_income_expense_account_name = AccountName(["income", "capital_gains"])
        else:
            gain_loss_income_expense_account_name = AccountName(["expenses", "capital_losses"])

        gain_loss_node = self.get_or_create_account(gain_loss_income_expense_account_name)
        
        synthetic_posting = Posting(
            account=gain_loss_income_expense_account_name,
            amount=Amount(gain_loss_amount.quantity, gain_loss_amount.commodity), # Ensure correct sign for income/expense
            comment=Comment(comment=f"Capital gain/loss from {source_account_name.name} sale on {transaction_date.strftime('%Y-%m-%d')}")
        )

        if synthetic_posting.amount is None: # Should not happen if gain_loss_amount.quantity != 0
            raise ValueError("Synthetic posting for gain/loss has no amount.")

        current_synthetic_amount: Amount = synthetic_posting.amount

        synthetic_balance_obj = gain_loss_node.get_own_balance(current_synthetic_amount.commodity)
        if isinstance(synthetic_balance_obj, CashBalance): # Gains/losses are typically cash-like
            synthetic_balance_obj.add_posting(synthetic_posting) # Pass the whole posting
        else:
            account_details = ""
            gain_loss_account_node = self.get_account(gain_loss_income_expense_account_name)
            if gain_loss_account_node:
                account_details = gain_loss_account_node._format_balances_for_error(current_synthetic_amount.commodity)
            
            raise ValueError(
                f"Gain/loss account {gain_loss_income_expense_account_name.name} is not a CashBalance type for commodity {current_synthetic_amount.commodity.name}. Cannot record gain/loss.\n"
                f"Account Details ({gain_loss_income_expense_account_name.name}):\n{account_details}"
            )

        gain_loss_node._propagate_total_balance_update(current_synthetic_amount)

    def _format_transaction_cash_postings_for_error(self, transaction: Transaction, exclude_posting: Posting) -> str:
        """Formats cash postings in a transaction for error messages, excluding one specific posting."""
        lines = []
        for p in transaction.postings:
            if p != exclude_posting and p.amount and p.amount.commodity.isCash():
                lines.append(f"    - {p.account.name}: {p.amount}")
        return "\n".join(lines) if lines else "    (No other cash postings found)"

    def _format_lot_details_for_error(self, lots: List[Lot]) -> str:
        """Formats lot details for error messages."""
        if not lots:
            return "    (No lots available or considered)"
        lines = []
        for lot_item in lots:
            lines.append(f"    - Acq. Date: {lot_item.acquisition_date}, Orig. Qty: {lot_item.quantity}, Rem. Qty: {lot_item.remaining_quantity}, Cost/Unit: {lot_item.cost_basis_per_unit}")
        return "\n".join(lines)

    def _process_asset_sale_capital_gains(self, sale_posting: Posting, transaction: Transaction):
        """Processes an asset sale for capital gains calculation and application."""
        if sale_posting.amount is None:
            return

        closing_account_name = sale_posting.account
        closing_commodity = sale_posting.amount.commodity
        closing_quantity = abs(sale_posting.amount.quantity)

        if not (closing_commodity and closing_quantity > 0):
            return

        # Identify actual cash proceeds from other commodities
        cash_proceeds_postings: List[Posting] = []
        for p in transaction.postings:
            if p != sale_posting and p.amount and p.amount.quantity > 0 and \
               p.amount.commodity != closing_commodity and p.amount.commodity.isCash():
                cash_proceeds_postings.append(p)

        if not cash_proceeds_postings:
            # No cash proceeds of a different commodity found, this is likely a transfer or non-sale event.
            # Do not treat as a sale for capital gains purposes.
            return

        # Consolidate cash proceeds
        total_proceeds: Optional[Amount] = None
        for p_cash in cash_proceeds_postings:
            if p_cash.amount is None: continue # Should not happen due to check above
            if total_proceeds is None:
                total_proceeds = p_cash.amount
            elif total_proceeds.commodity == p_cash.amount.commodity:
                total_proceeds = Amount(total_proceeds.quantity + p_cash.amount.quantity, total_proceeds.commodity)
            else:
                # Multiple different cash commodities found as proceeds
                cash_details_str = self._format_transaction_cash_postings_for_error(transaction, sale_posting)
                raise ValueError(
                    f"Multiple different cash commodities found in proceeds for transaction {transaction.date} - {transaction.payee}. Cannot reliably determine proceeds.\n"
                    f"Cash Postings Found:\n{cash_details_str}"
                )
        
        if total_proceeds is None: # Should be caught by 'if not cash_proceeds_postings' but as a safeguard
            # This case implies something went wrong if cash_proceeds_postings was not empty
            # but total_proceeds ended up as None.
            sale_posting_details = f"    Sale Posting: {sale_posting.account.name} {sale_posting.amount}"
            raise ValueError(
                f"Logical error: Cash proceeds postings were identified but could not be consolidated for transaction {transaction.date} - {transaction.payee}.\n"
                f"{sale_posting_details}"
            )

        proceeds_commodity_set = True # Flag that we have valid, consolidated proceeds

        quantity_to_match = closing_quantity
        closing_account_node = self.get_or_create_account(closing_account_name)
        all_relevant_lots = closing_account_node._collect_lots_recursive(closing_commodity)

        if not all_relevant_lots:
            account_balance_info = closing_account_node._format_balances_for_error(closing_commodity)
            raise ValueError(
                f"No lots found for {closing_account_name.name}:{closing_commodity.name} to match sale in transaction {transaction.date} - {transaction.payee}.\n"
                f"Account {closing_account_name.name} balance for {closing_commodity.name}:\n{account_balance_info}"
            )

        try:
            sorted_lots = sorted(all_relevant_lots, key=lambda lot: datetime.datetime.strptime(lot.acquisition_date, '%Y-%m-%d').date())
        except ValueError as e:
            # It's hard to pinpoint the exact failing lot before sorting, but we can list all acquisition dates.
            lot_acq_dates = [f"'{l.acquisition_date}'" for l in all_relevant_lots]
            raise ValueError(
                f"Error parsing acquisition date for sorting lots for {closing_account_name.name}:{closing_commodity.name}: {e}.\n"
                f"Problematic acquisition dates might be among: {', '.join(lot_acq_dates)}"
            )

        for current_lot in sorted_lots:
            if quantity_to_match <= 0:
                break
            if current_lot.remaining_quantity > 0:
                match_quantity_decimal = min(quantity_to_match, current_lot.remaining_quantity)
                match_quantity_amount = Amount(match_quantity_decimal, closing_commodity)

                cost_basis_decimal = match_quantity_decimal * current_lot.cost_basis_per_unit.quantity
                cost_basis_amount = Amount(cost_basis_decimal, current_lot.cost_basis_per_unit.commodity)

                proceeds_decimal = Decimal(0)
                if closing_quantity != 0 and proceeds_commodity_set : # Ensure proceeds were found
                    proceeds_decimal = (match_quantity_decimal / closing_quantity) * total_proceeds.quantity
                
                proceeds_amount = Amount(proceeds_decimal, total_proceeds.commodity if proceeds_commodity_set else cost_basis_amount.commodity) # Fallback commodity for proceeds if none found

                gain_loss_amount = Amount(Decimal(0), proceeds_amount.commodity)
                if cost_basis_amount.commodity != proceeds_amount.commodity and proceeds_commodity_set:
                    lot_detail_str = f"    - Acq. Date: {current_lot.acquisition_date}, Cost/Unit: {current_lot.cost_basis_per_unit}"
                    raise ValueError(
                        f"Cost basis commodity ({cost_basis_amount.commodity.name}) and proceeds commodity ({proceeds_amount.commodity.name}) differ. Cannot accurately calculate gain/loss.\n"
                        f"Transaction: {transaction.date} - {transaction.payee}\n"
                        f"Sale Posting: {sale_posting.account.name} {sale_posting.amount}\n"
                        f"Matched Lot Details:\n{lot_detail_str}"
                    )
                else:
                    gain_loss_decimal = proceeds_decimal - cost_basis_decimal
                    gain_loss_amount = Amount(gain_loss_decimal, proceeds_amount.commodity)

                try:
                    acquisition_date_obj = datetime.datetime.strptime(current_lot.acquisition_date, '%Y-%m-%d').date()
                except ValueError as e:
                    raise ValueError(f"Could not parse acquisition date '{current_lot.acquisition_date}' for lot being processed: {e}") # Already specific

                self.capital_gains_realized.append(CapitalGainResult(
                    closing_posting=sale_posting,
                    opening_lot_original_posting=current_lot.original_posting,
                    matched_quantity=match_quantity_amount,
                    cost_basis=cost_basis_amount,
                    proceeds=proceeds_amount,
                    gain_loss=gain_loss_amount,
                    closing_date=transaction.date,
                    acquisition_date=acquisition_date_obj
                ))

                current_lot.remaining_quantity -= match_quantity_decimal
                quantity_to_match -= match_quantity_decimal
                
                self._apply_gain_loss_to_income_accounts(gain_loss_amount, closing_account_name, transaction.date)

        if quantity_to_match > 0:
            lot_details_str = self._format_lot_details_for_error(all_relevant_lots) # Use all_relevant_lots as sorted_lots might be empty if parsing failed
            account_details_str = closing_account_node._format_balances_for_error(closing_commodity)
            error_message = (
                f"Not enough open lots found for {closing_quantity} {closing_commodity.name} "
                f"in {closing_account_name.name} to match closing posting in transaction "
                f"{transaction.date} - {transaction.payee}. Remaining to match: {quantity_to_match}.\n"
                f"Account Details ({closing_account_name.name} for {closing_commodity.name}):\n{account_details_str}\n"
                f"Available Lots Considered:\n{lot_details_str}"
            )
            raise ValueError(error_message)


    def apply_transaction(self, transaction: Transaction) -> 'BalanceSheet':
        """
        Applies a single transaction to the balance sheet, updating balances, lots, and calculating capital gains.
        This method modifies the BalanceSheet instance it's called on and returns it.
        """
        for posting in transaction.postings:
            if posting.amount is None: # Skip postings without amounts
                continue
            self._apply_direct_posting_effects(posting, transaction)

            # Check if this posting is an asset sale to trigger capital gains processing
            account_node = self.get_or_create_account(posting.account) # Get account node again, or pass from above
            balance_obj = account_node.get_own_balance(posting.amount.commodity) # Get balance obj again, or pass

            if posting.isClosing() and isinstance(balance_obj, AssetBalance):
                self._process_asset_sale_capital_gains(posting, transaction)
        return self

    @staticmethod
    def from_transactions(transactions: List[Transaction]) -> 'BalanceSheet':
        """
        Builds a BalanceSheet with a hierarchical account structure by applying transactions.
        """
        sorted_transactions = sorted(transactions, key=lambda t: t.date)
        balance_sheet = BalanceSheet()
        for transaction in sorted_transactions:
            balance_sheet.apply_transaction(transaction)
        return balance_sheet

    @staticmethod
    def from_journal(journal: 'Journal') -> 'BalanceSheet': # Add type hint for Journal
        """
        Builds a BalanceSheet from a Journal object.
        Extracts transactions from the journal and then uses from_transactions.
        """
        transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
        return BalanceSheet.from_transactions(transactions_only)

    def format_account_hierarchy(self, display: str = 'total') -> Generator[str, None, None]:
        for root_account_name_part in sorted(self.root_accounts.keys()):
            root_account = self.root_accounts[root_account_name_part]
            yield from root_account.format_hierarchical(indent=0, display=display)

    def format_account_flat(self, display: str = 'total') -> Generator[str, None, None]:
        all_accounts: List['Account'] = []
        for root_account in self.root_accounts.values():
            all_accounts.extend(root_account.get_all_subaccounts())
        sorted_accounts = sorted(all_accounts, key=lambda acc: acc.full_name.name)
        for account in sorted_accounts:
            if display == 'own' and account.children:
                has_own_balances_to_display = False
                for commodity_key in account.own_balances:
                    own_bal = account.own_balances.get(commodity_key)
                    if own_bal and own_bal.total_amount.quantity != 0:
                        has_own_balances_to_display = True
                        break
                if not has_own_balances_to_display:
                    continue
            yield from account.format_flat_lines(display=display)
