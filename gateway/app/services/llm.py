"""Unified LLM client that routes to vLLM or llama.cpp backends."""

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings


class LLMBackend:
    """Abstraction over vLLM and llama.cpp OpenAI-compatible APIs."""

    def __init__(self):
        self._clients: dict[str, httpx.AsyncClient] = {}

    def _get_client(self, backend: str) -> httpx.AsyncClient:
        if backend not in self._clients:
            if backend == "vllm":
                base_url = settings.vllm_base_url
            elif backend == "llama-cpp":
                base_url = settings.llama_cpp_base_url
            else:
                raise ValueError(f"Unknown backend: {backend}")
            self._clients[backend] = httpx.AsyncClient(base_url=base_url, timeout=120.0)
        return self._clients[backend]

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str = "",
        backend: str = "vllm",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs,
    ) -> dict | AsyncIterator[bytes]:
        client = self._get_client(backend)

        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if model:
            payload["model"] = model
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        # Merge any extra params
        for k, v in kwargs.items():
            if k not in payload:
                payload[k] = v

        if stream:
            return self._stream_response(client, payload)
        else:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            return response.json()

    async def _stream_response(
        self, client: httpx.AsyncClient, payload: dict
    ) -> AsyncIterator[bytes]:
        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield (line + "\n\n").encode()

    async def list_models(self, backend: str = "vllm") -> dict:
        client = self._get_client(backend)
        response = await client.get("/models")
        response.raise_for_status()
        return response.json()

    async def create_embedding(
        self, input_text: str | list[str], model: str = "", backend: str = "vllm"
    ) -> dict:
        client = self._get_client(backend)
        payload: dict[str, Any] = {"input": input_text}
        if model:
            payload["model"] = model
        response = await client.post("/embeddings", json=payload)
        response.raise_for_status()
        return response.json()

    async def health_check(self, backend: str = "vllm") -> bool:
        try:
            client = self._get_client(backend)
            response = await client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()


# Singleton
llm_backend = LLMBackend()
