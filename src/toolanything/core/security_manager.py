from __future__ import annotations

from typing import Any, Dict


class SecurityManager:
    def mask_keys_in_log(self, record: Dict[str, Any]) -> Dict[str, Any]:
        masked: Dict[str, Any] = {}
        for key, value in record.items():
            if "key" in key.lower():
                masked[key] = "***MASKED***"
            else:
                masked[key] = value
        return masked

    def audit_call(
        self, tool_name: str, args: Dict[str, Any], user: str | None = None
    ) -> Dict[str, Any]:
        return {
            "tool": tool_name,
            "user": user or "anonymous",
            "args": self.mask_keys_in_log(args),
        }
