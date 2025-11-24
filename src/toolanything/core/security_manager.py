from __future__ import annotations

from typing import Any


class SecurityManager:
    def mask_keys_in_log(self, record: dict) -> dict:
        masked = {}
        for key, value in record.items():
            if "key" in key.lower():
                masked[key] = "***MASKED***"
            else:
                masked[key] = value
        return masked

    def audit_call(self, tool_name: str, args: dict, user: str | None = None) -> dict[str, Any]:
        return {
            "tool": tool_name,
            "user": user or "anonymous",
            "args": self.mask_keys_in_log(args),
        }
