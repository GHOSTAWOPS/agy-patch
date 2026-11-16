"""Unit tests for idempotent helpers and dry-run flow in scripts/install.py."""

from __future__ import annotations

import pathlib
import tempfile
import unittest

from scripts import install


class InstallHelpersTests(unittest.TestCase):
    def test_merge_settings_preserves_existing_keys(self) -> None:
        existing = {"model": "Gemini 4 Hydrogen (High)", "trustedWorkspaces": ["/a"]}
        merged = install.merge_settings(existing, "/h/.gemini/antigravity-cli/statusline.sh", "512K")
        self.assertEqual(merged["model"], "Gemini 4 Hydrogen (High)")
        self.assertEqual(merged["trustedWorkspaces"], ["/a"])
        self.assertEqual(merged["contextWindow"], "512K")
        self.assertTrue(merged["statusLine"]["enabled"])

    def test_merge_settings_default_window_removes_key(self) -> None:
        merged = install.merge_settings({"contextWindow": "512K"}, "/s.sh", "Default")
        self.assertNotIn("contextWindow", merged)

    def test_upsert_and_remove_zshrc_block_is_idempotent(self) -> None:
        initial = "export PATH=$HOME/.local/bin:$PATH\n"
        once, state1 = install.upsert_zshrc_block(initial)
        self.assertEqual(state1, "added")
        twice, state2 = install.upsert_zshrc_block(once)
        self.assertEqual(state2, "unchanged")
        self.assertEqual(once, twice)

        cleaned, removed = install.remove_zshrc_block(twice)
        self.assertTrue(removed)
        self.assertEqual(cleaned, initial)

    def test_upsert_skips_if_manual_config_already_present(self) -> None:
        manual = 'export AGY_CLI_DISABLE_AUTO_UPDATE=true\nalias agy="$HOME/.gemini/bin/agy"\n'
        after, state = install.upsert_zshrc_block(manual)
        self.assertEqual(state, "already-configured")
        self.assertEqual(after, manual)

    def test_dry_run_makes_zero_disk_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            fake_bin = home / ".local/bin/agy"
            fake_bin.parent.mkdir(parents=True)
            fake_bin.write_text("#!/bin/sh\necho 1.5.9\n")
            fake_bin.chmod(0o755)

            if not all(install.shutil.which(c) for c in ("codesign", "jq")):
                self.skipTest("codesign/jq required for preflight")

            rc = install.main(
                [
                    "--dry-run",
                    "--home",
                    str(home),
                    "--binary",
                    str(fake_bin),
                    "--force-platform",
                ]
            )
            self.assertEqual(rc, 0)
            self.assertFalse((home / ".zshrc").exists())
            self.assertFalse((home / ".gemini/antigravity-cli/settings.json").exists())


if __name__ == "__main__":
    unittest.main()
