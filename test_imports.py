#!/usr/bin/env python3
"""Quick import test for all 3 sprints."""
import sys
sys.path.insert(0, '.')

tests = [
    ("PaperTrader", "src.execution.paper_trader", "PaperTrader"),
    ("Settlement", "src.execution.settlement", "settle_trades"),
    ("LearningEngine", "src.learning.improvement", "LearningEngine"),
]

for label, module, attr in tests:
    try:
        mod = __import__(module, fromlist=[attr])
        obj = getattr(mod, attr)
        print(f"  {label}: OK")
    except Exception as e:
        print(f"  {label}: FAIL - {e}")

# Check position_sizer
try:
    from src.execution.position_sizer import get_position_size, calculate_kelly
    print("  PositionSizer: OK")
except Exception as e:
    print(f"  PositionSizer: FAIL - {e}")

# Check SportsSignalLoop
try:
    from src.sports.sports_signal_loop import SportsSignalLoop
    print("  SportsSignalLoop: OK")
except Exception as e:
    print(f"  SportsSignalLoop: FAIL - {e}")

print("\nDone.")
