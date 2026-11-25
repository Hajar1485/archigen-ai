"""Ouvrir la maquette et servir uniquement la boucle locale."""
import socket
import threading
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

BASE = "http://127.0.0.1:8000"
URL = BASE + "/?exemple=simple#view3d"


def same_viewer():
    try:
        with urlopen(BASE + "/viewer/controller.js", timeout=1) as response:
            return response.read() == Path("frontend/viewer/controller.js").read_bytes()
    except (OSError, URLError):
        return False


def open_when_ready():
    for _ in range(100):
        if same_viewer():
            webbrowser.open(URL)
            return
        time.sleep(0.15)


def main():
    print(URL, flush=True)
    if same_viewer():
        webbrowser.open(URL)
        return
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", 8000))
        except OSError as exc:
            raise SystemExit("Port 8000 occupé. Fermez le service local qui l’utilise.") from exc
        threading.Thread(target=open_when_ready, daemon=True).start()
        server = uvicorn.Server(uvicorn.Config("api.main:app", host="127.0.0.1", port=8000))
        server.run(sockets=[sock])


if __name__ == "__main__":
    main()
