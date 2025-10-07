#!/bin/bash
set -e

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
uv run pytest -v

echo ""
echo "✅ All checks passed!"
