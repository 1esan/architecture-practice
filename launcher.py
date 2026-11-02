"""Portable source and PyInstaller launcher for Architecture Practice."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

APP_NAME = "architecture-practice"
DEFAULT_PORT = 8784


def parse_port(value: str | int | None = None) -> int:
    raw = str(value if value is not None else os.environ.get("ARCH_TRAINER_PORT", DEFAULT_PORT))
    try:
        port = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Порт должен быть числом от 1 до 65535") from exc
    if not 1 <= port <= 65535:
        raise ValueError("Порт должен быть числом от 1 до 65535")
    return port


def state_directory() -> pathlib.Path:
    """Return a per-user writable directory, outside a frozen install folder."""
    override = os.environ.get("ARCH_TRAINER_STATE_DIR")
    if override:
        return pathlib.Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            raise RuntimeError("Windows не сообщил папку LOCALAPPDATA для сохранения истории")
        return pathlib.Path(base) / "ArchitecturePractice"
    return pathlib.Path.home() / ".local" / "share" / "ArchitecturePractice"


def resource_directory() -> pathlib.Path:
    if getattr(sys, "frozen", False):
        return pathlib.Path(getattr(sys, "_MEIPASS"))
    return pathlib.Path(__file__).resolve().parent


def url_for(port: int) -> str:
    return f"http://127.0.0.1:{port}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def is_our_server(port: int, timeout: float = 0.5) -> bool:
    request = urllib.request.Request(url_for(port) + "/api/health", headers={"Host": f"127.0.0.1:{port}"})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(request, timeout=timeout) as response:
            data = json.loads(response.read(4096))
        return data.get("app") == APP_NAME
    except (OSError, ValueError, urllib.error.URLError, AttributeError):
        return False


def port_is_free(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def child_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--serve"]
    return [sys.executable, "-B", str(pathlib.Path(__file__).resolve()), "--serve"]


def launch_server(port: int, *, wait_seconds: float = 12.0) -> bool:
    """Start one child if the port is free; never claim or stop an unknown service."""
    if is_our_server(port):
        return True
    if not port_is_free(port):
        raise RuntimeError(f"Порт {port} занят другой программой. Она не была остановлена.")

    state = state_directory()
    state.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["ARCH_TRAINER_PORT"] = str(port)
    env["ARCH_TRAINER_RESOURCE_DIR"] = str(resource_directory())
    env["ARCH_TRAINER_STATE_DIR"] = str(state)
    log_path = state / "server.log"
    log = open(log_path, "ab")
    try:
        process = subprocess.Popen(child_command(), cwd=str(resource_directory()), env=env,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   close_fds=True, **({"creationflags": subprocess.CREATE_NO_WINDOW}
                                                      if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else {}))
    finally:
        log.close()

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if is_our_server(port):
            return True
        if process.poll() is not None:
            if is_our_server(port):
                return True
            if not port_is_free(port):
                raise RuntimeError(f"Порт {port} занят другой программой. Запуск отменён; ничего не остановлено.")
            raise RuntimeError(f"Сервер не запустился. Проверьте журнал: {log_path}")
        time.sleep(0.2)
    if is_our_server(port):
        return True
    if not port_is_free(port):
        raise RuntimeError(f"Порт {port} занят другой программой. Запуск отменён; ничего не остановлено.")
    raise RuntimeError(f"Сервер не запустился. Проверьте журнал: {log_path}")


def serve(port: int) -> None:
    os.environ["ARCH_TRAINER_PORT"] = str(port)
    os.environ.setdefault("ARCH_TRAINER_RESOURCE_DIR", str(resource_directory()))
    os.environ.setdefault("ARCH_TRAINER_STATE_DIR", str(state_directory()))
    os.environ.setdefault("PYTHONUTF8", "1")
    import server
    server.run()


def show_windows_error(message: str) -> None:
    """Show startup failures for a directly double-clicked Windows executable."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "Architecture Practice", 0x10)
    except (AttributeError, ImportError, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Локальный тренажёр Architecture Practice")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-open", action="store_true", help="запустить сервер без открытия браузера")
    parser.add_argument("--port", type=int, help="порт локального сервера (по умолчанию 8784)")
    args = parser.parse_args(argv)
    try:
        port = parse_port(args.port)
        if args.serve:
            serve(port)
            return 0
        if not launch_server(port):
            return 1
        url = url_for(port)
        if not args.no_open:
            webbrowser.open(url)
        print(f"Практика доступна: {url}" if not args.no_open else f"Сервер работает: {url} (браузер не открыт)")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Не удалось запустить Architecture Practice: {exc}", file=sys.stderr)
        if not args.serve and not args.no_open:
            show_windows_error(f"Не удалось запустить Architecture Practice:\n{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
