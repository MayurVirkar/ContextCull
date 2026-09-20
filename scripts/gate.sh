#!/usr/bin/env bash
# ContextForge Comprehensive Quality, Security, and Correctness Gate
set -euo pipefail

echo "================================================================="
echo "  ContextForge Quality & Security Gate"
echo "================================================================="

echo -e "\n[1/6] Checking Code Formatting (Ruff)..."
uv run ruff format --check src tests bench

echo -e "\n[2/6] Running Linting & Code Quality (Ruff)..."
uv run ruff check src tests bench

echo -e "\n[3/6] Running Static Type Checking (Pyright)..."
uv run pyright

echo -e "\n[4/6] Running AST Security Analysis (Bandit)..."
uv run bandit -c pyproject.toml -r src/

echo -e "\n[5/6] Running Supply-Chain Security Audit (pip-audit)..."
uv export --no-dev --no-emit-project | uv run pip-audit -r /dev/stdin

echo -e "\n[6/6] Running Test Suite & Coverage Gate (Pytest >= 80%)..."
uv run pytest --cov=tep --cov-report=term-missing

echo -e "\n================================================================="
echo "  ✓ All Quality, Security, and Correctness Gates Passed!"
echo "================================================================="
