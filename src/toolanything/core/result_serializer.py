from __future__ import annotations

from typing import Any, Dict


class ResultSerializer:
    def to_openai(self, result: Any) -> Dict[str, Any]:
        if isinstance(result, dict):
            return {"type": "json", "content": result}
        if isinstance(result, (list, tuple)):
            return {"type": "json", "content": list(result)}
        return {"type": "text", "content": str(result)}

    def to_mcp(self, result: Any) -> Dict[str, Any]:
        if isinstance(result, dict):
            return {"contentType": "application/json", "content": result}
        if isinstance(result, (list, tuple)):
            return {"contentType": "application/json", "content": list(result)}
        return {"contentType": "text/plain", "content": str(result)}
