class Backtest:
    def __init__(self, adapter, initial_cash=100000):
        self.adapter=adapter; self.cash=initial_cash; self.positions={}; self.trades=[]
    def run(self, strategy, market_data):
        for ts,row in market_data.iterrows():
            orders = strategy.on_bar(ts,row,self)
            for o in orders:
                fill=self.adapter.send_market_order(o['symbol'], o['qty']); self.trades.append(fill)
        return {'n_trades':len(self.trades),'cash':self.cash}
