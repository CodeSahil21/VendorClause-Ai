# Standard library
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

# Third-party
import httpx

# Local
from src.shared.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class MCPToolCall:
    server: str
    tool_name: str
    params: dict[str, Any]


class MCPClient:
    """Thin MCP client for Qdrant/Neo4j FastAPI MCP servers."""

    def __init__(self, timeout_seconds: float = 30.0, sse_health_ttl_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds
        self.sse_health_ttl_seconds = sse_health_ttl_seconds
        self._server_urls = {
            "qdrant": settings.qdrant_mcp_url,
            "neo4j": settings.neo4j_mcp_url,
        }
        self._last_health_ok: dict[str, float] = {}
        self._request_headers = {
            "X-API-Key": settings.mcp_auth_key,
        }
        self._http_client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def aclose(self) -> None:
        await self._http_client.aclose()

    def _resolve_server_url(self, server: str) -> str:
        if server.startswith("http://") or server.startswith("https://"):
            return server.rstrip("/")
        if server not in self._server_urls:
            raise ValueError(f"Unknown MCP server '{server}'. Expected one of: {list(self._server_urls.keys())}")
        return self._server_urls[server].rstrip("/")

    async def _check_health(self, base_url: str, max_retries: int = 2) -> None:
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                response = await self._http_client.get(f"{base_url}/health")
                response.raise_for_status()
                self._last_health_ok[base_url] = time.monotonic()
                return
            except Exception as exc:
                last_error = exc
                if attempt < max_retries:
                    await asyncio.sleep(0.2 * attempt)
        if last_error:
            raise last_error

    def _needs_http_healthcheck(self, base_url: str) -> bool:
        last_ok = self._last_health_ok.get(base_url)
        if last_ok is None:
            return True
        return (time.monotonic() - last_ok) > self.sse_health_ttl_seconds

    async def call_tool(self, server: str, tool_name: str, params: dict[str, Any]) -> Any:
        """Health-check (TTL gated), call /messages, return decoded tool results."""
        base_url = self._resolve_server_url(server)

        # Health-check server (TTL-gated). Retry once on transient failure.
        for attempt in range(1, 3):
            try:
                if self._needs_http_healthcheck(base_url):
                    await self._check_health(base_url)

                payload = {
                    "tool": tool_name,
                    "params": params,
                }
                response = await self._http_client.post(
                    f"{base_url}/messages",
                    json=payload,
                    headers=self._request_headers,
                )
                response.raise_for_status()
                data = response.json()

                if not isinstance(data, dict):
                    raise ValueError("MCP server returned non-dict response")
                if not data.get("success", False):
                    raise RuntimeError(data.get("error", "Unknown MCP tool error"))

                return data.get("results", [])
            except Exception as exc:
                if attempt == 2:
                    raise
                logger.warning(
                    "MCP call retry for %s.%s after error: %s",
                    server,
                    tool_name,
                    exc,
                )
                await asyncio.sleep(0.5)

        return []

    async def parallel_dispatch(self, calls: list[MCPToolCall]) -> list[Any]:
        """Dispatch multiple MCP calls concurrently."""
        tasks = [
            self.call_tool(call.server, call.tool_name, call.params)
            for call in calls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        normalized: list[Any] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                normalized.append(
                    {
                        "success": False,
                        "server": calls[i].server,
                        "tool": calls[i].tool_name,
                        "error": str(result),
                    }
                )
            else:
                normalized.append(result)
        return normalized
