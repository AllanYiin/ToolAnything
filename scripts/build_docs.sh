#!/usr/bin/env bash
set -euo pipefail

# 預留文件建置流程
if [ -d "docs" ]; then
  mkdocs build
else
  echo "No docs directory. Skipping."
fi
