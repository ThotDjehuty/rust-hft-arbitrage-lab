# python/strategies/definitions.py
"""
Strategy definitions extracted from notebooks.
Each strategy has parameters, description, and execution logic.
"""

from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class StrategyDefinition:
    """Metadata for a trading strategy."""
    name: str
    display_name: str
    description: str
    parameters: Dict[str, Any]  # parameter name -> default value
    param_descriptions: Dict[str, str]  # parameter name -> description
    requires_multiple_symbols: bool = False
    min_symbols: int = 1


AVAILABLE_STRATEGIES = {
    "triangular_arbitrage": StrategyDefinition(
        name="triangular_arbitrage",
        display_name="Triangular Arbitrage",
        description="Exploit price discrepancies across three currency pairs (e.g., BTC/USD, ETH/USD, ETH/BTC)",
        parameters={
            "symbol_a": "BTC/USD",
            "symbol_b": "ETH/USD",
            "symbol_c": "ETH/BTC",
            "min_profit_bps": 5.0,
            "trade_size_usd": 1000.0,
            "fee_bps": 10.0,
        },
        param_descriptions={
            "symbol_a": "First currency pair",
            "symbol_b": "Second currency pair",
            "symbol_c": "Third currency pair (quote/base of first two)",
            "min_profit_bps": "Minimum profit threshold in basis points",
            "trade_size_usd": "Trade size in USD equivalent",
            "fee_bps": "Trading fees per leg in basis points",
        },
        requires_multiple_symbols=True,
        min_symbols=3,
    ),
    
    "pairs_trading": StrategyDefinition(
        name="pairs_trading",
        display_name="Pairs Trading (Mean Reversion)",
        description="Statistical arbitrage on correlated pairs using z-score of spread",
        parameters={
            "symbol_a": "BTC/USD",
            "symbol_b": "ETH/USD",
            "lookback_periods": 60,
            "z_entry_threshold": 2.0,
            "z_exit_threshold": 0.5,
            "position_size": 1.0,
            "hedge_ratio": 1.0,
        },
        param_descriptions={
            "symbol_a": "First symbol",
            "symbol_b": "Second symbol (correlated)",
            "lookback_periods": "Rolling window for z-score calculation",
            "z_entry_threshold": "Z-score threshold to enter position",
            "z_exit_threshold": "Z-score threshold to exit position",
            "position_size": "Position size in base currency",
            "hedge_ratio": "Hedge ratio (beta) between pairs",
        },
        requires_multiple_symbols=True,
        min_symbols=2,
    ),
    
    "market_making": StrategyDefinition(
        name="market_making",
        display_name="Market Making",
        description="Provide liquidity by quoting bid/ask around mid price with inventory management",
        parameters={
            "symbol": "BTC/USD",
            "spread_bps": 10.0,
            "position_limit": 10.0,
            "inventory_skew_factor": 0.5,
            "quote_size": 1.0,
            "rebalance_threshold": 0.8,
        },
        param_descriptions={
            "symbol": "Trading pair",
            "spread_bps": "Bid-ask spread in basis points",
            "position_limit": "Maximum inventory position",
            "inventory_skew_factor": "How much to skew quotes based on inventory",
            "quote_size": "Size of each quote",
            "rebalance_threshold": "Inventory ratio triggering rebalance",
        },
        requires_multiple_symbols=False,
        min_symbols=1,
    ),
    
    "market_making_imbalance": StrategyDefinition(
        name="market_making_imbalance",
        display_name="Market Making (Order Book Imbalance)",
        description="Market making with order book imbalance prediction for short-term price movement",
        parameters={
            "symbol": "BTC/USD",
            "spread_bps": 8.0,
            "position_limit": 15.0,
            "imbalance_threshold": 0.6,
            "aggressiveness": 1.5,
            "quote_size": 1.0,
        },
        param_descriptions={
            "symbol": "Trading pair",
            "spread_bps": "Base bid-ask spread in basis points",
            "position_limit": "Maximum inventory position",
            "imbalance_threshold": "Order book imbalance ratio triggering action",
            "aggressiveness": "How aggressively to skew quotes (multiplier)",
            "quote_size": "Size of each quote",
        },
        requires_multiple_symbols=False,
        min_symbols=1,
    ),
    
    "stat_arb": StrategyDefinition(
        name="stat_arb",
        display_name="Statistical Arbitrage (Multi-Asset)",
        description="Mean reversion strategy on a basket of correlated assets",
        parameters={
            "symbols": ["BTC/USD", "ETH/USD", "BNB/USD"],
            "lookback_periods": 100,
            "z_entry": 2.5,
            "z_exit": 0.3,
            "rebalance_freq": 10,
        },
        param_descriptions={
            "symbols": "List of correlated symbols",
            "lookback_periods": "Rolling window for cointegration",
            "z_entry": "Entry z-score threshold",
            "z_exit": "Exit z-score threshold",
            "rebalance_freq": "Periods between portfolio rebalancing",
        },
        requires_multiple_symbols=True,
        min_symbols=2,
    ),
    
    "hawkes_market_making": StrategyDefinition(
        name="hawkes_market_making",
        display_name="Hawkes Process Market Making",
        description="Market making using Hawkes process to model order flow intensity",
        parameters={
            "symbol": "BTC/USD",
            "base_spread_bps": 5.0,
            "intensity_window": 100,
            "decay_factor": 0.8,
            "position_limit": 20.0,
        },
        param_descriptions={
            "symbol": "Trading pair",
            "base_spread_bps": "Baseline spread in basis points",
            "intensity_window": "Window for intensity estimation",
            "decay_factor": "Hawkes decay parameter",
            "position_limit": "Maximum inventory",
        },
        requires_multiple_symbols=False,
        min_symbols=1,
    ),
    
    "portfolio_hedging": StrategyDefinition(
        name="portfolio_hedging",
        display_name="Dynamic Portfolio Hedging",
        description="Delta hedging and dynamic risk management for multi-asset portfolio",
        parameters={
            "portfolio_symbols": ["BTC/USD", "ETH/USD"],
            "hedge_symbol": "BTC/USD",
            "rehedge_threshold": 0.1,
            "target_delta": 0.0,
            "lookback_periods": 30,
        },
        param_descriptions={
            "portfolio_symbols": "Portfolio constituents",
            "hedge_symbol": "Hedging instrument",
            "rehedge_threshold": "Delta deviation triggering rehedge",
            "target_delta": "Target portfolio delta",
            "lookback_periods": "Window for beta/correlation estimation",
        },
        requires_multiple_symbols=True,
        min_symbols=2,
    ),
}
