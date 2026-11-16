#!/usr/bin/env python3
"""Idempotent installer and uninstaller for agy-patch.

Designed for both humans and deploying agents:
  - Preflight checks OS/arch, Python >= 3.12, jq, codesign, and stock binary + templates.
  - Supports --dry-run to inspect every planned change before touching disk.
  - Applies binary patch, syncs runtime/agy-wrapper.sh and runtime/statusline.sh,
    configures statusLine + contextWindow in ~/.gemini/antigravity-cli/settings.json,
    and manages a clean marker block in ~/.zshrc.
  - Supports --uninstall to cleanly revert the binary and remove installed wrapper/shell block.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import platform
import re
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

MARKER_BEGIN = "# >>> agy-patch >>>"
MARKER_END = "# <<< agy-patch <<<"
VALID_WINDOWS = ("Default", "256K", "512K", "900K")
SHELL_BLOCK = "\n".join(
    [
        MARKER_BEGIN,
        'export AGY_CLI_DISABLE_AUTO_UPDATE=true',
        'alias agy="$HOME/.gemini/bin/agy"',
        MARKER_END,
    ]
)


def merge_settings(existing: dict, statusline_cmd: str, window: str | None) -> dict:
    """Merge statusLine and optional contextWindow into settings without clobbering user keys."""
    updated = dict(existing)
    updated["statusLine"] = {
        "type": "command",
        "command": statusline_cmd,
        "enabled": True,
    }
    if window:
        if window == "Default":
            updated.pop("contextWindow", None)
        else:
            updated["contextWindow"] = window
    return updated


def remove_statusline_if_managed(existing: dict, statusline_cmd: str) -> tuple[dict, bool]:
    """Remove statusLine only when it points to our managed statusline.sh."""
    updated = dict(existing)
    sl = updated.get("statusLine")
    if isinstance(sl, dict) and sl.get("command") in (
        statusline_cmd,
        "~/.gemini/antigravity-cli/statusline.sh",
    ):
        updated.pop("statusLine", None)
        return updated, True
    return updated, False


def upsert_zshrc_block(text: str) -> tuple[str, str]:
    """Insert or update the managed agy-patch block in .zshrc idempotently."""
    pattern = re.compile(
        rf"(?ms)^{re.escape(MARKER_BEGIN)}\n.*?^{re.escape(MARKER_END)}\n?"
    )
    if pattern.search(text):
        new_text = pattern.sub(SHELL_BLOCK + "\n", text, count=1)
        return new_text, "unchanged" if new_text == text else "updated"

    # Avoid duplicating manual exports/aliases already configured by the user.
    has_export = "AGY_CLI_DISABLE_AUTO_UPDATE=true" in text
    has_alias = re.search(r'^\s*alias\s+agy=.*(?:/\.gemini/bin/agy)', text, re.M) is not None
    if has_export and has_alias:
        return text, "already-configured"

    sep = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + sep + SHELL_BLOCK + "\n", "added"


def remove_zshrc_block(text: str) -> tuple[str, bool]:
    """Remove the managed agy-patch block from .zshrc if present."""
    pattern = re.compile(
        rf"(?ms)\n?^{re.escape(MARKER_BEGIN)}\n.*?^{re.escape(MARKER_END)}\n?"
    )
    new_text, count = pattern.subn("\n", text)
    if count == 0:
        return text, False
    new_text = re.sub(r"\n{3,}", "\n\n", new_text).strip("\n")
    if new_text:
        new_text += "\n"
    return new_text, True


def check_prerequisites(binary: pathlib.Path, force_platform: bool = False) -> tuple[list[str], str | None]:
    """Validate runtime prerequisites before patching."""
    errors: list[str] = []
    if not force_platform and (platform.system() != "Darwin" or platform.machine() != "arm64"):
        errors.append(f"Unsupported platform {platform.system()}/{platform.machine()} (requires Darwin/arm64)")
    if sys.version_info < (3, 12):
        errors.append(f"Python >= 3.12 required (found {sys.version.split()[0]})")
    for cmd in ("codesign", "jq"):
        if shutil.which(cmd) is None:
            errors.append(f"Required tool not found in PATH: {cmd}")
    if not binary.exists():
        errors.append(f"Target agy binary not found: {binary}")
        return errors, None

    proc = subprocess.run([str(binary), "--version"], capture_output=True, text=True)
    version = proc.stdout.strip() if proc.returncode == 0 else None
    if not version:
        errors.append(f"Could not read `agy --version` from {binary}")
    elif not (REPO / "templates" / f"v{version}").is_dir():
        errors.append(f"No templates/v{version}/ directory for {binary} (supported: {_supported_versions()})")
    return errors, version


def _supported_versions() -> str:
    versions = sorted(p.name for p in (REPO / "templates").glob("v*") if p.is_dir())
    return ", ".join(versions) or "none"


def install(
    home: pathlib.Path,
    binary: pathlib.Path,
    window: str,
    dry_run: bool,
    skip_shell: bool,
    force_platform: bool,
) -> int:
    errors, version = check_prerequisites(binary, force_platform=force_platform)
    if errors:
        for err in errors:
            print(f"[error] {err}", file=sys.stderr)
        return 1

    wrapper_target = home / ".gemini/bin/agy"
    statusline_target = home / ".gemini/antigravity-cli/statusline.sh"
    settings_path = home / ".gemini/antigravity-cli/settings.json"
    zshrc_path = home / ".zshrc"

    existing_settings: dict = {}
    if settings_path.exists():
        try:
            existing_settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError as exc:
            print(f"[error] Invalid JSON in {settings_path}: {exc}", file=sys.stderr)
            return 1
    new_settings = merge_settings(existing_settings, str(statusline_target), window)

    zshrc_before = zshrc_path.read_text() if zshrc_path.exists() else ""
    zshrc_after, zshrc_state = upsert_zshrc_block(zshrc_before)

    if dry_run:
        print(f"[dry-run] Binary      : {binary} (v{version})")
        print(f"[dry-run] Patch apply : python3 {REPO / 'patch_agy.py'} --apply --set-window {window}")
        print(f"[dry-run] Wrapper     : {REPO / 'runtime/agy-wrapper.sh'} -> {wrapper_target}")
        print(f"[dry-run] Statusline  : {REPO / 'runtime/statusline.sh'} -> {statusline_target}")
        print(f"[dry-run] Settings    : {settings_path} ({'unchanged' if new_settings == existing_settings else 'update'})")
        if not skip_shell:
            print(f"[dry-run] Shell rc    : {zshrc_path} ({zshrc_state})")
        return 0

    cmd = [
        sys.executable,
        str(REPO / "patch_agy.py"),
        "--apply",
        "--set-window",
        window,
        "--binary",
        str(binary),
        "--binary",
        str(wrapper_target),
    ]
    subprocess.run(cmd, check=True)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if new_settings != existing_settings or not settings_path.exists():
        settings_path.write_text(json.dumps(new_settings, indent=2) + "\n")
        print(f"[cfg]  Updated {settings_path} (statusLine + contextWindow={window!r})")
    else:
        print(f"[ok]   {settings_path} already up to date")

    if not skip_shell:
        if zshrc_after != zshrc_before:
            zshrc_path.write_text(zshrc_after)
            print(f"[cfg]  Updated {zshrc_path} ({zshrc_state} managed agy-patch block)")
        else:
            print(f"[ok]   {zshrc_path} ({zshrc_state})")

    print("\nVerification:")
    subprocess.run([sys.executable, str(REPO / "patch_agy.py"), "--status"], check=True)
    print("\nDone. Open a new shell (or run `source ~/.zshrc`) and check `type agy`.")
    return 0


def uninstall(home: pathlib.Path, binary: pathlib.Path, dry_run: bool, skip_shell: bool) -> int:
    wrapper_target = home / ".gemini/bin/agy"
    statusline_target = home / ".gemini/antigravity-cli/statusline.sh"
    settings_path = home / ".gemini/antigravity-cli/settings.json"
    zshrc_path = home / ".zshrc"

    if dry_run:
        print(f"[dry-run] Revert binary  : {binary}")
        print(f"[dry-run] Remove wrapper : {wrapper_target}")
        print(f"[dry-run] Remove script  : {statusline_target}")
        print(f"[dry-run] Clean settings : {settings_path}")
        if not skip_shell:
            print(f"[dry-run] Clean shell rc : {zshrc_path}")
        return 0

    if binary.exists():
        subprocess.run(
            [sys.executable, str(REPO / "patch_agy.py"), "--revert", "--binary", str(binary)],
            check=True,
        )

    if wrapper_target.exists():
        with wrapper_target.open("rb") as f:
            if f.read(2) == b"#!":
                wrapper_target.unlink()
                print(f"[del]  Removed wrapper {wrapper_target}")

    if statusline_target.exists():
        statusline_target.unlink()
        print(f"[del]  Removed {statusline_target}")

    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            existing = None
        if isinstance(existing, dict):
            cleaned, changed = remove_statusline_if_managed(existing, str(statusline_target))
            if changed:
                settings_path.write_text(json.dumps(cleaned, indent=2) + "\n")
                print(f"[cfg]  Removed managed statusLine from {settings_path}")

    if not skip_shell and zshrc_path.exists():
        before = zshrc_path.read_text()
        after, removed = remove_zshrc_block(before)
        if removed:
            zshrc_path.write_text(after)
            print(f"[cfg]  Removed agy-patch block from {zshrc_path}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions without modifying files")
    parser.add_argument("--uninstall", action="store_true", help="Revert binary patch and remove installed wrappers")
    parser.add_argument("--set-window", choices=VALID_WINDOWS, default="512K", help="Default contextWindow preset (default: 512K)")
    parser.add_argument("--skip-shell", action="store_true", help="Do not modify ~/.zshrc")
    parser.add_argument("--binary", type=pathlib.Path, help="Target agy binary path (default: ~/.local/bin/agy)")
    parser.add_argument("--home", type=pathlib.Path, default=pathlib.Path.home(), help="Override HOME directory (for testing)")
    parser.add_argument("--force-platform", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    home = args.home.expanduser().resolve()
    binary = (args.binary or (home / ".local/bin/agy")).expanduser()

    if args.uninstall:
        return uninstall(home, binary, dry_run=args.dry_run, skip_shell=args.skip_shell)
    return install(
        home,
        binary,
        window=args.set_window,
        dry_run=args.dry_run,
        skip_shell=args.skip_shell,
        force_platform=args.force_platform,
    )


if __name__ == "__main__":
    raise SystemExit(main())
