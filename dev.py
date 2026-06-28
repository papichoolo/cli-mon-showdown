#!/usr/bin/env python3
"""One-command launcher for CLI-Mon Showdown.

Bootstraps the environment (venv, Python deps, frontend deps), verifies
prerequisites (Node, the Pokemon Showdown clone), then starts and supervises
all long-running services:

  - server.py    FastAPI WebSocket battle server   (:8000)
  - dashboard.py agent state dashboard             (:8080)
  - frontend/    Vite dev server                   (:5173)

The Pokemon Showdown simulator is NOT started here: server.py spawns it as a
child process per WebSocket connection, and because that child shares this
launcher's process group it is reaped automatically on shutdown.

Usage:
    python dev.py                  # bootstrap + run everything
    python dev.py --no-frontend    # skip the Vite dev server
    python dev.py --no-install     # skip dependency installation
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
FRONTEND = ROOT / "frontend"
SHOWDOWN = ROOT / "pokemon-showdown"
REQUIREMENTS = ROOT / "requirements.txt"

IS_WINDOWS = platform.system() == "Windows"

COLORS = {
    "setup": "\033[33m",
    "server": "\033[36m",
    "dashboard": "\033[35m",
    "frontend": "\033[32m",
}
RESET = "\033[0m"
BOLD = "\033[1m"


def supports_color() -> bool:
    return sys.stdout.isatty() and not IS_WINDOWS


def log(name: str, message: str) -> None:
    if supports_color():
        color = COLORS.get(name, "")
        print(f"{color}[{name:<9}]{RESET} {message}", flush=True)
    else:
        print(f"[{name:<9}] {message}", flush=True)


def die(message: str) -> "None":
    log("setup", f"ERROR: {message}")
    sys.exit(1)


def venv_python() -> Path:
    if IS_WINDOWS:
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
def ensure_prerequisites() -> None:
    if shutil.which("node") is None:
        die("Node.js is required but `node` was not found on PATH.")
    if shutil.which("npm") is None:
        die("npm is required but `npm` was not found on PATH.")

    entry = SHOWDOWN / "pokemon-showdown"
    if not entry.exists():
        die(
            f"Pokemon Showdown not found at {SHOWDOWN}.\n"
            "        Clone and build it first:\n"
            "          git clone https://github.com/smogon/pokemon-showdown.git\n"
            "          cd pokemon-showdown && npm ci && cd .."
        )


def ensure_venv(install: bool) -> None:
    if not VENV.exists():
        log("setup", "Creating virtual environment at .venv ...")
        venv.create(VENV, with_pip=True)

    if install:
        log("setup", "Installing Python dependencies ...")
        try:
            subprocess.run(
                [str(venv_python()), "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS)],
                check=True,
            )
        except subprocess.CalledProcessError:
            die("Failed to install Python dependencies from requirements.txt.")


def ensure_frontend(install: bool) -> None:
    if not (FRONTEND / "node_modules").exists() or install:
        if not (FRONTEND / "node_modules").exists():
            log("setup", "Installing frontend dependencies (npm install) ...")
            try:
                subprocess.run(["npm", "install"], cwd=FRONTEND, check=True)
            except subprocess.CalledProcessError:
                die("Failed to run `npm install` in frontend/.")


def load_env() -> dict[str, str]:
    env = os.environ.copy()
    env_file = ROOT / ".env"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            env.setdefault(key.strip(), value)

    if not env.get("OPENROUTER_API_KEY") and not env.get("OPENAI_API_KEY"):
        log(
            "setup",
            "WARNING: no OPENROUTER_API_KEY / OPENAI_API_KEY set. "
            "The LLM agent will fail until you add one to .env.",
        )
    return env


# --------------------------------------------------------------------------- #
# Process supervision
# --------------------------------------------------------------------------- #
procs: dict[str, subprocess.Popen] = {}
stopping = threading.Event()


def stream_output(name: str, proc: subprocess.Popen) -> None:
    assert proc.stdout is not None
    for raw in iter(proc.stdout.readline, ""):
        if raw:
            log(name, raw.rstrip("\n"))
    proc.stdout.close()


def spawn(name: str, cmd: list[str], env: dict[str, str], cwd: Path | None = None) -> None:
    log("setup", f"starting {name}: {' '.join(cmd)}")
    kwargs: dict = dict(
        cwd=str(cwd or ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **kwargs)
    procs[name] = proc
    threading.Thread(target=stream_output, args=(name, proc), daemon=True).start()


def _terminate(proc: subprocess.Popen, force: bool = False) -> None:
    if proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, OSError):
        pass


def shutdown(*_args) -> None:
    if stopping.is_set():
        return
    stopping.set()
    log("setup", "Shutting down all services ...")

    for proc in procs.values():
        _terminate(proc, force=False)

    deadline = time.time() + 8
    for name, proc in procs.items():
        try:
            proc.wait(timeout=max(0.0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            log("setup", f"force-killing {name} ...")
            _terminate(proc, force=True)

    log("setup", "All services stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the CLI-Mon Showdown stack.")
    parser.add_argument("--no-frontend", action="store_true", help="don't start the Vite dev server")
    parser.add_argument("--no-install", action="store_true", help="skip dependency installation")
    parser.add_argument("--server-port", default="8000")
    parser.add_argument("--frontend-port", default="5173")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()


    ensure_prerequisites()
    ensure_venv(install=not args.no_install)
    if not args.no_frontend:
        ensure_frontend(install=not args.no_install)
    env = load_env()
    py = str(venv_python())

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    spawn(
        "server",
        [py, "-m", "uvicorn", "server:app", "--host", args.host, "--port", args.server_port],
        env,
    )
    if not args.no_frontend:
        spawn(
            "frontend",
            ["npm", "run", "dev", "--", "--host", args.host, "--port", args.frontend_port],
            env,
            cwd=FRONTEND,
        )


    log("setup", f"{BOLD}Stack is up.{RESET}" if supports_color() else "Stack is up.")
    log("setup", f"  battle server : http://{args.host}:{args.server_port}")
    if not args.no_frontend:
        log("setup", f"  frontend      : http://{args.host}:{args.frontend_port}")
    log("setup", "Press Ctrl-C to stop everything.")


    try:
        while not stopping.is_set():
            for name, proc in list(procs.items()):
                code = proc.poll()
                if code is not None:
                    log("setup", f"{name} exited (code {code}); tearing down the stack.")
                    shutdown()
                    sys.exit(code or 0)
            time.sleep(0.5)
    finally:
        shutdown()


if __name__ == "__main__":
    main()
