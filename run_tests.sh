#!/bin/bash
set -e

echo "📦 Tool versions:"
echo "  Python: $(uv run python --version)"
echo "  uv: $(uv --version)"
echo "  ruff: $(uv run ruff --version)"
echo "  mypy: $(uv run mypy --version)"
echo "  pytest: $(uv run pytest --version)"
echo ""

echo "🎨 Auto-formatting code..."
uv run ruff format .
uv run ruff check --unsafe-fixes --fix .

echo ""
echo "🧪 Running unit tests..."
uv run pytest tests/

echo ""
echo "🔍 Running ruff linter..."
uv run ruff check src tests

echo ""
echo "🔬 Running mypy type checker..."
uv run mypy src tests

echo ""
echo "✅ All checks passed!"
