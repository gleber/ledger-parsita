from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from .classes import Transaction, Posting # Adjusted for potential direct use
    from .common_types import Amount, Cost, CostKind, Commodity, Comment # Ensure all necessary types are available
    from .base_classes import AccountName # Ensure AccountName is available

from .errors import (
    TransactionBalanceError,
    NoCommoditiesElidedError,
    ImbalanceError,
    UnresolvedElidedAmountError,
    AmbiguousElidedAmountError,
    MultipleCommoditiesRemainingError, # Added this import
)


from collections import defaultdict
from dataclasses import replace
from decimal import Decimal

from returns.result import Result, Success, Failure
# from returns.pipeline import flow # Not used directly in this file
# from returns.pointfree import bind # Not used directly in this file
# from returns.maybe import Maybe, Some, Nothing # Not used directly in this file


def _transaction_balance(tx: "Transaction") -> Result["Transaction", TransactionBalanceError]:
    """
    Balances a transaction, handling elided amounts and cost-value logic.
    """
    from .classes import Posting, Amount, Cost, CostKind, Commodity, Comment, AccountName # Moved imports here to ensure availability

    current_tx_copy = replace(tx)  # Work with a copy for potential augmentation
    commodity_sums: Dict["Commodity", Decimal] = defaultdict(Decimal)
    elided_postings_indices = []

    # Calculate initial sums (including cost-value logic) and identify elided postings
    for i, posting in enumerate(current_tx_copy.postings):
        if posting.amount and isinstance(posting.amount, Amount):
            # Add effect of the primary amount
            commodity_sums[posting.amount.commodity] += posting.amount.quantity

            # If there's a cost, this posting also contributes to the balance of the cost's commodity.
            # The value of this posting in terms of the cost commodity is added.
            if (
                posting.cost
                and isinstance(posting.cost, Cost)
                and isinstance(posting.cost.amount, Amount)
            ):
                cost_commodity = posting.cost.amount.commodity
                cost_price_per_unit_or_total = posting.cost.amount.quantity

                if posting.cost.kind == CostKind.UnitCost:  # @ (per-unit price)
                    # Value in cost_commodity is (primary_quantity * price_per_unit)
                    value_in_cost_commodity = (
                        posting.amount.quantity * cost_price_per_unit_or_total
                    )
                    commodity_sums[cost_commodity] += value_in_cost_commodity
                elif posting.cost.kind == CostKind.TotalCost:  # @@ (total price)
                    # Value in cost_commodity is total_price (if primary_quantity > 0)
                    # or -total_price (if primary_quantity < 0).
                    if posting.amount.quantity > Decimal(0):
                        commodity_sums[
                            cost_commodity
                        ] += cost_price_per_unit_or_total
                    elif posting.amount.quantity < Decimal(0):
                        commodity_sums[
                            cost_commodity
                        ] -= cost_price_per_unit_or_total
                    # If posting.amount.quantity is 0, a total cost (@@) doesn't contribute to balancing here.
        else:
            elided_postings_indices.append(i)
            # Note: elided postings with balance assertions are handled later in elision logic

    if not elided_postings_indices:  # No elided amounts
        imbalances = {
            comm: sm for comm, sm in commodity_sums.items() if sm != Decimal(0)
        }

        if not imbalances:  # Already balanced
            return Success(current_tx_copy)

        if 1 <= len(imbalances) <= 2:  # Potential for equity inference
            inferred_equity_postings = []
            equity_account = AccountName(["equity", "conversion"])
            for comm, sum_val in imbalances.items():
                inferred_equity_postings.append(
                    Posting(
                        account=equity_account, amount=Amount(-sum_val, comm)
                    ).add_comment(Comment("inferred by equity conversion"))
                )

            final_postings = []
            final_postings.extend(current_tx_copy.postings)
            final_postings.extend(inferred_equity_postings)
            augmented_tx = replace(current_tx_copy, postings=final_postings)
            return Success(augmented_tx)
        else:  # More than 2 imbalances, cannot infer equity simply
            first_imbalance_comm = list(imbalances.keys())[0]
            return Failure(
                ImbalanceError(
                    first_imbalance_comm, imbalances[first_imbalance_comm]
                )
            )
    else:  # There are elided amounts
        actual_elided_postings = [
            current_tx_copy.postings[i] for i in elided_postings_indices
        ]

        if len(actual_elided_postings) == len(current_tx_copy.postings):
            return Failure(NoCommoditiesElidedError())

        if len(actual_elided_postings) == 1:
            elided_posting_original = actual_elided_postings[0]
            elided_idx_in_original_postings = current_tx_copy.postings.index(
                elided_posting_original
            )

            current_imbalances = {
                c: s for c, s in commodity_sums.items() if s != Decimal(0)
            }

            if len(current_imbalances) == 1:
                comm, net_sum = list(current_imbalances.items())[0]
                modified_posting = replace(
                    elided_posting_original,
                    amount=Amount(quantity=-net_sum, commodity=comm),
                ).add_comment(Comment("auto-balanced"))
                current_tx_copy.postings[elided_idx_in_original_postings] = (
                    modified_posting
                )
                return Success(current_tx_copy)

            elif not current_imbalances:
                if commodity_sums:
                    comm_to_use = list(commodity_sums.keys())[0]
                    modified_posting = replace(
                        elided_posting_original,
                        amount=Amount(quantity=Decimal(0), commodity=comm_to_use),
                    ).add_comment(Comment("auto-balanced"))
                    current_tx_copy.postings[elided_idx_in_original_postings] = (
                        modified_posting
                    )
                    return Success(current_tx_copy)
                else:
                    return Failure(NoCommoditiesElidedError())
            else:
                first_imbalance_comm = list(current_imbalances.keys())[0]
                return Failure(UnresolvedElidedAmountError(first_imbalance_comm))

        # Multiple elided postings
        all_sums_zero = all(s == Decimal(0) for s in commodity_sums.values())
        if all_sums_zero:
            if commodity_sums:
                comm_to_use = list(commodity_sums.keys())[0]
                for i in elided_postings_indices:
                    original_posting = current_tx_copy.postings[i]
                    current_tx_copy.postings[i] = replace(
                        original_posting, amount=Amount(Decimal(0), comm_to_use)
                    ).add_comment(Comment("auto-balanced"))
                return Success(current_tx_copy)
            else:
                return Failure(NoCommoditiesElidedError())

        current_imbalances = {
            c: s for c, s in commodity_sums.items() if s != Decimal(0)
        }
        if len(current_imbalances) == len(actual_elided_postings):
            imbalance_items = list(current_imbalances.items())
            for i, elided_idx in enumerate(elided_postings_indices):
                if i < len(imbalance_items):
                    comm, net_sum = imbalance_items[i]
                    original_posting = current_tx_copy.postings[elided_idx]
                    current_tx_copy.postings[elided_idx] = replace(
                        original_posting,
                        amount=Amount(quantity=-net_sum, commodity=comm),
                    ).add_comment(Comment("auto-balanced"))
                else:
                    original_posting = current_tx_copy.postings[elided_idx]
                    comm_to_use = (
                        list(commodity_sums.keys())[0]
                        if commodity_sums
                        else Commodity("USD")
                    )
                    current_tx_copy.postings[elided_idx] = replace(
                        original_posting,
                        amount=Amount(quantity=Decimal(0), commodity=comm_to_use),
                    ).add_comment(Comment("auto-balanced"))
            return Success(current_tx_copy)

        if commodity_sums:
            if len(current_imbalances) == 1:
                return Failure(
                    AmbiguousElidedAmountError(list(current_imbalances.keys())[0])
                )
            elif len(current_imbalances) > 1:
                return Failure(
                    MultipleCommoditiesRemainingError(
                        list(current_imbalances.keys())
                    )
                )

        if actual_elided_postings:
            if commodity_sums:
                if any(s != Decimal(0) for s in commodity_sums.values()):
                    first_imbalanced_comm = next(
                        (c for c, s in commodity_sums.items() if s != Decimal(0)),
                        Commodity("USD"),
                    )
                    return Failure(
                        UnresolvedElidedAmountError(first_imbalanced_comm)
                    )
                else: # All sums zero
                    if len(actual_elided_postings) > 1: # Multiple elided, all sums zero
                         return Failure(
                            AmbiguousElidedAmountError(
                                list(commodity_sums.keys())[0]
                                if commodity_sums
                                else Commodity("USD") # Should have a commodity if sums were calculated
                            )
                        )
            else: # No commodities at all, and elided postings exist
                return Failure(NoCommoditiesElidedError())

        final_imbalances = {
            c: s for c, s in commodity_sums.items() if s != Decimal(0)
        }
        if final_imbalances:
            first_imbalanced_comm = list(final_imbalances.keys())[0]
            return Failure(
                ImbalanceError(
                    first_imbalanced_comm, final_imbalances[first_imbalanced_comm]
                )
            )
        else:
            return Failure(
                TransactionBalanceError(
                    "Internal logic error: Elided postings remain but no imbalances found, and not caught by other specific errors."
                )
            )
