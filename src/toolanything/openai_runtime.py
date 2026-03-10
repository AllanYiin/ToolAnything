"""OpenAI Chat Completions tool-calling runtime helpers."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Callable, Mapping, Sequence
from urllib import error as url_error
from urllib import request as url_request

from .adapters.openai_adapter import OpenAIAdapter
from .core.failure_log import FailureLogManager
from .core.registry import ToolRegistry
from .core.result_serializer import ResultSerializer
from .core.security_manager import SecurityManager
from .exceptions import AdapterError
from .runtime.concurrency import call_maybe_async


class OpenAIChatRuntime:
    """Use a ToolAnything registry directly with OpenAI Chat Completions tool calling."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        *,
        failure_log: FailureLogManager | None = None,
        result_serializer: ResultSerializer | None = None,
        security_manager: SecurityManager | None = None,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        self.adapter = OpenAIAdapter(
            registry,
            failure_log=failure_log,
            result_serializer=result_serializer,
            security_manager=security_manager,
        )
        self.api_key_env = api_key_env

    def to_schema(self) -> list[dict[str, Any]]:
        """Return OpenAI `tools` payloads derived from the registry."""

        return self.adapter.to_schema()

    def create_tool_call(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        tool_call_id: str | None = None,
    ) -> dict[str, Any]:
        """Build a Chat Completions compatible tool_call payload."""

        return self.adapter.to_function_call(name, dict(arguments or {}), tool_call_id=tool_call_id)

    async def invoke_tool_call(
        self,
        tool_call: Mapping[str, Any],
        *,
        user_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute one OpenAI tool_call payload against the registry."""

        requested_name, arguments = self._parse_tool_call(tool_call)
        resolved_tool_call_id = tool_call_id or str(tool_call.get("id") or "").strip() or None
        return await self.adapter.to_invocation(
            requested_name,
            arguments,
            user_id=user_id,
            tool_call_id=resolved_tool_call_id,
        )

    async def invoke_tool_calls(
        self,
        tool_calls: Sequence[Mapping[str, Any]],
        *,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a batch of OpenAI tool_call payloads in order."""

        results: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            results.append(await self.invoke_tool_call(tool_call, user_id=user_id))
        return results

    def execute_tool_call(
        self,
        tool_call: Mapping[str, Any],
        *,
        user_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> dict[str, Any]:
        """Sync wrapper for `invoke_tool_call`."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.invoke_tool_call(
                    tool_call,
                    user_id=user_id,
                    tool_call_id=tool_call_id,
                )
            )

        raise RuntimeError("事件迴圈運行時請改用 invoke_tool_call。")

    def execute_tool_calls(
        self,
        tool_calls: Sequence[Mapping[str, Any]],
        *,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Sync wrapper for `invoke_tool_calls`."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.invoke_tool_calls(tool_calls, user_id=user_id))

        raise RuntimeError("事件迴圈運行時請改用 invoke_tool_calls。")

    async def run_async(
        self,
        *,
        model: str,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_rounds: int = 4,
        api_key: str | None = None,
        requester: Callable[..., Any] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Run a full OpenAI tool loop against the local registry."""

        resolved_model = model.strip()
        if not resolved_model:
            raise AdapterError("缺少 model")
        resolved_prompt = prompt.strip()
        if not resolved_prompt:
            raise AdapterError("缺少 prompt")
        if max_rounds < 1:
            raise AdapterError("max_rounds 必須大於 0")

        resolved_api_key = (api_key or "").strip() or self._load_api_key()
        tools = self.to_schema()
        messages: list[dict[str, Any]] = []
        transcript: list[dict[str, Any]] = []

        if system_prompt and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": resolved_prompt})
        transcript.append({"role": "user", "content": resolved_prompt})

        completion_requester = requester or self.request_chat_completion
        final_text = ""

        for _ in range(max_rounds):
            assistant_message = await call_maybe_async(
                completion_requester,
                api_key=resolved_api_key,
                model=resolved_model,
                messages=messages,
                tools=tools,
                temperature=temperature,
            )
            if not isinstance(assistant_message, Mapping):
                raise AdapterError("OpenAI requester 必須回傳 dict-like message")

            content = assistant_message.get("content")
            raw_tool_calls = assistant_message.get("tool_calls") or []
            if not isinstance(raw_tool_calls, list):
                raise AdapterError("OpenAI requester 回傳的 tool_calls 必須是 list")

            transcript.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": self.translate_tool_calls(raw_tool_calls),
                }
            )

            if raw_tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": raw_tool_calls,
                    }
                )
                for invocation in await self.invoke_tool_calls(raw_tool_calls, user_id=user_id):
                    transcript.append(invocation)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": invocation["tool_call_id"],
                            "content": invocation["content"],
                        }
                    )
                continue

            final_text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            break
        else:
            raise AdapterError(f"超過 OpenAI 工具呼叫輪數上限: max_rounds={max_rounds}")

        return {
            "model": resolved_model,
            "tools_count": len(tools),
            "final_text": final_text,
            "transcript": transcript,
            "messages": messages,
        }

    def run(
        self,
        *,
        model: str,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_rounds: int = 4,
        api_key: str | None = None,
        requester: Callable[..., Any] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Sync wrapper for `run_async`."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.run_async(
                    model=model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_rounds=max_rounds,
                    api_key=api_key,
                    requester=requester,
                    user_id=user_id,
                )
            )

        raise RuntimeError("事件迴圈運行時請改用 run_async。")

    def translate_tool_calls(
        self,
        tool_calls: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Map OpenAI-safe tool names back to the original registry names."""

        translated: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            normalized = dict(tool_call)
            function = dict(tool_call.get("function") or {})
            name = function.get("name")
            if isinstance(name, str):
                function["name"] = self.adapter.from_openai_name(name)
            normalized["function"] = function
            translated.append(normalized)
        return translated

    @staticmethod
    def request_chat_completion(
        *,
        api_key: str,
        model: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        temperature: float,
    ) -> dict[str, Any]:
        """Call OpenAI Chat Completions with `tools` and `tool_choice=auto`."""

        payload = {
            "model": model,
            "messages": list(messages),
            "tools": list(tools),
            "tool_choice": "auto",
            "temperature": temperature,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = url_request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with url_request.urlopen(req, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8") or "{}")
        except url_error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            details: dict[str, Any] = {"status": exc.code}
            try:
                details["response"] = json.loads(raw_body)
            except json.JSONDecodeError:
                details["response_text"] = raw_body
            raise AdapterError(f"OpenAI API 呼叫失敗: {details}") from exc
        except url_error.URLError as exc:
            raise AdapterError(f"OpenAI API 連線失敗: {getattr(exc, 'reason', exc)}") from exc

        choices = body.get("choices") or []
        if not choices:
            raise AdapterError(f"OpenAI API 未回傳 choices: {body}")
        message = choices[0].get("message") or {}
        return {
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls") or [],
        }

    def _load_api_key(self) -> str:
        api_key = os.getenv(self.api_key_env, "").strip()
        if not api_key:
            raise AdapterError(f"缺少 OpenAI API key: {self.api_key_env}")
        return api_key

    def _parse_tool_call(self, tool_call: Mapping[str, Any]) -> tuple[str, Any]:
        function = tool_call.get("function") or {}
        if not isinstance(function, Mapping):
            raise AdapterError("tool_call.function 必須是 object")

        requested_name = function.get("name")
        if not isinstance(requested_name, str) or not requested_name.strip():
            raise AdapterError("tool_call.function.name 必須是非空字串")

        return requested_name, function.get("arguments")
