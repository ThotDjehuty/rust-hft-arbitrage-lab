from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import os, json, random, time, asyncio
app = FastAPI(title="Mock Crypto Market APIs")
DATA_DIR = "/data"
def load_json(name: str):
    with open(os.path.join(DATA_DIR, name), "r") as f:
        return json.load(f)
@app.get("/health")
def health(): return {"status": "ok", "ts": int(time.time())}
@app.get("/api/{exchange}/ticker")
async def ticker(exchange: str):
    try: data = load_json(f"{exchange}.json")
    except Exception: return JSONResponse({"error":"unknown exchange"}, status_code=404)
    out = {"exchange": exchange, "timestamp": int(time.time()), "symbols": []}
    for s in data.get("symbols", []):
        p = round(s.get("price", 0.0) * (1 + random.uniform(-0.001,0.001)), 8)
        out["symbols"].append({"pair": s["pair"], "price": p})
    return out
@app.get("/api/{exchange}/orderbook/{symbol}")
async def orderbook(exchange: str, symbol: str, depth: int = 20, latency_ms: int = 0):
    if latency_ms: await asyncio.sleep(latency_ms/1000.0)
    try: data = load_json(f"{exchange}.json")
    except Exception: return JSONResponse({"error":"unknown exchange"}, status_code=404)
    base_price = data.get("symbols", [])[0]["price"]
    bids = [[round(base_price - i*0.01, 8), round(random.uniform(0.1,5.0),8)] for i in range(1, depth+1)]
    asks = [[round(base_price + i*0.01, 8), round(random.uniform(0.1,5.0),8)] for i in range(1, depth+1)]
    return {"exchange": exchange, "symbol": symbol, "bids": bids, "asks": asks, "depth": depth}
@app.get("/api/{exchange}/mock_trades/{symbol}")
async def mock_trades(exchange: str, symbol: str, n: int = 200):
    trades = []; px = 68000.0
    for i in range(n):
        px += random.uniform(-5,5)
        trades.append({"time": int(time.time()) - i, "price": px, "qty": round(random.uniform(0.01, 2.0), 4), "side": random.choice(["buy","sell"])})
    return {"exchange": exchange, "symbol": symbol, "trades": trades}
@app.websocket("/ws/orderbook/{exchange}/{symbol}")
async def ws_orderbook(ws: WebSocket, exchange: str, symbol: str, depth: int = 20, interval_ms: int = 1000):
    await ws.accept()
    try:
        while True:
            try:
                data = load_json(f"{exchange}.json"); base_price = data.get("symbols", [])[0]["price"]
            except Exception: base_price = 100.0
            bids = [[round(base_price - i*0.01, 8), round(random.uniform(0.1,5.0),8)] for i in range(1, depth+1)]
            asks = [[round(base_price + i*0.01, 8), round(random.uniform(0.1,5.0),8)] for i in range(1, depth+1)]
            await ws.send_json({"exchange": exchange, "symbol": symbol, "bids": bids, "asks": asks, "ts": int(time.time()*1000)})
            await asyncio.sleep(interval_ms/1000.0)
    except WebSocketDisconnect:
        return
