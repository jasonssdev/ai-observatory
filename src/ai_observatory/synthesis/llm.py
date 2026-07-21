"""Local LLM adapter: typed `LLMClient` port + `OllamaClient` implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class LLMResponse:
    """A single completion returned by an `LLMClient`."""

    text: str
    model: str
    raw: dict


class LLMError(Exception):
    """Base class for all `LLMClient` failures. Always raised, never swallowed."""


class LLMUnavailableError(LLMError):
    """Raised when the LLM server cannot be reached."""


class LLMTimeoutError(LLMError):
    """Raised when a request exceeds the configured timeout."""


class LLMModelNotFoundError(LLMError):
    """Raised when the configured model is not available on the server."""


class LLMResponseError(LLMError):
    """Raised when the server response is malformed or otherwise unusable."""


class LLMClient(Protocol):
    """Injectable I/O seam: generates a completion for a prompt."""

    def generate(self, prompt: str) -> LLMResponse: ...


def _as_timeout(timeout: httpx.Timeout | float) -> httpx.Timeout:
    """Normalize a scalar seconds value into an explicit `httpx.Timeout`.

    Bounding connect/read/write/pool separately (rather than relying on a
    single scalar) means a slow-but-alive connection cannot stall a call
    unboundedly on one phase.
    """
    if isinstance(timeout, httpx.Timeout):
        return timeout
    return httpx.Timeout(connect=timeout, read=timeout, write=timeout, pool=timeout)


class OllamaClient:
    """Default `LLMClient` implementation, calling a local Ollama server.

    Tests inject a `client` built with `httpx.MockTransport` to avoid
    network access. Failures are always raised as a typed `LLMError`
    subclass, never swallowed.
    """

    def __init__(
        self,
        url: str,
        model: str,
        timeout: httpx.Timeout | float,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = url
        self._model = model
        self._timeout = timeout
        self._client = client

    def generate(self, prompt: str) -> LLMResponse:
        endpoint = f"{self._url}/api/generate"
        payload = {"model": self._model, "prompt": prompt, "stream": False}

        try:
            if self._client is not None:
                response = self._client.post(endpoint, json=payload)
            else:
                with httpx.Client(timeout=_as_timeout(self._timeout)) as client:
                    response = client.post(endpoint, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise LLMUnavailableError(str(exc)) from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if response.status_code == 404:
                raise LLMModelNotFoundError(str(exc)) from exc
            raise LLMResponseError(str(exc)) from exc

        try:
            body = response.json()
            text = body["response"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise LLMResponseError(str(exc)) from exc

        return LLMResponse(text=text, model=self._model, raw=body)
