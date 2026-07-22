"""Unit tests for ai_observatory.cli: logging configuration seam."""

from __future__ import annotations

import logging

from ai_observatory.cli import _configure_logging


class TestConfigureLogging:
    def test_httpx_and_httpcore_loggers_raised_to_warning(self) -> None:
        _configure_logging()

        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
