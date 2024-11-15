# FreqTrade Strategy with Custom Order Algorithm

## Project Structure
```
├── freqtrad strategy/
│   └── user_data/
│       ├── backtest_results/
│       ├── data/
│       ├── freqaimodels/
│       ├── hyperopt_results/
│       ├── hyperopts/
│       ├── logs/
│       ├── notebooks/
│       ├── plot/
│       ├── strategies/
│       ├── config.json
│       ├── hyperopt.lock
│       └── tradesv3.sqlite
├── config.json
├── cross_margin_pairs.json
├── docker-compose.yml
├── ta-lib-0.4.0-src.tar.gz
└── order algo/
    ├── long/
    │   ├── _pycache_/
    │   ├── Dockerfile
    │   ├── main.py
    │   └── utils.py
    └── short/
        ├── _pycache_/
        ├── Dockerfile
        ├── main.py
        ├── requirements.txt
        └── utils.py
```

## System Components

### FreqTrade Strategy
- Custom strategy implementation in `freqtrad strategy/user_data/strategies/`
- Complete backtesting data and results
- Strategy optimization via hyperopt
- FreqAI model integration

### Order Algorithm
Two independent modules for position management:
- Long positions (`order algo/long/`)
- Short positions (`order algo/short/`)
Each with:
  - Custom order execution logic
  - Position sizing and risk management
  - Utils for exchange interaction

## Docker Deployment
- Separate containers for FreqTrade and order algorithms
- Configurations in `docker-compose.yml`
- TA-Lib included for technical analysis

## Risk Management
- Separate long/short position handling
- Cross-margin trading support
- Custom pairs configuration
- Complete transaction logging

## Warning
This system uses advanced trading features including:
- Cross-margin trading
- Long/Short positions
- Custom order execution
Test thoroughly in backtest and paper trading before live deployment.