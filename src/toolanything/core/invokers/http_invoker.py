"""HTTP source invoker."""
from __future__ import annotations

import asyncio
import json
import socket
from typing import Any, Mapping
from urllib import error as url_error
from urllib import parse as url_parse
from urllib import request as url_request

from ...exceptions import ToolError
from ..credentials import CredentialResolver
from ..runtime_types import ExecutionContext, InvocationResult, StreamEmitter
from ..source_specs import HttpFieldSpec, HttpSourceSpec


def _json_clone(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(value)))


class HttpInvoker:
    """用宣告式 HTTP source 呼叫上游 API。"""

    def __init__(
        self,
        source: HttpSourceSpec,
        *,
        credential_resolver: CredentialResolver | None = None,
    ) -> None:
        self.source = source
        self.credential_resolver = credential_resolver or CredentialResolver()

    def _extract_fields(
        self,
        arguments: Mapping[str, Any],
        field_specs: tuple[HttpFieldSpec, ...],
        *,
        location: str,
    ) -> dict[str, Any]:
        extracted: dict[str, Any] = {}
        for field in field_specs:
            input_key = field.input_key
            if input_key not in arguments:
                if field.required:
                    raise ToolError(
                        f"缺少必要 {location} 參數: {input_key}",
                        error_type="validation_error",
                        data={"location": location, "field": input_key},
                    )
                continue
            extracted[field.name] = arguments[input_key]
        return extracted

    def _render_path(self, arguments: Mapping[str, Any]) -> str:
        path_values = self._extract_fields(arguments, self.source.path_params, location="path")
        encoded_values = {key: url_parse.quote(str(value), safe="") for key, value in path_values.items()}

        try:
            return self.source.path.format(**encoded_values)
        except KeyError as exc:
            raise ToolError(
                f"路徑模板缺少參數 {exc.args[0]}",
                error_type="validation_error",
                data={"location": "path", "field": exc.args[0]},
            ) from exc

    def _render_query(self, arguments: Mapping[str, Any]) -> str:
        query_values = self._extract_fields(arguments, self.source.query_params, location="query")
        if not query_values:
            return ""
        return url_parse.urlencode(query_values, doseq=True)

    def _render_body(self, arguments: Mapping[str, Any]) -> bytes | None:
        if not self.source.body_params:
            return None

        raw_body = arguments.get("body", {})
        if raw_body is None:
            raw_body = {}
        if not isinstance(raw_body, Mapping):
            raise ToolError(
                "body 參數必須為 object",
                error_type="validation_error",
                data={"location": "body"},
            )

        body_values = self._extract_fields(raw_body, self.source.body_params, location="body")
        return json.dumps(body_values, ensure_ascii=False).encode("utf-8")

    def _render_headers(self, arguments: Mapping[str, Any]) -> dict[str, str]:
        headers: dict[str, str] = {}
        format_values = {key: value for key, value in arguments.items() if not isinstance(value, Mapping)}
        for header_name, template in self.source.header_templates.items():
            headers[header_name] = template.format(**format_values)

        headers.update(self.credential_resolver.resolve_headers(self.source.auth_ref))
        if self.source.body_params:
            headers.setdefault("Content-Type", "application/json; charset=utf-8")
        return headers

    def _build_request(self, arguments: Mapping[str, Any]) -> url_request.Request:
        path = self._render_path(arguments)
        query = self._render_query(arguments)
        url = url_parse.urljoin(self.source.base_url.rstrip("/") + "/", path.lstrip("/"))
        if query:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"

        body = self._render_body(arguments)
        headers = self._render_headers(arguments)
        return url_request.Request(
            url=url,
            data=body,
            headers=headers,
            method=self.source.method.upper(),
        )

    def _parse_response(self, response) -> Any:
        payload = response.read()
        if not payload:
            return None

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return json.loads(payload.decode("utf-8"))
        return payload.decode("utf-8")

    def _map_http_error(self, exc: url_error.HTTPError) -> ToolError:
        body = exc.read().decode("utf-8", errors="replace")
        return ToolError(
            f"上游 HTTP 錯誤: {exc.code}",
            error_type="upstream_http_error",
            data={"status": exc.code, "reason": exc.reason, "body": body},
        )

    def _map_transport_error(self, exc: Exception) -> ToolError:
        if isinstance(exc, TimeoutError | socket.timeout):
            return ToolError(
                "HTTP 請求逾時",
                error_type="upstream_timeout",
                data={"timeout_sec": self.source.timeout_sec},
            )

        return ToolError(
            "HTTP 請求失敗",
            error_type="upstream_network_error",
            data={"message": str(exc)},
        )

    async def invoke(
        self,
        input: Mapping[str, Any] | None,
        context: ExecutionContext,
        stream: StreamEmitter | None = None,
        *,
        inject_context: bool = False,
        context_arg: str = "context",
    ) -> InvocationResult:
        del context, stream, inject_context, context_arg

        arguments = _json_clone(input or {})
        request = self._build_request(arguments)
        attempts = max(self.source.retry_policy.max_attempts, 1)
        last_error: ToolError | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = await __import__("asyncio").to_thread(
                    url_request.urlopen,
                    request,
                    timeout=self.source.timeout_sec,
                )
                with response:
                    return InvocationResult(output=self._parse_response(response))
            except url_error.HTTPError as exc:
                last_error = self._map_http_error(exc)
            except (url_error.URLError, TimeoutError, socket.timeout) as exc:
                last_error = self._map_transport_error(exc)

            if attempt < attempts and self.source.retry_policy.backoff_sec > 0:
                await asyncio.sleep(self.source.retry_policy.backoff_sec)

        assert last_error is not None
        raise last_error


__all__ = ["HttpInvoker"]
