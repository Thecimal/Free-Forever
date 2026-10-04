"""Local model source: a local runtime speaking the Ollama native API."""

from __future__ import annotations

import os

import httpx

from .contract import Task
from .source import HttpSource, build_messages

DEFAULT_BASE_URL = "http://localhost:11434"


class LocalModelSource(HttpSource):
    type = "local"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        source_id: str = "local",
        timeout: float = 180.0,
        probe_timeout: float = 5.0,
        temperature: float = 0.2,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            source_id, model, timeout=timeout, probe_timeout=probe_timeout, client=client
        )
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature

    @classmethod
    def from_env(cls) -> LocalModelSource:
        return cls(
            base_url=os.environ.get("LOCAL_BASE_URL", DEFAULT_BASE_URL),
            model=os.environ["LOCAL_MODEL"],
        )

    def _complete(self, task: Task) -> tuple[object, object]:
        payload = {
            "model": self.model,
            "messages": build_messages(task),
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        response = self._send(
            "POST", f"{self.base_url}/api/chat", json=payload, timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"], data.get("model")

    def _probe(self) -> None:
        response = self._send("GET", f"{self.base_url}/api/tags", timeout=self.probe_timeout)
        response.raise_for_status()
