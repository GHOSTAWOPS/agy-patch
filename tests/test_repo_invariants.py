"""Offline repository sustainability and invariant tests."""

from __future__ import annotations

import unittest

from scripts import check_repo


class RepoInvariantsTests(unittest.TestCase):
    def test_python_compile(self) -> None:
        self.assertEqual(check_repo.check_python_compile(), [])

    def test_shell_syntax(self) -> None:
        self.assertEqual(check_repo.check_shell_syntax(), [])

    def test_site_shapes(self) -> None:
        self.assertEqual(check_repo.check_site_shapes(), [])

    def test_templates_consistency(self) -> None:
        self.assertEqual(check_repo.check_templates(), [])

    def test_privacy_and_secrets(self) -> None:
        self.assertEqual(check_repo.check_privacy_and_secrets(), [])

    def test_markdown_links(self) -> None:
        self.assertEqual(check_repo.check_markdown_links(), [])


if __name__ == "__main__":
    unittest.main()
