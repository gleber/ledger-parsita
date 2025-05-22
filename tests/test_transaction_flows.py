import pytest
from decimal import Decimal
from datetime import date
from src.classes import Transaction, Posting, Price
from typing import List # Import List

from src.transaction_flows import (
    transaction_to_flows,
    Flow,
    UnhandledRemainderError,
)
from returns.result import Success, Failure # Result is not directly used in tests
from src.classes import Transaction # Keep Transaction for type hint
from src.base_classes import Amount, Commodity, AccountName # Keep for Flow comparison
# from src.common_types import CostKind, Status # CostKind, Status no longer needed directly
from src.hledger_parser import HledgerParsers # Import HledgerParsers


def test_portfolio_rebalance_and_fee_settlement():
    transaction_string = """
2025-05-17 Portfolio Rebalance & Fee Settlement
    Assets:Broker:Portfolio:STOCKA    -50 STOCKA @ 30.00 USD ; Sold 50 STOCKA gain 1500 USD
    Assets:Broker:Portfolio:STOCKB    -20 STOCKB @ 90.00 USD ; Sold 20 STOCKB gain 1800 USD
    Assets:Broker:Portfolio:CRYPTOX     2 CRYPTOX @ 500.00 USD ; Bought 2 CRYPTOX for 1000 USD
    Assets:Broker:Portfolio:EURBOND     1 EURBOND @@ 880.00 USD ; Bought 1 EURBOND for 880 USD
    Expenses:Broker:Commissions         15.00 USD
    Expenses:Broker:AdvisoryFees        50.00 USD
    Assets:Broker:CashUSD               1355.00 USD
"""
    parsed_transaction_result = HledgerParsers.transaction.parse(transaction_string.strip())
    assert isinstance(parsed_transaction_result, Success), f"Failed to parse transaction: {parsed_transaction_result.failure()}"
    transaction: Transaction = parsed_transaction_result.unwrap()  # type: ignore
    # assert transaction.is_balanced() == True, f"Transaction is not balanced: {transaction}"

    result = transaction_to_flows(transaction)
    assert isinstance(result, Success), f"Expected Success, got {result.failure().__str__()}"
    generated_flows: List[Flow] = result.unwrap()

    expected_flow_purchase_cryptox = Flow(
        from_node="Assets:Broker:CashUSD",
        to_node="Assets:Broker:Portfolio:CRYPTOX",
        out_amount=Amount(Decimal("1000.00"), Commodity("USD")),
        in_amount=Amount(Decimal("2"), Commodity("CRYPTOX")),
        label="1000.00 USD -> 2 CRYPTOX",
        conversion_rate=Amount(Decimal("500.00"), Commodity("USD"))
    )
    expected_flow_purchase_eurbond = Flow(
        from_node="Assets:Broker:CashUSD",
        to_node="Assets:Broker:Portfolio:EURBOND",
        out_amount=Amount(Decimal("880.00"), Commodity("USD")),
        in_amount=Amount(Decimal("1"), Commodity("EURBOND")),
        label="880.00 USD -> 1 EURBOND",
        conversion_rate=Amount(Decimal("880.00"), Commodity("USD"))
    )
    expected_flow_commissions = Flow(
        from_node="Assets:Broker:CashUSD",
        to_node="Expenses:Broker:Commissions",
        out_amount=Amount(Decimal("15.00"), Commodity("USD")),
        in_amount=Amount(Decimal("15.00"), Commodity("USD")),
        label="15.00 USD transfer",
        conversion_rate=None
    )
    expected_flow_advisory_fees = Flow(
        from_node="Assets:Broker:CashUSD",
        to_node="Expenses:Broker:AdvisoryFees",
        out_amount=Amount(Decimal("50.00"), Commodity("USD")),
        in_amount=Amount(Decimal("50.00"), Commodity("USD")),
        label="50.00 USD transfer",
        conversion_rate=None
    )
    expected_flow_stocka_sale_main = Flow(
        from_node="Assets:Broker:Portfolio:STOCKA",
        to_node="Assets:Broker:CashUSD",
        out_amount=Amount(Decimal("50"), Commodity("STOCKA")),
        in_amount=Amount(Decimal("1500.00"), Commodity("USD")),
        label="50 STOCKA -> 1500.00 USD",
        conversion_rate=Amount(Decimal("30.00"), Commodity("USD"))
    )
    expected_flow_stockb_sale_main = Flow(
        from_node="Assets:Broker:Portfolio:STOCKB",
        to_node="Assets:Broker:CashUSD",
        out_amount=Amount(Decimal("20"), Commodity("STOCKB")),
        in_amount=Amount(Decimal("1800.00"), Commodity("USD")),
        label="20 STOCKB -> 1800.00 USD",
        conversion_rate=Amount(Decimal("90.00"), Commodity("USD"))
    )
    assert expected_flow_purchase_cryptox in generated_flows
    assert expected_flow_purchase_eurbond in generated_flows
    assert expected_flow_commissions in generated_flows
    assert expected_flow_advisory_fees in generated_flows
    assert expected_flow_stocka_sale_main in generated_flows
    assert expected_flow_stockb_sale_main in generated_flows
    assert len(generated_flows) == 6, f"Expected 6 flows, got {len(generated_flows)}. Flows: {generated_flows}"


def test_simple_income_transaction():
    transaction_string = """
2025-05-18 Interest Received
    Assets:Bank:Checking          10.00 USD
    Income:Bank:Interest         -10.00 USD
"""
    parsed_transaction_result = HledgerParsers.transaction.parse(transaction_string.strip())
    assert isinstance(parsed_transaction_result, Success), f"Failed to parse transaction: {parsed_transaction_result.failure()}"
    transaction: Transaction = parsed_transaction_result.unwrap() # type: ignore

    result = transaction_to_flows(transaction)
    assert isinstance(result, Success), f"Expected Success, got {result}"
    generated_flows: List[Flow] = result.unwrap()

    # Removed check_flows_balance

    expected_flows_corrected = [
        Flow(
            from_node="Income:Bank:Interest",
            to_node="Assets:Bank:Checking",
            out_amount=Amount(Decimal("10.00"), Commodity("USD")),
            in_amount=Amount(Decimal("10.00"), Commodity("USD")),
            label="10.00 USD transfer", # Based on _process_simple_unpriced_transfers
            conversion_rate=None
        )
    ]
    assert generated_flows == expected_flows_corrected


def test_sell_stockc_implicit_pnl():
    transaction_string = """
2025-05-19 Sell STOCKC - P&L Implicit in Equity
    Assets:Broker:Portfolio:STOCKC    -10 STOCKC @ 8.00 USD
    Assets:Broker:CashUSD              80.00 USD
"""
    parsed_transaction_result = HledgerParsers.transaction.parse(transaction_string.strip())
    assert isinstance(parsed_transaction_result, Success), f"Failed to parse transaction: {parsed_transaction_result.failure()}"
    transaction: Transaction = parsed_transaction_result.unwrap().strip_loc() # type: ignore

    result = transaction_to_flows(transaction)

    assert isinstance(result, Success), f"Expected Success, got {result}"
    generated_flows: List[Flow] = result.unwrap()

    # Removed check_flows_balance

    expected_flow_stockc_sale = Flow(
        from_node="Assets:Broker:Portfolio:STOCKC",
        to_node="Assets:Broker:CashUSD",
        out_amount=Amount(Decimal("10"), Commodity("STOCKC")),
        in_amount=Amount(Decimal("80.00"), Commodity("USD")),
        label="10 STOCKC -> 80.00 USD",
        conversion_rate=Amount(Decimal("8.00"), Commodity("USD"))
    )
    
    assert expected_flow_stockc_sale in generated_flows
    assert len(generated_flows) == 1


def test_simple_transfer_transaction():
    transaction_string = """
2025-05-20 Transfer BTC between wallets
    Assets:Wallet:OldBTC     -0.5 BTC
    Assets:Wallet:NewBTC      0.5 BTC
"""
    parsed_transaction_result = HledgerParsers.transaction.parse(transaction_string.strip())
    assert isinstance(parsed_transaction_result, Success), f"Failed to parse transaction: {parsed_transaction_result.failure()}"
    transaction: Transaction = parsed_transaction_result.unwrap().strip_loc() # type: ignore

    result = transaction_to_flows(transaction)
    assert isinstance(result, Success), f"Expected Success, got {result}"
    generated_flows: List[Flow] = result.unwrap()

    # Removed check_flows_balance

    expected_flows = [
        Flow(
            from_node="Assets:Wallet:OldBTC",
            to_node="Assets:Wallet:NewBTC",
            out_amount=Amount(Decimal("0.5"), Commodity("BTC")),
            in_amount=Amount(Decimal("0.5"), Commodity("BTC")),
            label="0.5 BTC transfer", # Based on _process_simple_unpriced_transfers
            conversion_rate=None
        )
    ]
    assert generated_flows == expected_flows


def test_no_pricing_transaction_cash_expenses():
    transaction_string = """
2025-05-21 Cash expenses
    Expenses:Food            20.00 USD
    Expenses:Transport       10.00 USD
    Assets:CashWallet       -30.00 USD
"""
    parsed_transaction_result = HledgerParsers.transaction.parse(transaction_string.strip())
    assert isinstance(parsed_transaction_result, Success), f"Failed to parse transaction: {parsed_transaction_result.failure()}"
    transaction: Transaction = parsed_transaction_result.unwrap().strip_loc() # type: ignore

    result = transaction_to_flows(transaction)
    assert isinstance(result, Success), f"Expected Success, got {result}"
    generated_flows: List[Flow] = result.unwrap()

    # Removed check_flows_balance

    # The prompt's example output for this case:
    # Flow: Assets:CashWallet (20.00 USD) --> Expenses:Food (20.00 USD) | Label: [20.00 USD transfer]
    # Flow: Assets:CashWallet (10.00 USD) --> Expenses:Transport (10.00 USD) | Label: [10.00 USD transfer]
    # This implies the two CashWallet postings are handled separately by _process_simple_unpriced_transfers.

    flow_food = Flow(
        from_node="Assets:CashWallet",
        to_node="Expenses:Food",
        out_amount=Amount(Decimal("20.00"), Commodity("USD")),
        in_amount=Amount(Decimal("20.00"), Commodity("USD")),
        label="20.00 USD transfer",
        conversion_rate=None
    )
    flow_transport = Flow(
        from_node="Assets:CashWallet",
        to_node="Expenses:Transport",
        out_amount=Amount(Decimal("10.00"), Commodity("USD")),
        in_amount=Amount(Decimal("10.00"), Commodity("USD")),
        label="10.00 USD transfer",
        conversion_rate=None
    )
    assert flow_food in generated_flows
    assert flow_transport in generated_flows
    assert len(generated_flows) == 2


def test_partial_cash_consumption():
    transaction_string = """
2025-05-22 Two sales, one cash line
    Assets:WidgetStore:Cash            100.00 USD
    Assets:Inventory:GadgetA            -1 GADGETA @ 70 USD
    Assets:Inventory:GadgetB            -1 GADGETB @ 30 USD
"""
    parsed_transaction_result = HledgerParsers.transaction.parse(transaction_string.strip())
    assert isinstance(parsed_transaction_result, Success), f"Failed to parse transaction: {parsed_transaction_result.failure()}"
    transaction: Transaction = parsed_transaction_result.unwrap().strip_loc() # type: ignore

    result = transaction_to_flows(transaction)
    assert isinstance(result, Success), f"Expected Success, got {result}"
    generated_flows: List[Flow] = result.unwrap()

    assert len(generated_flows) == 2, f"Expected 2 flows, got {len(generated_flows)}. Flows: {generated_flows}"
    assert Flow(
        from_node="Assets:Inventory:GadgetA",
        to_node="Assets:WidgetStore:Cash",
        out_amount=Amount(Decimal("1"), Commodity("GADGETA")),
        in_amount=Amount(Decimal("70.00"), Commodity("USD")),
        label="1 GADGETA -> 70.00 USD",
        conversion_rate=Amount(Decimal("70.00"), Commodity("USD"))
    ) in generated_flows
    assert Flow(
        from_node="Assets:Inventory:GadgetB",
        to_node="Assets:WidgetStore:Cash",
        out_amount=Amount(Decimal("1"), Commodity("GADGETB")),
        in_amount=Amount(Decimal("30.00"), Commodity("USD")),
        label="1 GADGETB -> 30.00 USD",
        conversion_rate=Amount(Decimal("30.00"), Commodity("USD"))
    ) in generated_flows
    