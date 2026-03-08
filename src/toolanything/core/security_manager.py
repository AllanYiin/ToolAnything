from __future__ import annotations

import re
from typing import Any, Dict


class SecurityManager:
    MASK = "***MASKED***"
    _EXACT_SENSITIVE_KEYS = {
        "apikey",
        "api_key",
        "accesskey",
        "access_key",
        "authorization",
        "auth",
        "clientsecret",
        "client_secret",
        "cookie",
        "password",
        "passwd",
        "privatekey",
        "private_key",
        "refreshtoken",
        "refresh_token",
        "secret",
        "sessionid",
        "session_id",
        "token",
    }
    _SENSITIVE_SUFFIXES = (
        "authorization",
        "cookie",
        "key",
        "password",
        "secret",
        "session",
        "sessionid",
        "token",
    )

    @classmethod
    def _normalize_key(cls, key: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", key.lower())

    @classmethod
    def _is_sensitive_key(cls, key: str) -> bool:
        normalized = cls._normalize_key(key)
        if normalized in cls._EXACT_SENSITIVE_KEYS:
            return True
        return any(normalized.endswith(suffix) for suffix in cls._SENSITIVE_SUFFIXES)

    def _mask_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return self.mask_keys_in_log(value)
        if isinstance(value, list):
            return [self._mask_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._mask_value(item) for item in value)
        return value

    def mask_keys_in_log(self, record: Dict[str, Any]) -> Dict[str, Any]:
        masked: Dict[str, Any] = {}
        for key, value in record.items():
            if self._is_sensitive_key(key):
                masked[key] = self.MASK
            else:
                masked[key] = self._mask_value(value)
        return masked

    def audit_call(
        self, tool_name: str, args: Dict[str, Any], user: str | None = None
    ) -> Dict[str, Any]:
        return {
            "tool": tool_name,
            "user": user or "anonymous",
            "args": self.mask_keys_in_log(args),
        }
