# python/strategies/executor.py
"""
Strategy executor with live and backtest modes.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """Configuration for strategy execution."""
    strategy_name: str
    parameters: Dict[str, Any]
    mode: str = "backtest"  # "backtest" or "live"
    initial_capital: float = 100000.0


class StrategyExecutor:
    """
    Executes trading strategies in backtest or live mode.
    """
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.cash = config.initial_capital
        self.positions = {}  # symbol -> (qty, avg_price)
        self.trades = []
        self.equity_history = []
        self.current_time = None
        
    def execute_trade(self, symbol: str, qty: float, price: float, side: str, timestamp: Optional[datetime] = None):
        """Execute a trade and update portfolio."""
        if timestamp is None:
            timestamp = datetime.now()
        
        cost = abs(qty) * price
        
        if side.lower() == 'buy':
            if cost > self.cash:
                logger.warning(f"Insufficient cash for {symbol} buy: need {cost}, have {self.cash}")
                return False
            
            self.cash -= cost
            prev_qty, prev_avg = self.positions.get(symbol, (0.0, 0.0))
            new_qty = prev_qty + qty
            new_avg = (prev_qty * prev_avg + qty * price) / new_qty if new_qty != 0 else price
            self.positions[symbol] = (new_qty, new_avg)
            
        elif side.lower() == 'sell':
            prev_qty, prev_avg = self.positions.get(symbol, (0.0, 0.0))
            if prev_qty < qty:
                logger.warning(f"Insufficient position for {symbol} sell: need {qty}, have {prev_qty}")
                return False
            
            self.cash += cost
            new_qty = prev_qty - qty
            if new_qty <= 1e-8:
                self.positions.pop(symbol, None)
            else:
                self.positions[symbol] = (new_qty, prev_avg)
        
        # Record trade
        self.trades.append({
            "timestamp": timestamp,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "value": cost,
        })
        
        return True
    
    def mark_to_market(self, market_prices: Dict[str, float], timestamp: Optional[datetime] = None):
        """Calculate current equity value."""
        if timestamp is None:
            timestamp = datetime.now()
        
        equity = self.cash
        for symbol, (qty, avg_price) in self.positions.items():
            current_price = market_prices.get(symbol, avg_price)
            equity += qty * current_price
        
        self.equity_history.append({
            "timestamp": timestamp,
            "equity": equity,
            "cash": self.cash,
            "positions_value": equity - self.cash,
        })
        
        return equity
    
    def run_triangular_arbitrage(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """Execute triangular arbitrage strategy."""
        params = self.config.parameters
        symbol_a = params.get("symbol_a", "BTC/USD")
        symbol_b = params.get("symbol_b", "ETH/USD")
        symbol_c = params.get("symbol_c", "ETH/BTC")
        min_profit_bps = params.get("min_profit_bps", 5.0)
        fee_bps = params.get("fee_bps", 10.0)
        trade_size = params.get("trade_size_usd", 1000.0)
        
        # Simple triangular arbitrage logic
        for idx, row in market_data.iterrows():
            timestamp = row.get("timestamp", datetime.now())
            
            # Get mid prices
            price_a = row.get(f"{symbol_a}_mid", 0)
            price_b = row.get(f"{symbol_b}_mid", 0)
            price_c = row.get(f"{symbol_c}_mid", 0)
            
            if price_a == 0 or price_b == 0 or price_c == 0:
                continue
            
            # Calculate implied vs actual
            # A->B->C cycle: Buy A with USD, trade A for B, sell B for USD
            implied_c = price_b / price_a  # How much B per A
            actual_c = price_c
            
            profit_bps = ((implied_c / actual_c) - 1) * 10000
            net_profit_bps = profit_bps - fee_bps * 3  # 3 legs
            
            if net_profit_bps > min_profit_bps:
                # Execute arbitrage cycle
                logger.info(f"Triangular arb opportunity: {net_profit_bps:.2f} bps")
                # Simplified: just record the opportunity
                self.trades.append({
                    "timestamp": timestamp,
                    "type": "triangular_arb",
                    "profit_bps": net_profit_bps,
                    "cycle": f"{symbol_a}->{symbol_b}->{symbol_c}",
                })
            
            # Mark to market
            self.mark_to_market({
                symbol_a: price_a,
                symbol_b: price_b,
                symbol_c: price_c,
            }, timestamp)
        
        return self.get_results()
    
    def run_pairs_trading(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """Execute pairs trading strategy."""
        params = self.config.parameters
        symbol_a = params.get("symbol_a", "BTC/USD")
        symbol_b = params.get("symbol_b", "ETH/USD")
        lookback = params.get("lookback_periods", 60)
        z_entry = params.get("z_entry_threshold", 2.0)
        z_exit = params.get("z_exit_threshold", 0.5)
        position_size = params.get("position_size", 1.0)
        
        position = 0  # -1 (short spread), 0 (flat), +1 (long spread)
        
        for idx in range(lookback, len(market_data)):
            row = market_data.iloc[idx]
            timestamp = row.get("timestamp", datetime.now())
            
            price_a = row.get(f"{symbol_a}_mid", 0)
            price_b = row.get(f"{symbol_b}_mid", 0)
            
            if price_a == 0 or price_b == 0:
                continue
            
            # Calculate spread and z-score
            window = market_data.iloc[idx-lookback:idx]
            spread = window[f"{symbol_a}_mid"] - window[f"{symbol_b}_mid"]
            z_score = (spread.iloc[-1] - spread.mean()) / (spread.std() + 1e-8)
            
            # Trading logic
            if position == 0:
                if z_score > z_entry:
                    # Short spread: sell A, buy B
                    self.execute_trade(symbol_a, position_size, price_a, "sell", timestamp)
                    self.execute_trade(symbol_b, position_size, price_b, "buy", timestamp)
                    position = -1
                elif z_score < -z_entry:
                    # Long spread: buy A, sell B
                    self.execute_trade(symbol_a, position_size, price_a, "buy", timestamp)
                    self.execute_trade(symbol_b, position_size, price_b, "sell", timestamp)
                    position = 1
            else:
                if abs(z_score) < z_exit:
                    # Exit position
                    if position == -1:
                        self.execute_trade(symbol_a, position_size, price_a, "buy", timestamp)
                        self.execute_trade(symbol_b, position_size, price_b, "sell", timestamp)
                    else:
                        self.execute_trade(symbol_a, position_size, price_a, "sell", timestamp)
                        self.execute_trade(symbol_b, position_size, price_b, "buy", timestamp)
                    position = 0
            
            # Mark to market
            self.mark_to_market({symbol_a: price_a, symbol_b: price_b}, timestamp)
        
        return self.get_results()
    
    def run_market_making(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """Execute market making strategy."""
        params = self.config.parameters
        symbol = params.get("symbol", "BTC/USD")
        spread_bps = params.get("spread_bps", 10.0)
        position_limit = params.get("position_limit", 10.0)
        
        for idx, row in market_data.iterrows():
            timestamp = row.get("timestamp", datetime.now())
            mid_price = row.get(f"{symbol}_mid", 0)
            
            if mid_price == 0:
                continue
            
            # Current inventory
            current_qty, _ = self.positions.get(symbol, (0.0, 0.0))
            
            # Quote both sides if within limits
            spread = mid_price * spread_bps / 10000
            
            # Simulate fills (simplified)
            if current_qty < position_limit:
                # Can buy - place bid
                if np.random.random() < 0.1:  # 10% fill probability
                    self.execute_trade(symbol, 0.1, mid_price - spread/2, "buy", timestamp)
            
            if current_qty > -position_limit:
                # Can sell - place ask
                if np.random.random() < 0.1:
                    self.execute_trade(symbol, 0.1, mid_price + spread/2, "sell", timestamp)
            
            self.mark_to_market({symbol: mid_price}, timestamp)
        
        return self.get_results()
    
    def get_results(self) -> Dict[str, Any]:
        """Calculate strategy performance metrics."""
        if not self.equity_history:
            return {
                "total_trades": len(self.trades),
                "final_equity": self.cash,
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
            }
        
        df = pd.DataFrame(self.equity_history)
        df["returns"] = df["equity"].pct_change().fillna(0)
        
        total_return = (df["equity"].iloc[-1] / self.config.initial_capital - 1) * 100
        
        # Sharpe ratio (annualized)
        if len(df["returns"]) > 1:
            sharpe = (df["returns"].mean() / (df["returns"].std() + 1e-8)) * np.sqrt(252)
        else:
            sharpe = 0.0
        
        # Max drawdown
        rolling_max = df["equity"].cummax()
        drawdown = (df["equity"] - rolling_max) / rolling_max
        max_dd = drawdown.min() * 100
        
        return {
            "total_trades": len(self.trades),
            "final_equity": df["equity"].iloc[-1],
            "total_return_pct": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": max_dd,
            "equity_curve": df,
            "trades": pd.DataFrame(self.trades) if self.trades else pd.DataFrame(),
        }
