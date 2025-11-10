"""
Script pour parcourir tous les notebooks et injecter cellules standards :
- Imports (pandas, numpy, rust_bridge, backtest)
- Connexion aux services Rust (exemple)
- Templates de stratégies (triangular, market making, pair trading)
- Template backtest run & visualisation

Exécuter depuis la racine du repo :
python scripts/enrich_notebooks.py --dry-run
"""
import nbformat
import os
import argparse

BASE_CELL_HEADER = """# En-tête ajouté automatiquement : imports et configuration
import json
import pandas as pd
import numpy as np
from python.rust_bridge import parse_orderbook, compute_triangular_opportunity, start_ws
from python.backtest.core import Backtest, sharpe_ratio, max_drawdown
"""

CELL_CONNECT_RUST = """# Connexion Rust (WebSocket example)
# Remplacez l'URL par celle de l'exchange ou du service
try:
    start_ws("wss://example.exchange/ws")
    print("Rust WS démarré en arrière-plan (vérifier logs).")
except Exception as e:
    print("Erreur démarage WS Rust :", e)
"""

CELL_STRATEGY_TRI = """# Stratégie Triangular (template)
# Entrée: trois orderbooks normalisés (ob1, ob2, ob3)
# Utilise compute_triangular_opportunity du module Rust pour calcul math/performant
def triangular_strategy(ob1_json, ob2_json, ob3_json):
    ob1 = parse_orderbook(ob1_json)
    ob2 = parse_orderbook(ob2_json)
    ob3 = parse_orderbook(ob3_json)
    profit, route = compute_triangular_opportunity(ob1, ob2, ob3)
    return profit, route
"""

CELL_BACKTEST_RUN = """# Backtest example
bt = Backtest(initial_cash=100000)
# Exemple d'execution : (timestamp, symbol, qty, price, side)
bt.execute_trade('2025-01-01', 'BTC-USD', 0.1, 30000, 'buy')
df = bt.results_df()
print(df.tail())
print('Sharpe:', sharpe_ratio(df['returns']))
print('Max Drawdown:', max_drawdown(df['equity'] if 'equity' in df else df['equity']))
"""

def find_notebooks(root='.'):
    nbs = []
    for dirpath, dirs, files in os.walk(root):
        for f in files:
            if f.endswith('.ipynb'):
                nbs.append(os.path.join(dirpath, f))
    return nbs

def inject_cells(nb_path, dry_run=True):
    nb = nbformat.read(nb_path, as_version=4)
    # check if already injected by searching a marker
    joined = "\n".join(c.get('source','') for c in nb['cells'][:3])
    if 'En-tête ajouté automatiquement' in joined:
        print(f"Skipped (already enriched): {nb_path}")
        return False
    new_cells = [
        nbformat.v4.new_code_cell(BASE_CELL_HEADER),
        nbformat.v4.new_code_cell(CELL_CONNECT_RUST),
        nbformat.v4.new_code_cell(CELL_STRATEGY_TRI),
        nbformat.v4.new_code_cell(CELL_BACKTEST_RUN),
    ]
    nb['cells'] = new_cells + nb['cells']
    if dry_run:
        print(f"Would inject into {nb_path}")
        return True
    nbformat.write(nb, nb_path)
    print(f"Injected into {nb_path}")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    nbs = find_notebooks(args.root)
    print(f"Found {len(nbs)} notebooks")
    for n in nbs:
        inject_cells(n, dry_run=args.dry_run)

if __name__ == "__main__":
    main()