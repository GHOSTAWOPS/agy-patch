#!/usr/bin/env python3
"""Windows wrapper for a patched agy: auto-update guard + prompt-cache keepalive.

Mirrors runtime/agy-wrapper.sh without a POSIX shell. `agy.cmd` calls this file
with the user's arguments; the script finds the real binary, optionally starts
the loopback cache relay for interactive/ACP sessions, and waits for agy so the
relay can be stopped on exit.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import threading

DISABLE_AUTO_UPDATE = "AGY_CLI_DISABLE_AUTO_UPDATE"
PRINT_ONLY = {"-p", "--print", "--prompt", "--login", "--help", "-h"}


def real_binary() -> pathlib.Path:
    override = os.environ.get("AGY_REAL_BINARY")
    if override:
        return pathlib.Path(override).expanduser()
    local = pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home()))
    candidates = (
        local / "agy/bin/agy.exe",
        pathlib.Path.home() / ".local/bin/agy.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit(f"agy-patch: cannot find the installed agy.exe (looked in {', '.join(map(str, candidates))})")


def relay_script() -> pathlib.Path | None:
    candidates = (
        pathlib.Path(os.environ.get("AGY_PATCH_REPO", "")) / "runtime/cache_relay.py"
        if os.environ.get("AGY_PATCH_REPO")
        else None,
        pathlib.Path.home() / ".gemini/agy-patch/runtime/cache_relay.py",
        pathlib.Path(__file__).with_name("cache_relay.py"),
    )
    return next((path for path in candidates if path and path.is_file()), None)


def wants_relay(args: list[str]) -> bool:
    if os.environ.get("AGY_CACHE_RELAY") == "off":
        return False
    if "--hub" in args:
        return False
    if args and args[0] == "acp":
        return True
    if not args:
        return True
    if args[0].startswith("-"):
        return not any(arg == flag or arg.startswith(flag + "=") for arg in args for flag in PRINT_ONLY)
    return False


def start_relay(script: pathlib.Path) -> tuple[subprocess.Popen[str], int] | None:
    env = os.environ.copy()
    upstream = env.get("GOOGLE_GEMINI_BASE_URL")
    command = [sys.executable, "-I", str(script), "--parent", str(os.getpid())]
    if upstream and upstream != env.get("AGY_CACHE_RELAY"):
        command += ["--gemini-upstream", upstream]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        relay = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=flags,
        )
    except OSError:
        return None

    line: list[str] = []

    def read_port() -> None:
        if relay.stdout is not None:
            line.append(relay.stdout.readline().strip())

    reader = threading.Thread(target=read_port, daemon=True)
    reader.start()
    reader.join(3)
    if not line or not line[0].isdigit():
        relay.terminate()
        return None
    return relay, int(line[0])


def main(argv: list[str]) -> int:
    args = list(argv)
    env = os.environ.copy()
    env[DISABLE_AUTO_UPDATE] = "true"
    binary = real_binary()
    relay: subprocess.Popen[str] | None = None
    upstream = env.get("GOOGLE_GEMINI_BASE_URL")
    if wants_relay(args):
        script = relay_script()
        if script is not None:
            started = start_relay(script)
            if started is not None:
                relay, port = started
                env["AGY_CACHE_RELAY"] = f"http://127.0.0.1:{port}"
                env["CLOUD_CODE_URL"] = env["AGY_CACHE_RELAY"]
                if upstream and upstream != env["AGY_CACHE_RELAY"]:
                    env["AGY_GEMINI_UPSTREAM"] = upstream
                    env["GOOGLE_GEMINI_BASE_URL"] = env["AGY_CACHE_RELAY"]
    try:
        return subprocess.run([str(binary), *args], env=env).returncode
    finally:
        if relay is not None:
            relay.terminate()
            try:
                relay.wait(timeout=5)
            except subprocess.TimeoutExpired:
                relay.kill()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
