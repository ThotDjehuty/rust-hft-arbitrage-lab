import numpy as np
import pandas as pd
import plotly.graph_objects as go

class Backtest:
    def __init__(self, initial_cash=100000.0):
        self.cash = initial_cash
        self.positions = {}  # symbol -> (qty, avg_price)
        self.trades = []     # records of trades
        self.history = []    # pnl history points (timestamp, equity)

    def execute_trade(self, timestamp, symbol, qty, price, side):
        cost = qty * price
        if side.lower() == 'buy':
            self.cash -= cost
            prev = self.positions.get(symbol, (0.0, 0.0))
            new_qty = prev[0] + qty
            new_avg = (prev[0]*prev[1] + qty*price) / (new_qty if new_qty!=0 else 1)
            self.positions[symbol] = (new_qty, new_avg)
        else:
            # sell
            self.cash += cost
            prev = self.positions.get(symbol, (0.0, 0.0))
            new_qty = prev[0] - qty
            if new_qty <= 0:
                self.positions.pop(symbol, None)
            else:
                self.positions[symbol] = (new_qty, prev[1])
        self.trades.append({"ts": timestamp, "symbol": symbol, "qty": qty, "price": price, "side": side})
        self.record_snapshot(timestamp, price)

    def mark_to_market(self, timestamp, market_prices: dict):
        equity = self.cash
        for s,(qty,avg) in self.positions.items():
            price = market_prices.get(s, avg)
            equity += qty*price
        self.history.append((timestamp, equity))
        return equity

    def record_snapshot(self, timestamp, sample_price=0.0):
        # Quick equity snapshot after trade
        mp = {s: p for s,(p,q) in [(s,(sample_price,0)) for s in self.positions.keys()]} if self.positions else {}
        self.mark_to_market(timestamp, mp)

    def results_df(self):
        df = pd.DataFrame(self.history, columns=["ts", "equity"]).set_index("ts")
        df["returns"] = df["equity"].pct_change().fillna(0.0)
        df["cum_return"] = (1 + df["returns"]).cumprod() - 1
        return df

def sharpe_ratio(returns, freq=252):
    # returns: series of simple returns
    if len(returns) < 2:
        return 0.0
    mu = returns.mean() * freq
    sigma = returns.std() * np.sqrt(freq)
    return mu / sigma if sigma != 0 else 0.0

def max_drawdown(equity_curve):
    roll_max = equity_curve.cummax()
    drawdown = (equity_curve - roll_max) / roll_max
    return drawdown.min()