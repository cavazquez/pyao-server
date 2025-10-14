#!/bin/bash
set -e

echo "📦 Tool versions:"
echo "  Python: $(uv run python --version)"
echo "  uv: $(uv --version)"
echo "  ruff: $(uv run ruff --version)"
echo "  mypy: $(uv run mypy --version)"
echo "  pytest: $(uv run pytest --version)"
echo ""

echo "🔍 Running ruff linter..."
uv run ruff check .

echo ""
echo "🎨 Running ruff formatter..."
uv run ruff format --check .

echo ""
echo "🔬 Running mypy type checker..."
uv run mypy .

echo ""
echo "🧪 Running unit tests..."
uv run pytest
echo ""
echo "✅ All checks passed!"
