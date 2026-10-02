"""Executors turn a Task into a normalized Result.

Callers only see ``executor.execute(task)``. How the model is reached
(OmniRoute today; browser, local or other API sources later) stays behind
this interface.
"""

from __future__ import annotations

import os
import time
from typing import Protocol

import httpx

from .contract import Result, Status, Task


class Executor(Protocol):
    def execute(self, task: Task) -> Result: ...


class OmniRouteExecutor:
    """Runs a Task against an OmniRoute (OpenAI-compatible) endpoint."""

    source = "omniroute"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 180.0,
        temperature: float = 0.2,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self._client = client

    @classmethod
    def from_env(cls) -> OmniRouteExecutor:
        return cls(
            base_url=os.environ["LLM_BASE_URL"],
            api_key=os.environ["LLM_API_KEY"],
            model=os.environ["LLM_MODEL"],
        )

    def execute(self, task: Task) -> Result:
        content = "\n\n".join([*task.context, task.prompt])
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "temperature": self.temperature,
        }
        start = time.perf_counter()
        try:
            response = self._post(payload)
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            if not isinstance(text, str):
                raise TypeError("response message content is not a string")
            model = data.get("model")
            if not isinstance(model, str) or not model:
                model = self.model
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            return self._result("", self.model, "error", start, f"{type(exc).__name__}: {exc}")
        return self._result(text, model, "success", start)

    def _post(self, payload: dict) -> httpx.Response:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self._client is not None:
            return self._client.post(url, headers=headers, json=payload, timeout=self.timeout)
        return httpx.post(url, headers=headers, json=payload, timeout=self.timeout)

    def _result(
        self, content: str, model: str, status: Status, start: float, error: str | None = None
    ) -> Result:
        latency_ms = round((time.perf_counter() - start) * 1000)
        return Result(
            content=content,
            source=self.source,
            model=model,
            status=status,
            latency_ms=latency_ms,
            error=error,
        )
