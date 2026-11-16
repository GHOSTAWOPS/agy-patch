"""Unit tests for integrations/consult_gemini pure helpers."""

from __future__ import annotations

import pathlib
import sys
import unittest

INTEGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "integrations"
if str(INTEGRATIONS_DIR) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS_DIR))

from consult_gemini.acp_client import AcpError, detect_soft_error, split_retry_notices
from consult_gemini.service import normalize_model
from consult_gemini.usage_db import TurnUsage


class ConsultGeminiTests(unittest.TestCase):
    def test_split_retry_notices(self) -> None:
        raw = "⚠ API error (attempt 1): 429 rate limit\nHello world"
        clean, notices = split_retry_notices(raw)
        self.assertEqual(clean, "Hello world")
        self.assertEqual(notices, ["429 rate limit"])

    def test_detect_soft_error(self) -> None:
        err = detect_soft_error("Verification Required")
        self.assertIsInstance(err, AcpError)
        self.assertEqual(err.kind, "VERIFY")
        self.assertIsNone(detect_soft_error("Everything looks good."))

    def test_normalize_model_strips_effort_suffix(self) -> None:
        self.assertEqual(normalize_model("gemini-4-carbon-high"), "gemini-4-carbon")
        self.assertEqual(normalize_model("gemini-3.8-flash"), "gemini-3.8-flash")

    def test_turn_usage_format_summary(self) -> None:
        usage = TurnUsage(input_tokens=1000, cached_read_tokens=9000, output_tokens=200, thought_tokens=50, ttft_seconds=1.2, stream_tps=48.3)
        summary = usage.format_summary()
        self.assertIn("in=10,000 (90% cached)", summary)
        self.assertIn("out=200 (thought=50)", summary)
        self.assertIn("ttft=1.2s", summary)
        self.assertIn("tps=48", summary)


if __name__ == "__main__":
    unittest.main()
