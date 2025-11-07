# rust-hft-arbitrage-lab

## 📌 Objectif
Laboratoire d’arbitrage haute fréquence combinant Rust (moteur) et Python (stratégies).

## 🧩 Composants
- `rust_core/` : moteur d’arbitrage, matching engine en Rust
- `rust_python_bindings/` : bindings PyO3 exposés à Python via `maturin`
- `examples/notebooks/` : stratégies en Python avec backtesting et visualisation
- `docker/` : environnement reproductible avec Docker Compose
- `.github/workflows/` : CI/CD pour build/test/package

## 🚀 Lancer le projet
```bash
docker-compose up --build
```

## 🧪 Stratégies incluses
- 📈 Triangular Arbitrage
- 🪙 Market Making

## 📚 Références scientifiques
- Marcos López de Prado – *Advances in Financial ML*
- Rama Cont – *Financial Modelling*
- Jim Gatheral – *The Volatility Surface*
- Bacry et al. – *Hawkes Processes in Finance*
- Cartea & Jaimungal – *Algorithmic and High-Frequency Trading*
