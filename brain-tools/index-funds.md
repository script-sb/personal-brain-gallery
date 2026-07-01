# Index Fund Module

The index fund module provides educational portfolio templates and due-diligence helpers. It does not place trades and does not replace personalized financial advice.

Commands:

```bash
python3 -m brain_core funds profile --years 10 --risk 3
python3 -m brain_core funds template --profile balanced
python3 -m brain_core funds score --expense-ratio 0.03 --tracking-error 0.02 --assets-under-management 10000 --broad --liquid
python3 -m brain_core funds rebalance --profile balanced --stock 70 --bond 25 --cash 5
```

Principles:

- Use broad diversification for core holdings.
- Keep costs low; expense ratio is one of the few controllable variables.
- Match allocation to time horizon and risk tolerance.
- Rebalance periodically or when drift is material.
- Consider taxes, account type, and transaction costs before trading.
