"""Credential resolver for non-callable sources."""
from __future__ import annotations

import os
from typing import Dict

from ..exceptions import ToolError


class CredentialResolver:
    """解析執行期秘密資料。"""

    def resolve_headers(self, auth_ref: str | None) -> Dict[str, str]:
        if not auth_ref:
            return {}

        if auth_ref.startswith("env:"):
            env_name = auth_ref.split(":", 1)[1]
            value = os.getenv(env_name)
            if not value:
                raise ToolError(
                    f"找不到認證環境變數 {env_name}",
                    error_type="credential_error",
                    data={"auth_ref": auth_ref},
                )
            return {"Authorization": f"Bearer {value}"}

        raise ToolError(
            f"不支援的 auth_ref 類型: {auth_ref}",
            error_type="credential_error",
            data={"auth_ref": auth_ref},
        )


__all__ = ["CredentialResolver"]
