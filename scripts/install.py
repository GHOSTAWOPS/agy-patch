#!/usr/bin/env python3
"""Idempotent installer and uninstaller for agy-patch.

Designed for both humans and deploying agents:
  - Preflight checks the platform, Python >= 3.12, required tools, and stock binary + templates.
  - Supports --dry-run to inspect every planned change before touching disk.
  - Applies the binary patch, syncs the runtime wrapper/statusline, configures
    statusLine + contextWindow in ~/.gemini/antigravity-cli/settings.json, and
    manages a clean marker block in ~/.zshrc (macOS) or the PowerShell profile (Windows).
  - Supports --uninstall to cleanly revert the binary and remove installed wrapper/shell block.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

IS_WINDOWS = sys.platform == "win32"
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
POWERSHELL_BLOCK = "\n".join(
    [
        MARKER_BEGIN,
        '$env:AGY_CLI_DISABLE_AUTO_UPDATE = "true"',
        '$agyPatchBin = Join-Path $HOME ".gemini\\bin"',
        'if (($env:PATH -split \';\') -notcontains $agyPatchBin) { $env:PATH = "$agyPatchBin;$env:PATH" }',
        MARKER_END,
    ]
)


def default_binary(home: pathlib.Path) -> pathlib.Path:
    """The installed binary for this platform; Windows uses agy's own install target."""
    if IS_WINDOWS:
        local = pathlib.Path(os.environ.get("LOCALAPPDATA", home))
        candidates = (local / "agy/bin/agy.exe", home / ".local/bin/agy.exe")
        return next((path for path in candidates if path.exists()), candidates[0])
    return home / ".local/bin/agy"


def windows_paths(home: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    """(wrapper .cmd, wrapper .py, statusline .py) for the Windows runtime layer."""
    return (
        home / ".gemini/bin/agy.cmd",
        home / ".gemini/bin/agy_wrapper.py",
        home / ".gemini/antigravity-cli/statusline.py",
    )


def powershell_profile(home: pathlib.Path) -> pathlib.Path:
    """Prefer PowerShell 7's profile, but keep using 5.1's when that is what exists."""
    ps7 = home / "Documents/PowerShell/Microsoft.PowerShell_profile.ps1"
    ps5 = home / "Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1"
    return ps5 if ps5.exists() and not ps7.exists() else ps7


def statusline_command(home: pathlib.Path) -> str:
    if IS_WINDOWS:
        _, _, target = windows_paths(home)
        return f'"{sys.executable}" -I "{target}"'
    return str(home / ".gemini/antigravity-cli/statusline.sh")


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


def remove_statusline_if_managed(
    existing: dict, statusline_cmd: str, statusline_target: pathlib.Path | None = None
) -> tuple[dict, bool]:
    """Remove statusLine only when it points to our managed statusline."""
    updated = dict(existing)
    sl = updated.get("statusLine")
    command = sl.get("command") if isinstance(sl, dict) else None
    managed = {statusline_cmd, "~/.gemini/antigravity-cli/statusline.sh"}
    if isinstance(command, str) and (
        command in managed or (statusline_target is not None and str(statusline_target) in command)
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
        new_text = pattern.sub(lambda _: SHELL_BLOCK + "\n", text, count=1)
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


def upsert_powershell_block(text: str) -> tuple[str, str]:
    """Insert or update the managed agy-patch block in a PowerShell profile."""
    pattern = re.compile(
        rf"(?ms)^{re.escape(MARKER_BEGIN)}\n.*?^{re.escape(MARKER_END)}\n?"
    )
    if pattern.search(text):
        new_text = pattern.sub(lambda _: POWERSHELL_BLOCK + "\n", text, count=1)
        return new_text, "unchanged" if new_text == text else "updated"

    has_export = "AGY_CLI_DISABLE_AUTO_UPDATE" in text
    has_path = ".gemini\\bin" in text
    if has_export and has_path:
        return text, "already-configured"

    sep = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + sep + POWERSHELL_BLOCK + "\n", "added"


def remove_powershell_block(text: str) -> tuple[str, bool]:
    """Remove the managed agy-patch block from a PowerShell profile if present."""
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
    if IS_WINDOWS:
        if not force_platform and (
            platform.system() != "Windows" or platform.machine().lower() not in ("amd64", "x86_64")
        ):
            errors.append(f"Unsupported platform {platform.system()}/{platform.machine()} (requires Windows/amd64)")
    elif not force_platform and (platform.system() != "Darwin" or platform.machine() != "arm64"):
        errors.append(f"Unsupported platform {platform.system()}/{platform.machine()} (requires Darwin/arm64)")
    if sys.version_info < (3, 12):
        errors.append(f"Python >= 3.12 required (found {sys.version.split()[0]})")
    if not IS_WINDOWS:
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


def _windows_wrapper_cmd(binary: pathlib.Path) -> str:
    """A shim with the absolute interpreter and target binary, independent of PATH."""
    return (
        f'@echo off\r\n'
        f'set "AGY_REAL_BINARY={binary}"\r\n'
        f'"{sys.executable}" -I "%~dp0agy_wrapper.py" %*\r\n'
    )


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

    settings_path = home / ".gemini/antigravity-cli/settings.json"
    if IS_WINDOWS:
        wrapper_target, wrapper_py, statusline_target = windows_paths(home)
        runtime_wrapper = REPO / "runtime/agy-wrapper.cmd"
        runtime_wrapper_py = REPO / "runtime/agy_wrapper.py"
        runtime_statusline = REPO / "runtime/statusline.py"
        shell_rc = powershell_profile(home)
        shell_kind = "PowerShell profile"
        statusline_cmd = statusline_command(home)
        upsert_shell = upsert_powershell_block
    else:
        wrapper_target = home / ".gemini/bin/agy"
        statusline_target = home / ".gemini/antigravity-cli/statusline.sh"
        runtime_wrapper = REPO / "runtime/agy-wrapper.sh"
        runtime_statusline = REPO / "runtime/statusline.sh"
        shell_rc = home / ".zshrc"
        shell_kind = "shell rc"
        statusline_cmd = str(statusline_target)
        upsert_shell = upsert_zshrc_block

    existing_settings: dict = {}
    if settings_path.exists():
        try:
            existing_settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError as exc:
            print(f"[error] Invalid JSON in {settings_path}: {exc}", file=sys.stderr)
            return 1
    new_settings = merge_settings(existing_settings, statusline_cmd, window)

    shell_before = shell_rc.read_text() if shell_rc.exists() else ""
    shell_after, shell_state = upsert_shell(shell_before)

    if dry_run:
        print(f"[dry-run] Binary      : {binary} (v{version})")
        print(f"[dry-run] Patch apply : {sys.executable} {REPO / 'patch_agy.py'} --apply")
        print(f"[dry-run] Wrapper     : {runtime_wrapper} -> {wrapper_target}")
        if IS_WINDOWS:
            print(f"[dry-run] Wrapper py  : {runtime_wrapper_py} -> {wrapper_py}")
        print(f"[dry-run] Statusline  : {runtime_statusline} -> {statusline_target}")
        print(f"[dry-run] Settings    : {settings_path} ({'unchanged' if new_settings == existing_settings else 'update'})")
        if not skip_shell:
            print(f"[dry-run] {shell_kind:9s}: {shell_rc} ({shell_state})")
        return 0

    cmd = [
        sys.executable,
        str(REPO / "patch_agy.py"),
        "--apply",
        "--binary",
        str(binary),
    ]
    if not IS_WINDOWS:
        cmd += ["--binary", str(wrapper_target)]
    child_env = os.environ.copy()
    child_env["HOME"] = str(home)
    child_env["USERPROFILE"] = str(home)
    subprocess.run(cmd, check=True, env=child_env)

    if IS_WINDOWS:
        wrapper_target.parent.mkdir(parents=True, exist_ok=True)
        wrapper_target.write_text(_windows_wrapper_cmd(binary), encoding="utf-8", newline="")
        shutil.copy2(runtime_wrapper_py, wrapper_py)
        shutil.copy2(REPO / "runtime/cache_relay.py", wrapper_py.with_name("cache_relay.py"))
        print(f"[cfg]  Installed wrapper {wrapper_target} + {wrapper_py.name}")
    else:
        wrapper_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(runtime_wrapper, wrapper_target)
        os.chmod(wrapper_target, 0o755)

    statusline_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(runtime_statusline, statusline_target)
    if not IS_WINDOWS:
        os.chmod(statusline_target, 0o755)
    print(f"[cfg]  Installed statusline {statusline_target}")

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if new_settings != existing_settings or not settings_path.exists():
        settings_path.write_text(json.dumps(new_settings, indent=2) + "\n")
        print(f"[cfg]  Updated {settings_path} (statusLine + contextWindow={window!r})")
    else:
        print(f"[ok]   {settings_path} already up to date")

    if not skip_shell:
        if shell_after != shell_before:
            shell_rc.parent.mkdir(parents=True, exist_ok=True)
            shell_rc.write_text(shell_after)
            print(f"[cfg]  Updated {shell_rc} ({shell_state} managed agy-patch block)")
        else:
            print(f"[ok]   {shell_rc} ({shell_state})")

    print("\nVerification:")
    subprocess.run(
        [sys.executable, str(REPO / "patch_agy.py"), "--status", "--binary", str(binary)],
        check=True,
        env=child_env,
    )
    if IS_WINDOWS:
        print("\nDone. Open a new PowerShell window and run `agy --version`.")
    else:
        print("\nDone. Open a new shell (or run `source ~/.zshrc`) and check `type agy`.")
    return 0


def uninstall(home: pathlib.Path, binary: pathlib.Path, dry_run: bool, skip_shell: bool) -> int:
    settings_path = home / ".gemini/antigravity-cli/settings.json"
    if IS_WINDOWS:
        wrapper_target, wrapper_py, statusline_target = windows_paths(home)
        shell_rc = powershell_profile(home)
        remove_shell = remove_powershell_block
        shell_kind = "PowerShell profile"
    else:
        wrapper_target = home / ".gemini/bin/agy"
        wrapper_py = None
        statusline_target = home / ".gemini/antigravity-cli/statusline.sh"
        shell_rc = home / ".zshrc"
        remove_shell = remove_zshrc_block
        shell_kind = "shell rc"

    if dry_run:
        print(f"[dry-run] Revert binary  : {binary}")
        print(f"[dry-run] Remove wrapper : {wrapper_target}")
        if wrapper_py is not None:
            print(f"[dry-run] Remove script  : {wrapper_py}")
        print(f"[dry-run] Remove script  : {statusline_target}")
        print(f"[dry-run] Clean settings : {settings_path}")
        if not skip_shell:
            print(f"[dry-run] Clean {shell_kind}: {shell_rc}")
        return 0

    if binary.exists():
        child_env = os.environ.copy()
        child_env["HOME"] = str(home)
        child_env["USERPROFILE"] = str(home)
        subprocess.run(
            [sys.executable, str(REPO / "patch_agy.py"), "--revert", "--binary", str(binary)],
            check=True,
            env=child_env,
        )

    if wrapper_target.exists():
        if IS_WINDOWS or wrapper_target.open("rb").read(2) == b"#!":
            wrapper_target.unlink()
            print(f"[del]  Removed wrapper {wrapper_target}")

    if wrapper_py is not None and wrapper_py.exists():
        wrapper_py.unlink()
        print(f"[del]  Removed {wrapper_py}")
        relay_copy = wrapper_py.with_name("cache_relay.py")
        if relay_copy.exists():
            relay_copy.unlink()
            print(f"[del]  Removed {relay_copy}")

    if statusline_target.exists():
        statusline_target.unlink()
        print(f"[del]  Removed {statusline_target}")

    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            existing = None
        if isinstance(existing, dict):
            cleaned, changed = remove_statusline_if_managed(existing, statusline_command(home), statusline_target)
            if changed:
                settings_path.write_text(json.dumps(cleaned, indent=2) + "\n")
                print(f"[cfg]  Removed managed statusLine from {settings_path}")

    if not skip_shell and shell_rc.exists():
        before = shell_rc.read_text()
        after, removed = remove_shell(before)
        if removed:
            shell_rc.write_text(after)
            print(f"[cfg]  Removed agy-patch block from {shell_rc}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions without modifying files")
    parser.add_argument("--uninstall", action="store_true", help="Revert binary patch and remove installed wrappers")
    parser.add_argument("--set-window", choices=VALID_WINDOWS, default="512K", help="Default contextWindow preset (default: 512K)")
    parser.add_argument("--skip-shell", action="store_true", help="Do not modify ~/.zshrc or the PowerShell profile")
    parser.add_argument("--binary", type=pathlib.Path, help="Target agy binary path (default: the platform install target)")
    parser.add_argument("--home", type=pathlib.Path, default=pathlib.Path.home(), help="Override HOME directory (for testing)")
    parser.add_argument("--force-platform", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    home = args.home.expanduser().resolve()
    binary = (args.binary or default_binary(home)).expanduser().resolve()

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
