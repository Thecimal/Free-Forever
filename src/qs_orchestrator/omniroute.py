"""OmniRoute source: an OpenAI-compatible gateway endpoint."""

from __future__ import annotations

import os

import httpx

from .contract import Task
from .source import HttpSource, render_task


class OmniRouteSource(HttpSource):
    type = "api"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        source_id: str = "omniroute",
        timeout: float = 180.0,
        probe_timeout: float = 5.0,
        temperature: float = 0.2,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            source_id, model, timeout=timeout, probe_timeout=probe_timeout, client=client
        )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature

    @classmethod
    def from_env(cls) -> OmniRouteSource:
        return cls(
            base_url=os.environ["LLM_BASE_URL"],
            api_key=os.environ["LLM_API_KEY"],
            model=os.environ["LLM_MODEL"],
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _complete(self, task: Task) -> tuple[object, object]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": render_task(task)}],
            "temperature": self.temperature,
        }
        response = self._send(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"], data.get("model")

    def _probe(self) -> None:
        response = self._send(
            "GET", f"{self.base_url}/models", headers=self._headers(), timeout=self.probe_timeout
        )
        response.raise_for_status()
