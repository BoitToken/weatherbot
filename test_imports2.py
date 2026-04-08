#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

tests = [
    ("InternalArbScanner", "src.strategies.internal_arb", "InternalArbScanner"),
    ("OrderbookChecker", "src.execution.orderbook", "OrderbookChecker"),
    ("EdgeMonitor", "src.execution.edge_monitor", "EdgeMonitor"),
]

for label, module, attr in tests:
    try:
        mod = __import__(module, fromlist=[attr])
        obj = getattr(mod, attr)
        print(f"  {label}: OK")
    except Exception as e:
        print(f"  {label}: FAIL - {e}")
