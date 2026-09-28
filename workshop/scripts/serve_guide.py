"""Optionally serve the already-built static guide on localhost."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

GUIDE = Path(__file__).resolve().parents[1] / "guide"


def main() -> None:
    if not (GUIDE / "index.html").is_file():
        raise SystemExit("Guide not found. Run uv run poe docs-build first.")
    handler = partial(SimpleHTTPRequestHandler, directory=str(GUIDE))
    with ThreadingHTTPServer(("127.0.0.1", 8000), handler) as server:
        print("Workshop guide: http://127.0.0.1:8000 (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nGuide server stopped.")


if __name__ == "__main__":
    main()
