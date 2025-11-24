"""簡易的 docstring 擷取與結構化工具。

專案中的工具與 pipeline 常以函數形式存在，若僅依靠函數名稱或 decorator
中的 `description`，語意上不足以說明「何時使用此工具」、
「有哪些方法或行為」、「輸入輸出格式」等細節。此模組提供一個輕量化
的解析器，能從函數 docstring 擷取可被 LLM 直接消化的提示資訊，供
Tool Calling 與 MCP 描述欄位使用。
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional


@dataclass
class DocMetadata:
    """Docstring 解析後的結構化結果。"""

    raw: str
    summary: str
    usage: Optional[str] = None
    parameters: Dict[str, str] = field(default_factory=dict)
    returns: Optional[str] = None

    def to_prompt_hint(self) -> str:
        """將 metadata 組合成適合描述欄位的提示字串。"""

        parts: list[str] = []
        if self.usage:
            parts.append(f"使用時機：{self.usage}")
        if self.parameters:
            param_desc = "; ".join(
                f"{name}: {desc}" for name, desc in self.parameters.items()
            )
            parts.append(f"參數說明：{param_desc}")
        if self.returns:
            parts.append(f"輸出格式：{self.returns}")
        return " ".join(parts)


_SECTION_HEADERS = {
    "usage": {"usage", "用法", "使用時機"},
    "args": {"args", "parameters", "參數"},
    "returns": {"returns", "return", "輸出", "回傳"},
}


def _match_section(line: str) -> str | None:
    stripped = line.strip()
    header = stripped.split(":", 1)[0].rstrip(":").lower()
    for section, aliases in _SECTION_HEADERS.items():
        if header in aliases:
            return section
    return None


def parse_docstring(func: Callable[..., object]) -> DocMetadata | None:
    """從函數 docstring 擷取用於 Tool 描述的資訊。"""

    raw_doc = inspect.getdoc(func)
    if not raw_doc:
        return None

    summary_lines: list[str] = []
    usage_lines: list[str] = []
    return_lines: list[str] = []
    parameters: Dict[str, str] = {}

    current_section = "summary"
    current_param: str | None = None

    for raw_line in raw_doc.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        matched_section = _match_section(stripped)
        if matched_section:
            current_section = matched_section
            current_param = None
            if ":" in stripped:
                _, remainder = stripped.split(":", 1)
                inline = remainder.strip()
                if inline:
                    if current_section == "usage":
                        usage_lines.append(inline)
                    elif current_section == "returns":
                        return_lines.append(inline)
            continue

        if current_section == "summary":
            summary_lines.append(stripped)
            continue

        if current_section == "usage":
            usage_lines.append(stripped)
            continue

        if current_section == "args":
            if ":" in stripped:
                name, desc = stripped.split(":", 1)
                current_param = name.strip()
                parameters[current_param] = desc.strip()
            elif current_param:
                parameters[current_param] += f" {stripped}"
            continue

        if current_section == "returns":
            return_lines.append(stripped)

    summary = " ".join(summary_lines).strip()
    usage = " ".join(usage_lines).strip() or None
    returns = " ".join(return_lines).strip() or None

    return DocMetadata(
        raw=raw_doc,
        summary=summary,
        usage=usage,
        parameters=parameters,
        returns=returns,
    )
