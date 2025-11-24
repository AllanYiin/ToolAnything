#!/usr/bin/env bash
set -euo pipefail

if command -v ruff >/dev/null 2>&1; then
  ruff check src tests
else
  echo "ruff 未安裝，跳過 lint。"
fi

if command -v black >/dev/null 2>&1; then
  black src tests
else
  echo "black 未安裝，跳過格式化。"
fi
