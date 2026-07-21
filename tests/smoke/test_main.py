"""Smoke test: `ai_observatory:main` entry point invokes the typer app."""

from __future__ import annotations

import pytest

import ai_observatory
import ai_observatory.cli as cli_module


class TestMainEntrypoint:
    def test_main_invokes_typer_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        invoked = []
        monkeypatch.setattr(cli_module, "app", lambda: invoked.append(True))

        ai_observatory.main()

        assert invoked == [True]


if __name__ == "__main__":
    pytest.main([__file__])
