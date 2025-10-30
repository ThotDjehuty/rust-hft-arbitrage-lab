import requests
class SimulatedAdapter:
    def __init__(self, base_url='http://mock_apis:8000', spread_bps=1.0):
        self.base_url=base_url; self.spread_bps=spread_bps
    def send_market_order(self, symbol, qty, exchange='binance'):
        ob=requests.get(f"{self.base_url}/api/{exchange}/orderbook/{symbol}?depth=20").json()
        side='buy' if qty>0 else 'sell'; levels=ob['asks'] if side=='buy' else ob['bids']
        qty_abs=abs(qty); filled=0.0; cost=0.0
        for p,s in levels:
            if qty_abs<=0: break
            take=min(qty_abs,s); filled+=take; cost+=take*p; qty_abs-=take
        return {'filled_qty':filled,'cost':cost,'side':side}
