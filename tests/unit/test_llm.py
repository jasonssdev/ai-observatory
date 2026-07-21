"""Unit tests for ai_observatory.synthesis.llm: OllamaClient adapter."""

from __future__ import annotations

import httpx
import pytest

from ai_observatory.synthesis.llm import (
    LLMModelNotFoundError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
    OllamaClient,
)

_URL = "http://localhost:11434"
_MODEL = "llama3.2"
_TIMEOUT = 60.0


def _client_with_handler(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


class TestGenerateSuccess:
    def test_generate_success(self) -> None:
        captured_request: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_request["body"] = request.read()
            return httpx.Response(
                200, json={"response": "hi there", "model": "llama3.2"}
            )

        client = OllamaClient(
            url=_URL,
            model=_MODEL,
            timeout=_TIMEOUT,
            client=_client_with_handler(handler),
        )

        result = client.generate("hello")

        assert result.text == "hi there"
        assert result.model == "llama3.2"
        assert result.raw == {"response": "hi there", "model": "llama3.2"}

        import json as _json

        sent_body = _json.loads(captured_request["body"])
        assert sent_body == {"model": "llama3.2", "prompt": "hello", "stream": False}


class TestGenerateUnreachable:
    def test_generate_unreachable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        client = OllamaClient(
            url=_URL,
            model=_MODEL,
            timeout=_TIMEOUT,
            client=_client_with_handler(handler),
        )

        with pytest.raises(LLMUnavailableError):
            client.generate("hello")


class TestGenerateTimeout:
    def test_generate_timeout(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        client = OllamaClient(
            url=_URL,
            model=_MODEL,
            timeout=_TIMEOUT,
            client=_client_with_handler(handler),
        )

        with pytest.raises(LLMTimeoutError):
            client.generate("hello")


class TestGenerateModelNotFound:
    def test_generate_model_not_found(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                404, json={"error": "model 'llama3.2' not found, try pulling it"}
            )

        client = OllamaClient(
            url=_URL,
            model=_MODEL,
            timeout=_TIMEOUT,
            client=_client_with_handler(handler),
        )

        with pytest.raises(LLMModelNotFoundError):
            client.generate("hello")

    def test_generate_other_non_2xx_raises_response_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "internal server error"})

        client = OllamaClient(
            url=_URL,
            model=_MODEL,
            timeout=_TIMEOUT,
            client=_client_with_handler(handler),
        )

        with pytest.raises(LLMResponseError):
            client.generate("hello")


class TestGenerateMalformedResponse:
    def test_generate_non_json_body(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"not json at all")

        client = OllamaClient(
            url=_URL,
            model=_MODEL,
            timeout=_TIMEOUT,
            client=_client_with_handler(handler),
        )

        with pytest.raises(LLMResponseError):
            client.generate("hello")

    def test_generate_missing_response_key(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"model": "llama3.2"})

        client = OllamaClient(
            url=_URL,
            model=_MODEL,
            timeout=_TIMEOUT,
            client=_client_with_handler(handler),
        )

        with pytest.raises(LLMResponseError):
            client.generate("hello")


class TestClientLifecycle:
    def test_generate_uses_injected_client_directly(self, monkeypatch) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"response": "ok"})

        injected_client = _client_with_handler(handler)

        constructed_clients: list[httpx.Client] = []
        original_init = httpx.Client.__init__

        def tracking_init(self, *args, **kwargs):
            constructed_clients.append(self)
            return original_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.Client, "__init__", tracking_init)

        client = OllamaClient(
            url=_URL, model=_MODEL, timeout=_TIMEOUT, client=injected_client
        )
        constructed_clients.clear()  # ignore construction of injected_client itself

        result = client.generate("hello")

        assert result.text == "ok"
        assert constructed_clients == []

    def test_generate_creates_scoped_client_when_none_injected(
        self, monkeypatch
    ) -> None:
        """No client injected -> a scoped `httpx.Client` is built, used, closed.

        `httpx.Client` itself is replaced with a fake so this test never
        touches the network (zero live Ollama dependency), while still
        proving the production code path constructs a real per-call client
        with the expected `httpx.Timeout` and closes it via `with`.
        """
        captured: dict = {}

        class FakeResponse:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return {"response": "ok"}

        class FakeScopedClient:
            def __init__(self, *, timeout: httpx.Timeout) -> None:
                captured["timeout"] = timeout
                captured["closed"] = False

            def post(self, url: str, json: dict) -> FakeResponse:
                captured["url"] = url
                return FakeResponse()

            def __enter__(self) -> FakeScopedClient:
                return self

            def __exit__(self, *exc_info: object) -> None:
                captured["closed"] = True

        monkeypatch.setattr(
            "ai_observatory.synthesis.llm.httpx.Client", FakeScopedClient
        )

        client = OllamaClient(url=_URL, model=_MODEL, timeout=_TIMEOUT, client=None)

        result = client.generate("hello")

        assert result.text == "ok"
        assert captured["url"] == f"{_URL}/api/generate"
        timeout = captured["timeout"]
        assert timeout.connect == _TIMEOUT
        assert timeout.read == _TIMEOUT
        assert timeout.write == _TIMEOUT
        assert timeout.pool == _TIMEOUT
        assert captured["closed"] is True


if __name__ == "__main__":
    pytest.main([__file__])
