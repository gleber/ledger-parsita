from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from decimal import Decimal
from returns.result import Result, Success, Failure

from src.classes import Transaction, Posting, Cost as PostingCost # Alias to avoid confusion
from src.base_classes import Amount, Commodity
from src.common_types import CostKind # CostKind is from common_types

# --- Custom Error for unhandled remainders ---
@dataclass
class UnhandledPostingDetail:
    account_name: str
    original_quantity: Decimal
    remaining_quantity: Decimal
    commodity: str 
    original_index: int

    def __str__(self) -> str:
        return (f"Account: {self.account_name}, "
                f"Original: {self.original_quantity} {self.commodity}, "
                f"Remainder: {self.remaining_quantity} {self.commodity}, "
                f"Index: {self.original_index}")

@dataclass
class UnhandledRemainderError(Exception):
    transaction_ref: str
    unhandled_postings: List[UnhandledPostingDetail]
    
    def __str__(self) -> str:
        details = "\n    ".join(str(p) for p in self.unhandled_postings)
        return f"Transaction '{self.transaction_ref}' has unhandled posting remainders:\n    {details}"

# --- Data Structures ---
@dataclass(frozen=True)
class Flow:
    from_node: str
    to_node: str
    out_amount: Amount
    in_amount: Amount
    label: str
    conversion_rate: Optional[Amount] = None

    def __str__(self):
        rate_str = f", Rate: {self.conversion_rate}" if self.conversion_rate else ""
        return (f"Flow: {self.from_node} ({self.out_amount}) "
                f"--> {self.to_node} ({self.in_amount}){rate_str} "
                f"| Label: [{self.label}]")

@dataclass
class PostingStatus:
    original_posting: Posting
    original_index: int
    remaining_quantity: Amount = field(init=False) 

    def __post_init__(self):
        if self.original_posting.amount is None:
            raise ValueError(
                f"Posting at index {self.original_index} for account "
                f"'{self.original_posting.account.name}' has no amount (elided and not resolved?). "
                "transaction_to_flows requires postings with concrete amounts."
            )
        self.remaining_quantity = self.original_posting.amount


# 2. Helper Function for finding and updating counterparty postings
def find_and_update_balancing_posting(
    target_value_effect: Amount, 
    postings_status_list: List[PostingStatus], 
    exclude_indices: List[int] 
) -> Optional[Tuple[str, int, Amount]]:
    target_quantity_val = target_value_effect.quantity
    target_commodity_name = target_value_effect.commodity.name

    # Try exact full consumption first
    for p_status in postings_status_list:
        if p_status.original_index in exclude_indices or p_status.remaining_quantity.quantity == Decimal('0'):
            continue
        
        original_p = p_status.original_posting
        is_unpriced = original_p.cost is None # A posting is unpriced if it has no 'cost' attribute

        if original_p.amount and original_p.amount.commodity.name == target_commodity_name and is_unpriced:
            if p_status.remaining_quantity.quantity == target_quantity_val:
                amount_consumed = p_status.remaining_quantity
                p_status.remaining_quantity = Amount(Decimal('0'), amount_consumed.commodity)
                return original_p.account.name, p_status.original_index, amount_consumed

    # Try partial consumption from a larger posting
    for p_status in postings_status_list:
        if p_status.original_index in exclude_indices or p_status.remaining_quantity.quantity == Decimal('0'):
            continue

        original_p = p_status.original_posting
        is_unpriced = original_p.cost is None
        
        if original_p.amount and original_p.amount.commodity.name == target_commodity_name and is_unpriced:
            if target_quantity_val > Decimal('0') and \
               p_status.remaining_quantity.quantity >= target_quantity_val:
                consumed_value = target_quantity_val
                p_status.remaining_quantity = Amount(
                    p_status.remaining_quantity.quantity - consumed_value, 
                    p_status.remaining_quantity.commodity
                )
                return original_p.account.name, p_status.original_index, Amount(consumed_value, target_value_effect.commodity)
            
            elif target_quantity_val < Decimal('0') and \
                 p_status.remaining_quantity.quantity <= target_quantity_val:
                consumed_value = target_quantity_val
                p_status.remaining_quantity = Amount(
                    p_status.remaining_quantity.quantity - consumed_value,
                    p_status.remaining_quantity.commodity
                )
                return original_p.account.name, p_status.original_index, Amount(consumed_value, target_value_effect.commodity)
                
    return None


# 3. Refactored Processing Functions
def _get_posting_price_info(posting: Posting, main_commodity_quantity_val: Decimal) -> Tuple[Optional[Amount], Optional[Commodity], Optional[Amount]]:
    """
    Extracts conversion value, conversion commodity, and per-unit rate from a posting's cost.
    Returns (value_effect_in_conversion_currency_Amount, conversion_commodity_obj, rate_Amount)
    """
    value_effect_in_conversion_currency: Optional[Amount] = None
    conversion_commodity_obj: Optional[Commodity] = None
    rate_as_amount: Optional[Amount] = None

    if posting.cost:  # posting.cost is of type src.classes.Cost (aliased as PostingCost)
        cost_obj: PostingCost = posting.cost 
        # cost_obj.kind is CostKind (from src.common_types)
        # cost_obj.amount is the Amount of the price (e.g., 10 USD for "@ 10 USD")

        if cost_obj.kind == CostKind.UnitCost:  # e.g., "@ 10 USD"
            rate_as_amount = cost_obj.amount  # This is the per-unit price
            conversion_commodity_obj = rate_as_amount.commodity
            value_effect_in_conversion_currency = Amount(
                main_commodity_quantity_val * rate_as_amount.quantity,
                conversion_commodity_obj
            )
        elif cost_obj.kind == CostKind.TotalCost:  # e.g., "@@ 100 USD"
            total_price_amount = cost_obj.amount  # This is the total price
            conversion_commodity_obj = total_price_amount.commodity
            value_effect_in_conversion_currency = total_price_amount

            if main_commodity_quantity_val != Decimal('0'):
                rate_as_amount = Amount(
                    total_price_amount.quantity / main_commodity_quantity_val,
                    conversion_commodity_obj
                )
    
    return value_effect_in_conversion_currency, conversion_commodity_obj, rate_as_amount


def _process_priced_conversions(
    postings_status_list: List[PostingStatus], 
    flows: List[Flow]
) -> bool:
    made_progress_this_pass = False
    for i in range(len(postings_status_list)):
        main_posting_status = postings_status_list[i]
        main_original_posting = main_posting_status.original_posting
        
        if main_posting_status.remaining_quantity.quantity == Decimal('0'):
            continue
        
        if main_original_posting.amount and abs(main_posting_status.remaining_quantity.quantity) != abs(main_original_posting.amount.quantity):
            continue 

        is_priced = main_original_posting.cost is not None

        is_sale_conversion = (
            main_original_posting.amount and main_original_posting.amount.quantity < Decimal('0') and
            is_priced
        )
        if is_sale_conversion and main_original_posting.amount:
            asset_account_name = main_original_posting.account.name
            quantity_sold_val = abs(main_posting_status.remaining_quantity.quantity) 
            commodity_sold_obj = main_posting_status.remaining_quantity.commodity
            
            out_amount_obj = Amount(quantity_sold_val, commodity_sold_obj)
            
            value_generated_amount, conversion_commodity_obj, rate_amount_obj = _get_posting_price_info(
                main_original_posting, quantity_sold_val # Pass absolute quantity for rate calculation if needed
            )
            
            if not value_generated_amount or not conversion_commodity_obj:
                continue

            if commodity_sold_obj.name == conversion_commodity_obj.name: 
                continue

            in_amount_obj = value_generated_amount
            current_op_indices = {main_posting_status.original_index}
            
            counterparty_info = find_and_update_balancing_posting(
                in_amount_obj, 
                postings_status_list, list(current_op_indices) 
            )
            
            if counterparty_info:
                counterparty_account_name, cp_idx, consumed_amount = counterparty_info
                if consumed_amount.quantity != in_amount_obj.quantity:
                        print(f"Warning: Partial consumption for proceeds of {commodity_sold_obj.name} conversion. "
                              f"Expected {in_amount_obj}, balanced by {consumed_amount} from {counterparty_account_name}")

                label_summary = (f"{out_amount_obj.quantity} {out_amount_obj.commodity.name} -> "
                                 f"{in_amount_obj.quantity:.2f} {in_amount_obj.commodity.name}")
                flows.append(Flow(from_node=asset_account_name, 
                                  to_node=counterparty_account_name, 
                                  out_amount=out_amount_obj,
                                  in_amount=in_amount_obj,
                                  conversion_rate=rate_amount_obj,
                                  label=label_summary))
                
                main_posting_status.remaining_quantity = Amount(Decimal('0'), commodity_sold_obj)
                made_progress_this_pass = True
                return True

        is_purchase_conversion = (
            main_original_posting.amount and main_original_posting.amount.quantity > Decimal('0') and
            is_priced
        )
        if is_purchase_conversion and main_original_posting.amount:
            asset_account_name = main_original_posting.account.name
            quantity_bought_val = main_posting_status.remaining_quantity.quantity
            commodity_bought_obj = main_posting_status.remaining_quantity.commodity

            in_amount_obj = Amount(quantity_bought_val, commodity_bought_obj)
            
            cost_amount, conversion_commodity_obj, rate_amount_obj = _get_posting_price_info(
                main_original_posting, quantity_bought_val
            )

            if not cost_amount or not conversion_commodity_obj:
                continue

            if commodity_bought_obj.name == conversion_commodity_obj.name:
                continue
            
            out_amount_obj = cost_amount
            current_op_indices = {main_posting_status.original_index}
            
            target_for_balancing = Amount(-out_amount_obj.quantity, out_amount_obj.commodity)
            counterparty_info = find_and_update_balancing_posting(
                target_for_balancing, 
                postings_status_list, list(current_op_indices)
            )

            if counterparty_info:
                counterparty_account_name, cp_idx, consumed_amount = counterparty_info
                if consumed_amount.quantity != target_for_balancing.quantity:
                    print(f"Warning: Partial consumption for cost of {commodity_bought_obj.name} conversion. "
                          f"Expected {target_for_balancing}, balanced by {consumed_amount} from {counterparty_account_name}")

                label_summary = (f"{out_amount_obj.quantity:.2f} {out_amount_obj.commodity.name} -> "
                                 f"{in_amount_obj.quantity} {in_amount_obj.commodity.name}")
                flows.append(Flow(from_node=counterparty_account_name, 
                                  to_node=asset_account_name, 
                                  out_amount=out_amount_obj,
                                  in_amount=in_amount_obj,
                                  conversion_rate=rate_amount_obj,
                                  label=label_summary))
                main_posting_status.remaining_quantity = Amount(Decimal('0'), commodity_bought_obj)
                made_progress_this_pass = True
                return True
    return made_progress_this_pass


def _process_simple_unpriced_transfers(
    postings_status_list: List[PostingStatus], 
    flows: List[Flow]
) -> bool:
    made_progress_this_pass = False
    for i_p1 in range(len(postings_status_list)):
        p1_status = postings_status_list[i_p1]
        if p1_status.remaining_quantity.quantity == Decimal('0'): continue
        if p1_status.original_posting.cost: continue # Skip if priced

        for i_p2 in range(i_p1 + 1, len(postings_status_list)):
            p2_status = postings_status_list[i_p2]
            if p2_status.remaining_quantity.quantity == Decimal('0'): continue
            if p2_status.original_posting.cost: continue # Skip if priced

            if p1_status.remaining_quantity.commodity.name == p2_status.remaining_quantity.commodity.name and \
               p1_status.remaining_quantity.quantity == -p2_status.remaining_quantity.quantity:
                
                from_acc_name, to_acc_name = "", ""
                transfer_amount_obj: Amount
                
                p1_qty = p1_status.remaining_quantity.quantity
                p1_comm_obj = p1_status.remaining_quantity.commodity

                if p1_qty < Decimal('0'): 
                    from_acc_name = p1_status.original_posting.account.name
                    to_acc_name = p2_status.original_posting.account.name
                    transfer_amount_obj = Amount(abs(p1_qty), p1_comm_obj)
                else: 
                    from_acc_name = p2_status.original_posting.account.name
                    to_acc_name = p1_status.original_posting.account.name
                    transfer_amount_obj = Amount(p1_qty, p1_comm_obj)
                
                label_summary = f"{transfer_amount_obj.quantity} {transfer_amount_obj.commodity.name} transfer"
                
                flows.append(Flow(from_node=from_acc_name, 
                                  to_node=to_acc_name, 
                                  out_amount=transfer_amount_obj, 
                                  in_amount=transfer_amount_obj,
                                  conversion_rate=None, 
                                  label=label_summary))
                
                p1_status.remaining_quantity = Amount(Decimal('0'), p1_comm_obj)
                p2_status.remaining_quantity = Amount(Decimal('0'), p2_status.remaining_quantity.commodity)
                made_progress_this_pass = True
                return True
    return made_progress_this_pass


def transaction_to_flows(
    transaction_data: Transaction
) -> Result[List[Flow], UnhandledRemainderError]:
    flows: List[Flow] = []
    
    try:
        postings_status_list = [
            PostingStatus(original_posting=p, original_index=i)
            for i, p in enumerate(transaction_data.postings)
        ]
    except ValueError as e:
        # Construct a generic UnhandledPostingDetail for the error message
        # The actual failing posting isn't easily identifiable here without more context from the loop
        error_detail = UnhandledPostingDetail(
            account_name="<Initialization Error>",
            original_quantity=Decimal('0'),
            remaining_quantity=Decimal('0'),
            commodity="N/A",
            original_index=-1 
        )
        # Use the message from the ValueError to give more specific feedback
        # This is a slight misuse of UnhandledRemainderError, but conveys the problem.
        # A custom error for init failures might be better long-term.
        return Failure(UnhandledRemainderError(
            transaction_ref=f"{transaction_data.date} {transaction_data.payee or ''} - Init Error: {str(e)}",
            unhandled_postings=[error_detail] 
        ))

    iteration_limit = len(postings_status_list) * len(postings_status_list) + 10 
    current_iter = 0
    
    while current_iter < iteration_limit:
        current_iter += 1
        made_progress_in_this_iteration = False

        if _process_priced_conversions(postings_status_list, flows):
            made_progress_in_this_iteration = True
            continue
        
        if not made_progress_in_this_iteration:
            if _process_simple_unpriced_transfers(postings_status_list, flows):
                made_progress_in_this_iteration = True
                continue
        
        if not made_progress_in_this_iteration:
            break 

    unhandled_postings_details: List[UnhandledPostingDetail] = []
    for p_status in postings_status_list:
        if p_status.remaining_quantity.quantity != Decimal('0'):
            original_p = p_status.original_posting
            orig_qty = original_p.amount.quantity if original_p.amount else Decimal('0')
            orig_comm_name = original_p.amount.commodity.name if original_p.amount else "N/A"
            
            detail = UnhandledPostingDetail(
                account_name=original_p.account.name,
                original_quantity=orig_qty,
                remaining_quantity=p_status.remaining_quantity.quantity,
                commodity=p_status.remaining_quantity.commodity.name,
                original_index=p_status.original_index
            )
            unhandled_postings_details.append(detail)
    
    if unhandled_postings_details:
        error_message_ref = f"{transaction_data.date} {transaction_data.payee or ''}"
        return Failure(UnhandledRemainderError(transaction_ref=error_message_ref, unhandled_postings=unhandled_postings_details))

    if current_iter >= iteration_limit:
        return Failure(UnhandledRemainderError(
            transaction_ref=f"{transaction_data.date} {transaction_data.payee or ''} - Iteration Limit Reached",
            unhandled_postings=[UnhandledPostingDetail( # Generic detail for iteration limit
                account_name="<System>",
                original_quantity=Decimal('0'), remaining_quantity=Decimal('0'),
                commodity="N/A", original_index=-1 
            )]
        ))
    
    return Success(flows)
