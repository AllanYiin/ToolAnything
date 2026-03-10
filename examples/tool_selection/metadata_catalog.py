"""Tool selection: 建立含 metadata 的工具目錄。"""
from __future__ import annotations

from .catalog_shared import build_registry, describe_registry


def main() -> None:
    registry = build_registry()
    print("已建立工具目錄：")
    for line in describe_registry(registry):
        print(line)


if __name__ == "__main__":
    main()
