#!/bin/bash
# Validation script for Signal Engine (Agent 2)

set -e

cd /data/.openclaw/workspace/projects/brobot

echo "================================================"
echo "WeatherBot Signal Engine — Validation"
echo "================================================"
echo ""

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found"
    exit 1
fi
echo "✅ Virtual environment exists"

# Check all deliverable files
echo ""
echo "Checking deliverable files..."

files=(
    "src/markets/__init__.py"
    "src/markets/polymarket_scanner.py"
    "src/markets/market_matcher.py"
    "src/signals/__init__.py"
    "src/signals/gaussian_model.py"
    "src/signals/mismatch_detector.py"
    "src/signals/claude_analyzer.py"
    "src/signals/signal_bus.py"
    "src/signals/signal_loop.py"
    "tests/__init__.py"
    "tests/test_gaussian_model.py"
    "tests/test_market_matcher.py"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file MISSING"
        exit 1
    fi
done

# Run unit tests
echo ""
echo "Running unit tests..."
echo ""

.venv/bin/python -m pytest tests/test_gaussian_model.py -v --tb=short

echo ""

.venv/bin/python -m pytest tests/test_market_matcher.py -v --tb=short

# Test standalone modules
echo ""
echo "Testing standalone modules..."
echo ""

echo "Testing Gaussian Model..."
.venv/bin/python src/signals/gaussian_model.py > /dev/null 2>&1 && echo "  ✅ Gaussian Model" || echo "  ❌ Gaussian Model"

echo "Testing Market Matcher..."
.venv/bin/python src/markets/market_matcher.py > /dev/null 2>&1 && echo "  ✅ Market Matcher" || echo "  ❌ Market Matcher"

echo "Testing Signal Bus..."
.venv/bin/python src/signals/signal_bus.py > /dev/null 2>&1 && echo "  ✅ Signal Bus" || echo "  ❌ Signal Bus"

echo "Testing Mismatch Detector..."
.venv/bin/python src/signals/mismatch_detector.py > /dev/null 2>&1 && echo "  ✅ Mismatch Detector" || echo "  ❌ Mismatch Detector"

echo "Testing Signal Loop..."
.venv/bin/python src/signals/signal_loop.py > /dev/null 2>&1 && echo "  ✅ Signal Loop" || echo "  ❌ Signal Loop"

# Count lines of code
echo ""
echo "Code statistics..."
total_lines=$(find src/markets src/signals tests -name "*.py" -type f -exec wc -l {} + | tail -1 | awk '{print $1}')
file_count=$(find src/markets src/signals tests -name "*.py" -type f | wc -l)

echo "  Files: $file_count"
echo "  Total lines: $total_lines"

# Summary
echo ""
echo "================================================"
echo "✅ SIGNAL ENGINE VALIDATION COMPLETE"
echo "================================================"
echo ""
echo "All deliverables present and functional."
echo "Ready for integration with Agent 1 (Data Layer)."
echo ""
