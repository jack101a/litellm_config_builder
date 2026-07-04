from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from litellm_config_studio.server import create_app


def find_free_port(preferred: int | None = None) -> int:
    if preferred:
        if is_free(preferred):
            return preferred
        print(f"Port {preferred} is busy. Selecting another free port...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return int(s.getsockname()[1])


def is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", port))
            return True
        except OSError:
            return False


def lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:  # noqa: BLE001
        return None


def open_browser_later(url: str) -> None:
    def _open() -> None:
        time.sleep(0.8)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch LiteLLM Config Studio")
    parser.add_argument("--host", default=None, help="Bind host. Defaults to 127.0.0.1 unless --lan is used.")
    parser.add_argument("--port", type=int, default=None, help="Preferred port. If busy, another free port is selected.")
    parser.add_argument("--lan", action="store_true", help="Bind to 0.0.0.0 and print LAN URL. Use only on trusted networks.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically.")
    args = parser.parse_args(argv)

    host = args.host or ("0.0.0.0" if args.lan else "127.0.0.1")
    port = find_free_port(args.port or 48731)
    local_url = f"http://127.0.0.1:{port}"
    ip = lan_ip()

    print("\nLiteLLM Config Studio")
    print("=" * 24)
    print(f"Local: {local_url}")
    if args.lan and ip:
        print(f"LAN:   http://{ip}:{port}")
        print("Warning: LAN mode exposes this UI to other devices on your network.")
    else:
        print("LAN:   disabled by default. Use --lan to enable.")
    print("\nPress Ctrl+C to stop.\n")

    if not args.no_browser:
        open_browser_later(local_url)

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
